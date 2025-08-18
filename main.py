#!/usr/bin/env python3
"""
视频转文字应用
基于FunASR实现本地视频文件的语音识别转录
"""

import os
import sys
import argparse
import tempfile
from pathlib import Path

from video_processor import (
    extract_audio_from_video, 
    validate_video_file, 
    validate_audio_file,
    get_supported_video_formats
)
from asr_transcriber import ASRTranscriber

def print_banner():
    """打印应用横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    视频转文字工具                            ║
    ║                 基于FunASR语音识别                           ║
    ║                                                              ║
    ║  支持格式: MP4, AVI, MKV, MOV, WMV, FLV, WEBM, M4V          ║
    ║  输出格式: TXT, SRT, VTT, JSON                               ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def setup_argparse():
    """设置命令行参数解析"""
    parser = argparse.ArgumentParser(
        description="视频转文字工具 - 基于FunASR语音识别",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py input.mp4                           # 基础转录，输出文本
  python main.py input.mp4 -o output.txt             # 指定输出文件
  python main.py input.mp4 -f srt -l zh              # 输出SRT字幕，指定中文
  python main.py input.mp4 -f json --timestamps      # 输出JSON格式，包含时间戳
  python main.py input.mp4 --model paraformer-zh     # 使用指定模型
        """
    )
    
    parser.add_argument(
        "input",
        help="输入视频文件路径"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出文件路径（可选，默认根据输入文件名生成）"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["text", "srt", "vtt", "json"],
        default="text",
        help="输出格式 (默认: text)"
    )
    
    parser.add_argument(
        "-l", "--language",
        default="auto",
        help="语言代码 (默认: auto，支持: zh, en, ja, ko, es, fr, de, it, pt, ru)"
    )
    
    parser.add_argument(
        "--model",
        default="iic/SenseVoiceSmall",
        help="ASR模型名称 (默认: iic/SenseVoiceSmall)"
    )
    
    parser.add_argument(
        "--vad-model",
        default="fsmn-vad",
        help="VAD模型名称 (默认: fsmn-vad)"
    )
    
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "mps", "auto"],
        default="auto",
        help="计算设备 (默认: auto，自动检测最佳设备)"
    )
    
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="输出包含时间戳信息"
    )
    
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="保留提取的音频文件"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细信息"
    )
    
    parser.add_argument(
        "--max-length",
        type=int,
        default=30,
        help="VAD片段合并最大长度(秒)，用于控制字幕片段长度 (默认: 30秒)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="批处理大小，GPU加速时可适当增大 (默认: 8)"
    )
    
    return parser

def generate_output_path(input_path, output_format):
    """生成输出文件路径"""
    input_path = Path(input_path)
    base_name = input_path.stem
    
    format_extensions = {
        "text": ".txt",
        "srt": ".srt",
        "vtt": ".vtt",
        "json": ".json"
    }
    
    extension = format_extensions.get(output_format, ".txt")
    return str(input_path.parent / f"{base_name}_transcription{extension}")

def main():
    """主函数"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    print_banner()
    
    # 验证输入文件
    if args.verbose:
        print(f"验证输入文件: {args.input}")
    
    video_validation = validate_video_file(args.input)
    if not video_validation["valid"]:
        print(f"❌ 输入文件验证失败: {video_validation['error']}")
        return 1
    
    if args.verbose:
        print("✅ 视频文件验证通过")
        print(f"   时长: {video_validation['duration']:.2f}秒")
        print(f"   分辨率: {video_validation['size']}")
        print(f"   帧率: {video_validation['fps']:.2f}fps")
    
    # 提取音频
    temp_audio_path = None
    try:
        print("🎵 正在从视频中提取音频...")
        temp_audio_path = extract_audio_from_video(args.input)
        
        # 验证音频文件
        audio_validation = validate_audio_file(temp_audio_path)
        if not audio_validation["valid"]:
            print(f"❌ 音频提取失败: {audio_validation['error']}")
            return 1
        
        if args.verbose:
            print("✅ 音频提取完成")
            print(f"   时长: {audio_validation['duration']:.2f}秒")
            print(f"   采样率: {audio_validation['sample_rate']}Hz")
            print(f"   声道数: {audio_validation['channels']}")
        
        # 初始化ASR转录器
        print("🤖 正在初始化语音识别模型...")
        transcriber = ASRTranscriber(
            model_name=args.model,
            vad_model=args.vad_model,
            device=args.device
        )
        
        # 执行转录
        print("📝 正在进行语音识别转录...")
        if args.timestamps:
            result = transcriber.transcribe_with_timestamps(
                temp_audio_path, 
                args.language,
                max_length=args.max_length,
                batch_size=args.batch_size
            )
        else:
            result = transcriber.transcribe_audio(
                temp_audio_path, 
                args.language, 
                max_length=args.max_length,
                batch_size=args.batch_size
            )
        
        if not result["success"]:
            print(f"❌ 转录失败: {result['error']}")
            return 1
        
        # 格式化输出
        formatted_output = transcriber.format_transcription_output(result, args.format)
        
        # 确定输出路径
        if args.output:
            output_path = args.output
        else:
            output_path = generate_output_path(args.input, args.format)
        
        # 保存结果
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:  # 只有当输出路径包含目录时才创建
                os.makedirs(output_dir, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            
            print(f"✅ 转录完成！")
            print(f"📄 输出文件: {output_path}")
            
            if args.verbose:
                print(f"   语言: {result.get('language', '未知')}")
                print(f"   文本长度: {len(result['text'])}字符")
                if 'segments' in result:
                    print(f"   分段数: {len(result['segments'])}")
            
            # 显示部分转录内容
            preview_text = result['text'][:200]
            if len(result['text']) > 200:
                preview_text += "..."
            print(f"\n📝 转录预览:\n{preview_text}")
            
        except Exception as e:
            print(f"❌ 保存输出文件失败: {str(e)}")
            return 1
            
    except Exception as e:
        print(f"❌ 处理过程中发生错误: {str(e)}")
        return 1
        
    finally:
        # 清理临时文件
        if temp_audio_path and os.path.exists(temp_audio_path):
            if args.keep_audio:
                audio_output_path = generate_output_path(args.input, "wav").replace(".txt", ".wav")
                os.rename(temp_audio_path, audio_output_path)
                if args.verbose:
                    print(f"🎵 音频文件已保存: {audio_output_path}")
            else:
                os.unlink(temp_audio_path)
                if args.verbose:
                    print("🗑️  临时音频文件已清理")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 程序异常退出: {str(e)}")
        sys.exit(1)