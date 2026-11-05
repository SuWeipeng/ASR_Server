# 字幕同步修复 + 引号感知断句

本文档记录 2026-11 这轮字幕质量修复的设计、机制与验证方法。
涉及两条独立流水线：**退化段时间戳修复**（对齐漂移/钉死）与**引号感知断句**（引号对被拆开）。

## 问题与根因

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

### B. 全局再对齐通道（`subtitle_service._refine_segment_timing`）

主修复。**2026-11-06 起为"词→岛全局 DP 分配"机制**（初版的退化判据+岛归属游标+
分层验收只能修"判据命中的段"，无法发现自洽错位，已整体替换）。流程：

```
语音岛检测 → 宽岛切分（≤10s 虚拟单元）→ 词→单元全局 DP 分配
→ 分组联合重对齐（段被拆到多单元时合并窗口）→ 拆段 A/B 裁决
→ 验收失败的单元内插值 → 段边界从词重建 → 起点静音吸附
→ 单调性定点迭代兜底 → 相邻段重叠钳位
```

**为什么必须全局分配**：压缩数据的词与错误岛时间可以完美吻合（自洽错位），
漂移先验在局部是误导；均匀语速预算在欠填区不可分（两个都欠填的单元之间
怎么分文本总代价不变）。因此以"预算 + 全局顺序约束"为主体、漂移时间只作
轻先验（`W_TIME = 0.05 × rate`），让全局最优解而不是局部信号做裁决。

**DP 分配**：`f(i, j)` = 前 i 个词分给前 j 个单元的最小代价，
`cost(k..i → 单元 j) = |单元宽×rate − 词字符数| + W_TIME × Σ词漂移中点到单元距离`。
语速 `rate = 全部词字符数 / 全部单元宽度`（全局自校准，语言/语速自适应）。
允许空单元（代价 = 其预算，自然平衡"文本多而岛少"与"岛多而文本少"）。
复杂度 O(词数×单元数)：cost 绝对值项按字符前缀和分裂成两个 running-min，
前缀最小值 + 单调队列维护，几秒内完成 5000 词 × 200 单元。

**分组联合重对齐**：段被 DP 拆到多个单元时（均匀语速在局部密度突变处的噪声），
把这些单元合并为一组——合并窗口内 aligner 的顺序匹配能自己找到正确落点。
验收 = 词数一致 + 时长词达标（≤8 词要求几乎全有时长，否则 2/3）；
失败 → 单元范围内按字符数加权插值（单元即归属，插值安全）。
健康组跳过（词本就在范围内、无零/超长词、语音占比正常）——已对齐的素材
几乎零开销。

**拆段 A/B 裁决**：off-by-one 错位的典型残留是段的头部词被预算拉去填前一岛
的坑（如 `They're just visually challenged.` 的头两个词被分进上一句的尾音岛）。
对每个被拆的段做对照实验：A=保持现状，B=把头部词移入最后一个单元所在组
重新对齐；用「段内词间隙 + 时长/字符离散度 + 窗口内岛语音未被词覆盖量」
打分，B 明显更优才采纳（LIS 平滑会抹平间隙，离散度项兜底）。

**保留的兜底**：修复前快照；起点静音吸附（只前移）；单调性定点迭代
（回退倒挂段至不动点）；相邻段重叠 >0.05s 钳位。DP 输出本应单调，
这些是安全网。

**日志治理**：只输出一行 INFO 汇总
`Sync repair: N units, X realigned, Y interpolated, Z healthy-skipped, S snapped`；
拒绝/回退细节降为 DEBUG。

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

`app/config.py`（均可环境变量覆盖）：

| 配置 | 默认 | 说明 |
|---|---|---|
| `SUBTITLE_SYNC_REPAIR` | `true` | 修复通道总开关，**设 false 即回滚到现状行为** |
| `SYNC_REPAIR_MAX_WORD_DUR` | `1.5` | 单词时长超过此值视为不健康，触发重对齐（秒） |
| `SYNC_REPAIR_SPEECH_RATIO` | `0.35` | 单元/组语音帧占比低于此值视为不健康，触发重对齐 |
| `SYNC_REPAIR_SNAP_WINDOW` | `0.7` | 起点静音吸附最大前移（秒） |

注意：旧缓存（`cache/`）的时间戳已固化在 transcription.json 里，需在前端
**强制刷新**（`POST /api/transcription/generate` + `force_refresh=true`）
重新生成才能享受修复。

## 测试与验证

离线测试（不依赖 8000 服务；conda python 直调，见根目录记忆/开发环境约定）：

```bash
# 引号断句（纯 CPU，秒级）
/c/Users/Sugar/.conda/envs/qwen3-asr/python.exe D:/ASR_Server/backend/test_punct_segmentation.py

# 同步修复验收（加载 ForcedAligner，CPU 约 1-2 分钟）
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

注意：ASR 转写文本每次运行有细微差异（如该句在两次运行中分别转写为
"They're/You're just visually challenged"，某次 "Three blocks away" 整句未出现），
测试用相对定位与结构断言，不依赖具体句子文本。

旧缓存升级：修复管线升级后可用 `backend/repair_cache.py` 对现有缓存重跑修复并
回写（无需完整重新生成 demucs + ASR）：

```bash
/c/Users/Sugar/.conda/envs/qwen3-asr/python.exe D:/ASR_Server/backend/repair_cache.py [cache_dir ...]
```

端到端验证：后端改动由 8000 常驻服务热加载（uvicorn reload）；
前端强制刷新重新生成缓存后，点击字幕应立即朗读对应句子；日志只有一行
`Sync repair: ...` 汇总（不再有 reject 刷屏）。

## 已知限制

- 均匀语速预算在"文本量与语音量严重不匹配"的区域（说话极慢/极快的对白）
  仍可能把段边界分错 ±1 词；拆段 A/B 裁决能修正其中结构性信号最明显的部分。
  残余的语音岛无字幕覆盖（ASR 漏听/文本被压缩吃掉）表现为"该处音频无对应
  字幕行"，不会产生指向错误音频的点击。
- 验收失败的单元按字符加权插值，插值词时长均匀但与真实发音位置可能有
  ±0.5s 级偏差（仍远优于压缩错位）。
- 直引号二义判定对连续同向直引号（`""Go`）会判错方向，属 ASR 罕见输出，
  由未闭合保护兜底。
- `SYNC_REPAIR_*` 阈值按英语电影语速标定；中文素材如出现误修，优先调
  `SYNC_REPAIR_SPEECH_RATIO`（调高 → 更多单元被判健康、跳过重对齐）。
