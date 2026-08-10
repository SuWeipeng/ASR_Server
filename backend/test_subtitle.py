"""
测试字幕生成功能
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.subtitle_service import subtitle_service
from app.services.media_service import media_service
from app.utils import logger

def test_subtitle_generation():
    """测试字幕生成"""

    # 测试文件路径
    test_file = r"D:\ASR_Server\1.mp4"

    print("=" * 60)
    print("测试字幕生成功能")
    print("=" * 60)
    print(f"测试文件: {test_file}")
    print(f"文件存在: {os.path.exists(test_file)}")
    print()

    try:
        # Step 1: 上传文件
        print("[1/3] 上传文件...")
        import uuid
        file_id = str(uuid.uuid4())

        # 模拟文件上传（直接复制文件）
        import shutil
        upload_dir = r"D:\ASR_Server\uploads"
        os.makedirs(upload_dir, exist_ok=True)

        uploaded_path = os.path.join(upload_dir, f"{file_id}.mp4")
        shutil.copy(test_file, uploaded_path)

        # 创建文件记录
        media_service._files[file_id] = {
            "file_id": file_id,
            "filename": "1.mp4",
            "file_type": "video/mp4",
            "file_path": uploaded_path,
            "file_size": os.path.getsize(uploaded_path),
            "duration": 0.0,
            "upload_time": None
        }

        print(f"✅ 文件已上传: {file_id}")
        print()

        # Step 2: 提取音频
        print("[2/3] 提取音频...")
        audio_path = media_service.extract_audio_from_media(file_id)
        print(f"✅ 音频已提取: {audio_path}")
        print()

        # Step 3: 生成字幕
        print("[3/3] 生成字幕...")
        print("（首次运行会加载模型，可能需要1-2分钟）")
        print("请耐心等待...")

        result = subtitle_service.generate_subtitles(
            file_id=file_id,
            language="English",
            use_alignment=True
        )

        if result:
            print()
            print("=" * 60)
            print("✅ 字幕生成成功！")
            print("=" * 60)
            print(f"文件ID: {result.file_id}")
            print(f"语言: {result.language}")
            print(f"时长: {result.duration:.2f}秒")
            print(f"处理时间: {result.processing_time:.2f}秒")
            print(f"字幕段数: {len(result.segments)}")
            print()
            print("字幕预览:")
            print("-" * 60)
            for i, segment in enumerate(result.segments[:5]):  # 只显示前5段
                print(f"[{i}] {segment.start:.2f}s - {segment.end:.2f}s")
                print(f"    {segment.text}")
                print()

            if len(result.segments) > 5:
                print(f"... 还有 {len(result.segments) - 5} 段字幕")

            print()
            print("完整文本:")
            print("-" * 60)
            print(result.full_text[:500])
            if len(result.full_text) > 500:
                print("...")
            print()

        else:
            print("❌ 字幕生成失败")
            return False

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_subtitle_generation()
    sys.exit(0 if success else 1)
