# 字幕同步修复 + 引号感知断句

本文档记录 2026-11 这轮字幕质量修复的设计、机制与验证方法。
涉及两条独立流水线：**退化段时间戳修复**（对齐漂移/钉死）与**引号感知断句**（引号对被拆开）。

## 问题与根因

> 2026-11-06 晚间复盘（01_part1）：下文"问题 1"的根因分析只说对了表层。
> "词→岛全局 DP 分配"机制（当日早间上线）自己制造了更严重的系统性错位，
> 当晚已整体替换为 v3"逐段候选窗 ASR 重探测"机制，详见 B 节与
> `SYNC_REPAIR_PROGRESS.md`。以下根因记录保留作背景。

### 问题 1：单句字幕与视频对不上（如 Flipped 02_part2 的 1:15 "Three blocks away."）

根因链：

1. VAD 切块后 `_merge_adjacent_segments` 把间隔 ≤0.5s 的相邻块合并成长块
   （实测最长 17.3s）。
2. `Qwen3ASRModel.transcribe(return_time_stamps=True)` **内部已按块调用 forced
   aligner** —— 现有词级时间戳本就是 aligner 输出。
3. **aligner 在含多个句间停顿的长窗口上不稳定**：句尾短句的时间戳被压缩/前移
   到静音里。实测案例（`cache/02_part2_130405428`）：
   - `Three blocks away.` 标称 75.98–76.38s，该区间近乎无声，真实语音在 76.3–77.5s
   - `Nothing.` / `Oh, okay.` 双双钉死在 236.632s、时长为零
   - `My mistake.` 早漂一个短语（它的音频其实是 "Oh, okay." 的）
4. 而在**语音岛边界的紧窗口**上重对齐，结果准确（中英文均实测可用）。

**2026-11-06 补充（重新生成缓存后发现的更深层问题）**：ASR 内部对齐不只"个别段漂移"，
而是把文本**系统性向块首压缩**。逐岛核算 `02_part2` 缓存：**170 个语音岛中 24 个（14%）
完全无人认领**（真实语音存在却没有任何词落在里面），多段文本挤进早期岛（island0 塞了
10.6s 语音量的文本）。更麻烦的是存在 **off-by-one 自洽错位**：如 `They're just visually
challenged.` 的词恰好坐满上一句的尾音岛 [17.05,18.1]——零时长词为零、每词时长正常、
时间与错误岛完美吻合，一切局部判据（退化检测/岛归属）全部漏检，点击字幕指向错误的音频。
错位是全局序列问题（文本序 ↔ 语音岛序的对应断了），局部启发式无法修复，
由此产生了下文的"词→岛全局 DP 分配"机制。

附带修复的 aligner 调用层 bug（此前任何外部对齐调用都静默失败）：

- `language=None` 会让 aligner 崩溃（`encode_timestamp` 里 `.lower()`），
  而 `alignment_service` 恰好把 `"auto"` 转成 `None`
- `aligner_model.align()` 解析 `result["segments"]`，但 aligner 实际返回
  `List[ForcedAlignResult]`（`.items` 可迭代）→ 永远返回空列表
  → `_apply_alignment_to_segments` 是双重损坏的死代码，已删除

### 问题 2：双引号对被拆开，下一条字幕以孤立引号开头

`punct_segmentation.group_by_punctuation` 把段末属于开引号集合的字符一律移到
下一段开头。直引号 `"` / `'` 开闭同形，**闭引号也被当开引号移动**：

```
I asked, "Is everything okay?" She said yes...
  → 切成：I asked, "Is everything okay?   /   " She said yes...
```

## 修复设计

### A. Aligner 调用层（`aligner_model.py` / `alignment_service.py`）

- `normalize_align_language`：`None` / `""` / `"auto"` 统一规整为 `"auto"`
  （落入库的通用分词分支，中英混排均可用）
- 结果解析改为迭代 `results[0]` 的 items（`.text` / `.start_time` / `.end_time`）
- 新增 `align_waveform((np.ndarray, sr), text, language)`：直接传波形元组，免临时文件
- 新增 `refine_alignment(wav, sr, text, window, language)`：按窗口切片后对齐，
  返回全量音频时间坐标的词列表

设备说明：ASR / aligner 模型加载跟随 `settings.DEVICE`
（`config.py` 启动时自动检测 CUDA，插拔显卡后需重启服务重新检测）；
新增代码无 GPU 假设，重对齐走同一模型单例，接上显卡坞即自动用 GPU。
`speech_islands` 的包络计算是纯 numpy（毫秒级），不值得上 GPU。

### B. 同步修复通道（`subtitle_service._refine_segment_timing`）

主修复。机制迭代过三版，教训链很重要，别走回头路：

| 版本 | 机制 | 结果 / 教训 |
|---|---|---|
| v1 | forced-aligner 候选窗打分 | 部分修对但 50 段误 kept；**forced aligner 会把任意文本铺到任意语音上，错文本对错音频同样高分，不能做内容验证** |
| v2 | 不健康段合并大簇窗 ASR + 游标匹配 + 单调 revert | 大窗内匹配漂移、revert 连锁撤销 40+ 已验证修复；**必须逐段紧窗；内容验证过的落位不做 revert 只做钳位** |
| v3（现行） | 健康冻结 + 逐段候选窗批量 ASR + difflib 内容验证落位 | 01_part1 全部 18 个真值锚点命中，词落岛外 67→15，幂等 |

**为什么旧"词→岛全局 DP 分配"（02cf087）必须废弃**：它用均匀语速预算全量重排、
ASR 词时间只作 0.05×rate 轻先验——语速离群段（快喊话/慢旁白）被预算模型系统性
挪到错误的岛组。01_part1 实测：`Bryce, isn't it time...`（真实在 69.3–71.95，
快喊话、局部速率≈全局 2 倍）整簇被推迟 4–7s 钉到 75.05–78.99；全片 26 个语音岛
（47.4s，16% 语音宽）无人认领；插值兜底把错位"焊死"成均匀词时长，一切局部
判据（词时长>0.01s 之类）全部漏检。BGM 残留岛还虚增语速分母放大错位。
用户质疑"整簇推迟合理吗？不会打乱模型准确时间吗"——正确，这正是缺陷本身。

**v3 流程**：

```
健康分类与冻结 → 待探测集（不健康 ∪ 零间隙链 ∪ 词级插值签名）
→ 逐段候选窗（自身±0.8s ∪ 无人认领单元组±0.5s ∪ 邻近探测段自身窗
   ∪ 相邻探测段桥接窗）全局去重 → 批量 ASR（return_time_stamps=True）
→ difflib 词块内容验证（cov≥0.5、锚点间隙≤3s、跨度速率合理）
→ 达标段按探针词时间落位（未匹配词锚点间小步插值，首尾向窗内延展≤1.2s）
→ 段边界从词重建 → 起点静音吸附（只前移）→ 单调性钳位（不回退）→ 重叠钳位
```

要点：

- **健康即冻结**：词中点全在语音单元内 + 词时长正常 + 速率 ∈ [RATE_LO,
  RATE_HI] + 语音占比达标的段一律不动。ASR 本来就对的段绝不被重排推翻，
  重跑天然幂等（01_part1 修复后健康段 77→102）。
- **探针时间戳是窗口相对的**：批量 ASR 返回的词时间必须加窗口起点偏移
  （`probe_sync_truth.py` 同款约定）。
- **内容验证是核心原语**（P0 探针 18/18 验证）：紧窗 ASR 重转写天然回答
  "这段音频到底说的是不是这句话"，forced aligner 做不到。
- **候选窗四类来源缺一不可**（01_part1 各有命中案例）：自身窗（验证"原位
  即对"）；无人认领单元组（错位段的主要去处，0.12s 小岛也要收——"Huh?"
  只有 0.15s）；邻近探测段自身窗（真位置可能被其它不健康段的词占着，
  形不成无人认领组）；相邻探测段桥接窗（RMS 阈值漏检的轻声旁白区无任何
  单元，seg106 真值 340.88–345.36 就在这种区域，自身窗够不着中间）。
- **单调性只钳位不回退**：倒挂时只挪低信任方（健康冻结 > 内容验证 cov >
  未匹配保留）的段标签，内容验证过的落位绝不被撤销。
- **对不上的段保留现状**：如缓存文本与实际语音不符（01_part1 seg123 文本
  "Oh, Bryce, let's speak with him." vs 实际 "Can I speak with you?"），
  这是 ASR 转写错误，不是时间错位，重排无意义。

**性能**：GPU（RTX 4090）上 8 分钟音频全量修复（含 ~170 窗批量 ASR）约 1 分钟；
健康段多的缓存只探测少数段，接近零开销。

**日志治理**：一行 INFO 汇总
`Sync repair: N segs (H healthy-frozen), P probed in W windows, R re-anchored,
K unmatched-kept, S snapped, unclaimed_units=U`；拒绝细节降 DEBUG。

**带通 A/B 结论**（P0 探针，`probe_sync_truth.py`）：demucs 后带通无增益——
电话频段（450–3100Hz）丢词（"I go"/"her"/"A" 掉岛外），温和语音频段
（80–5500Hz）与 raw 持平。默认关闭（`SYNC_REPAIR_BANDPASS=false`），
特殊素材可开。

### C. 引号感知断句（`punct_segmentation.py`）

单遍引号深度游走（`_scan_quote_depth`），按当前深度决定句末标点行为：

- 句末标点在**深度 0**（引号外）→ 正常硬切
- 句末标点在**引号内但同标点串随后闭合**（如 `?"`）→ 硬切且引号对完整收尾：
  `I asked, "Is everything okay?"` 不再被拆开
- 引语内句末标点（引号未闭合）→ 不切，记 `soft` 候选，供超长引语二次切分
  （切点优先级：soft 候选 → 子句标点 → 最大词间隙；超长引语允许拆开引号对）
- 段末**深度 0 处的开引号/开括号**仍移到下一段开头（保留 `He said. "Go...` 的正确
  行为）；**闭引号永不移动**
- 直引号 `"` `'` 开闭同形，按深度二义判定（深度 0 视为开，否则视为闭）
- 未闭合保护：引号持续张开超 300 字符或 30s → 强制归零深度并告警
  （ASR 偶发丢闭引号时后续句子仍能正常切分）

`attach_punctuation` / `render_segment_text` / `segment_subtitles` 契约不变；
desync → None → 调用方回退旧逻辑的契约不变。

## 配置与回滚

`SYNC_REPAIR_*` 参数**可在前端设置页（"字幕质量"选项卡）运行时调整**，
持久化于 `backend/sync_repair_config.json`（`GET/PUT/POST /api/sync-repair/config`，
热生效）；下表 env 变量仅在 JSON 首次生成前作种子值。修改参数保存后前端会自动
对当前视频调 `POST /api/transcription/repair/{file_id}` 轻量重修复（只重排
时间戳，不重跑 demucs/ASR）；CLI 批量重修复用 `repair_cache.py`。

`app/config.py`（env 种子值，均可环境变量覆盖）：

| 配置 | 默认 | 说明 |
|---|---|---|
| `SUBTITLE_SYNC_REPAIR` | `true` | 修复通道总开关，**设 false 即回滚到现状行为**（设置页同名"启用时间戳修复"） |
| `SYNC_REPAIR_MAX_WORD_DUR` | `1.5` | 单词时长超过此值视为不健康，触发重探测（秒） |
| `SYNC_REPAIR_SPEECH_RATIO` | `0.35` | 段区间语音帧占比低于此值视为不健康，触发重探测 |
| `SYNC_REPAIR_SNAP_WINDOW` | `0.7` | 起点静音吸附最大前移（秒） |
| `SYNC_REPAIR_RATE_LO` | `4` | chars/s 下限，低于视为拖沓/铺静音 |
| `SYNC_REPAIR_RATE_HI` | `34` | chars/s 上限，高于视为挤扁/错位（接受窗放宽到 +8） |
| `SYNC_REPAIR_SEARCH_S` | `12` | 候选窗搜索半径（秒） |
| `SYNC_REPAIR_MERGE_GAP` | `1.2` | 无人认领单元合并成候选组的最大桥接间隔（秒） |
| `SYNC_REPAIR_MIN_ISLAND_W` | `0.12` | 参与候选的最小单元宽（秒，短感叹词岛 ~0.15s） |
| `SYNC_REPAIR_BANDPASS` | `false` | demucs 后修复通道内可选带通（探针 A/B 无增益，默认关） |
| `SYNC_REPAIR_BANDPASS_LO/HI` | `80/5500` | 带通频段（Hz） |

跨字段不变量（`rate_lo < rate_hi`、`bandpass_lo < bandpass_hi`）由配置管理器
校验（部分更新时 pydantic 看不到合并后状态），违反返回 400。

注意：旧缓存（`cache/`）的时间戳已固化在 transcription.json 里，需在前端
**强制刷新**（`POST /api/transcription/generate` + `force_refresh=true`）
重新生成才能享受修复。

## 测试与验证

离线测试（不依赖 8000 服务；conda python 直调，见根目录记忆/开发环境约定）：

```bash
# 引号断句（纯 CPU，秒级）
/c/Users/Sugar/.conda/envs/qwen3-asr/python.exe D:/ASR_Server/backend/test_punct_segmentation.py

# 同步修复验收（加载 Qwen3-ASR；GPU 数十秒，CPU 约 5-10 分钟）
/c/Users/Sugar/.conda/envs/qwen3-asr/python.exe D:/ASR_Server/backend/test_sync_repair.py
```

`test_punct_segmentation.py` 用例：闭引号整段成对、直引号不移动、中文弯引号/书名号、
未闭合保护、长引语 soft 拆分、缓存 7（`7_32554575`）真实回归、desync/空输入。

`test_sync_repair.py` 断言（02_part2_130405428，含用户实测回归）：

| 断言 | 说明 |
|---|---|
| `... just visually challenged.`（`I feel sorry for you.` 的前一段）start ≥18.3 | off-by-one 回归：不再错位到上一句尾音岛 [17.05,18.1]（实测 15.59→19.04） |
| `I feel sorry for you.` end ≤23.0 且在 challenged 之后 | 两句落在真实语音岛 [≈18.55, 22.75] 内 |
| `Nothing.` / `Oh, okay.` / `My mistake.` 各 ≥80% 在单一语音岛内且有序 | 3 岛 4 句存在两种自洽布局，断言结构性质而非具体位置 |
| 幂等性：目标段重跑漂移 ≤0.5s | 缓存已是修复产物，重跑应近似恒等 |
| 段数/文本不变、start 单调、无重叠 | 不变量 |
| `1_33779614` 同跑 | `language='auto'` 路径回归 |

01_part1_133682968（v3 复盘主缓存）：18 个真值锚点段（探针
`probe_sync_truth.py` 18/18 + 定点复验，真值同步在 `cache/<name>/sync_truth.json`），
修复前与重跑后都必须在真值区间 ±0.6/0.8s 内、重跑漂移 ≤0.6s。
含用户报告簇（1:15 "Bryce..."→69.3、1:16 "Huh?"→72.68、"Oh yeah."→75.05、
1:17 "I mean..."→76.8、1:22 "I was about..."→80.05、1:51 "Finally..."→100.7）
与散段（seg4/5/77/85/103/115/116/121/123/139）。seg123 文本与实际语音不符
（"Oh, Bryce, let's speak with him." vs 实际 "Can I speak with you?"），
断言用锚点区间 [408.7,412.6]。

注意：ASR 转写文本每次运行有细微差异（如该句在两次运行中分别转写为
"They're/You're just visually challenged"，某次 "Three blocks away" 整句未出现），
测试用相对定位与结构断言，不依赖具体句子文本。

旧缓存升级：修复管线升级后可用 `backend/repair_cache.py` 对现有缓存重跑修复并
回写（无需完整重新生成 demucs + ASR）；首次修复会落盘
`transcription.presnap.json`（修复前快照，重跑不覆盖），便于事后区分
"ASR 本来就错"还是"修复推翻了正确时间"：

```bash
/c/Users/Sugar/.conda/envs/qwen3-asr/python.exe D:/ASR_Server/backend/repair_cache.py [cache_dir ...]
# 无参数 = 处理 cache/ 下全部缓存
```

端到端验证：后端改动由 8000 常驻服务热加载（uvicorn reload）；
前端强制刷新重新生成缓存后，点击字幕应立即朗读对应句子；日志只有一行
`Sync repair: ...` 汇总（不再有 reject 刷屏）。

## 已知限制

- **幂等有界抖动**：落位在 RMS 阈值漏检区（轻声旁白）的段永远过不了健康
  检查（词不在单元内），每次重跑都会重探测；窗口边界变化导致 ASR 掉/多一个
  边界词时，首尾插值有 ~1s 级抖动（围绕真值振荡，不累积）。01_part1 实测
  16/148 段有 ≤1s 变化，18 个真值锚点段全部稳定（漂移 ≤0.6s）。
- 内容验证靠 ASR 听力：demucs 人声残留 BGM 重、含哼唱/童谣（如 139.55–142.6
  "K-I-S-S-I-N-G"）的区域 cov 不达标 → 保留现状，表现为"该处音频无对应
  字幕行"，不会产生指向错误音频的点击。
- 缓存文本与实际语音不符的段（ASR 转写错误）保留现状，其中被邻居正确落位
  挤压的段标签可能收窄（如 seg123 显示 0.2s）——文本本身就是错的，
  强制刷新重新转写才能根治。
- 直引号二义判定对连续同向直引号（`""Go`）会判错方向，属 ASR 罕见输出，
  由未闭合保护兜底。
- `SYNC_REPAIR_*` 阈值按英语电影语速标定；中文素材如出现误修，优先调
  `SYNC_REPAIR_SPEECH_RATIO`（调高 → 更多段被判健康、跳过重探测）。
