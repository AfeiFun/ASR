#!/usr/bin/env python3
"""
ASR MCP服务器 V2 - 优化版本
基于Model Context Protocol (MCP)的视频转文字服务
支持从URL下载视频并进行语音识别转录
"""

import os
import tempfile
import json
import sys
from pathlib import Path
from typing import Dict, Any

from fastmcp import FastMCP

# 导入本地模块
from video_downloader import VideoDownloader
from asr_transcriber import ASRTranscriber
from video_processor import extract_audio_from_video, get_supported_video_formats

# 创建FastMCP应用
mcp = FastMCP("ASR Transcriber")

# 全局变量
video_downloader = None
asr_transcriber = None

def initialize_services():
    """初始化服务"""
    global video_downloader, asr_transcriber
    
    try:
        # 初始化视频下载器
        video_downloader = VideoDownloader()
        print("✅ 视频下载器初始化成功", file=sys.stderr)
        
        # 初始化ASR转录器（默认配置）
        asr_transcriber = ASRTranscriber()
        print("✅ ASR转录器初始化成功", file=sys.stderr)
        
    except Exception as e:
        print(f"❌ 服务初始化失败: {str(e)}", file=sys.stderr)
        raise

@mcp.tool()
def transcribe_from_url(
    url: str,
    output_format: str = "text",
    language: str = "auto"
) -> str:
    """
    从视频URL下载并转录
    
    Args:
        url: 视频URL（支持YouTube、Bilibili等平台）
        output_format: 输出格式（text/srt/vtt/json）
        language: 语言代码（auto/zh/en/ja/ko等）
    
    Returns:
        转录结果
    """
    try:
        global video_downloader, asr_transcriber
        
        # 验证URL
        if not video_downloader.is_supported_url(url):
            return f"❌ 不支持的URL或URL无效: {url}"
        
        # 获取视频信息
        try:
            video_info = video_downloader.get_video_info(url)
            print(f"📹 视频信息: {video_info['title']} (时长: {video_info['duration']}秒)", file=sys.stderr)
        except Exception as e:
            return f"❌ 获取视频信息失败: {str(e)}"
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="mcp_asr_")
        
        try:
            # 下载音频（直接下载音频格式更高效）
            print("🔽 开始下载音频...", file=sys.stderr)
            audio_file = video_downloader.download_audio_only(url, temp_dir)
            
            # 重新初始化ASR转录器（使用默认VAD设置）
            transcriber = ASRTranscriber(enable_vad=True)
            
            # 转录音频
            print("🎤 开始转录...", file=sys.stderr)
            result = transcriber.transcribe_audio(
                audio_path=audio_file,
                language=language,
                max_length=5,  # 默认5秒分段
                batch_size=600  # 默认批处理大小
            )
            
            # 格式化输出
            output = format_transcription_output(result, output_format, video_info)
            
            return f"✅ 转录完成！\n\n📹 视频: {video_info['title']}\n⏱️ 时长: {video_info['duration']}秒\n🎯 格式: {output_format}\n\n{output}"
            
        finally:
            # 清理临时文件
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        return f"❌ 转录失败: {str(e)}"

@mcp.tool()
def transcribe_local_file(
    file_path: str,
    output_format: str = "text",
    language: str = "auto"
) -> str:
    """
    转录本地视频/音频文件
    
    Args:
        file_path: 本地文件路径
        output_format: 输出格式（text/srt/vtt/json）
        language: 语言代码（auto/zh/en/ja/ko等）
    
    Returns:
        转录结果
    """
    try:
        global asr_transcriber
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            return f"❌ 文件不存在: {file_path}"
        
        # 检查文件类型
        file_ext = file_path.suffix.lower()
        audio_exts = ['.wav', '.mp3', '.flac', '.m4a', '.aac']
        video_exts = get_supported_video_formats()
        
        temp_dir = tempfile.mkdtemp(prefix="mcp_asr_local_")
        
        try:
            if file_ext in audio_exts:
                # 直接处理音频文件
                audio_file = str(file_path)
            elif file_ext in video_exts:
                # 从视频提取音频
                print("🎬 从视频提取音频...", file=sys.stderr)
                audio_file = extract_audio_from_video(
                    str(file_path),
                    os.path.join(temp_dir, "extracted_audio.wav")
                )
            else:
                return f"❌ 不支持的文件格式: {file_ext}"
            
            # 重新初始化ASR转录器（使用默认VAD设置）
            transcriber = ASRTranscriber(enable_vad=True)
            
            # 转录音频
            print("🎤 开始转录...", file=sys.stderr)
            result = transcriber.transcribe_audio(
                audio_path=audio_file,
                language=language,
                max_length=5,  # 默认5秒分段
                batch_size=600  # 默认批处理大小
            )
            
            # 格式化输出
            file_info = {"title": file_path.stem, "duration": 0}
            output = format_transcription_output(result, output_format, file_info)
            
            return f"✅ 转录完成！\n\n📁 文件: {file_path.name}\n🎯 格式: {output_format}\n\n{output}"
            
        finally:
            # 清理临时文件
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        return f"❌ 转录失败: {str(e)}"

@mcp.tool()
def get_video_info(url: str) -> str:
    """
    获取视频信息
    
    Args:
        url: 视频URL
    
    Returns:
        视频信息（JSON格式）
    """
    try:
        global video_downloader
        
        if not video_downloader.is_supported_url(url):
            return f"❌ 不支持的URL或URL无效: {url}"
        
        info = video_downloader.get_video_info(url)
        
        # 格式化显示
        formatted_info = f"""
📹 **视频信息**

**标题**: {info['title']}
**时长**: {info['duration']}秒 ({info['duration']//60}分{info['duration']%60}秒)
**上传者**: {info['uploader']}
**上传日期**: {info['upload_date']}
**观看次数**: {info['view_count']:,} 次
**可用格式数**: {info['formats_available']} 个
**网页链接**: {info['webpage_url']}

**描述**: {info['description']}
"""
        
        return formatted_info
        
    except Exception as e:
        return f"❌ 获取视频信息失败: {str(e)}"

@mcp.tool()
def list_supported_languages() -> str:
    """
    列出支持的语言
    
    Returns:
        支持的语言列表
    """
    languages = {
        "auto": "自动检测",
        "zh": "中文",
        "en": "英文",
        "ja": "日语",
        "ko": "韩语",
        "es": "西班牙语",
        "fr": "法语",
        "de": "德语",
        "ru": "俄语"
    }
    
    result = "🌍 **支持的语言**:\n\n"
    for code, name in languages.items():
        result += f"• `{code}`: {name}\n"
    
    result += "\n**使用方法**: 在转录时设置 `language` 参数，例如 `language='zh'` 表示中文"
    
    return result

@mcp.tool()
def list_supported_platforms() -> str:
    """
    列出支持的视频平台
    
    Returns:
        支持的平台列表
    """
    try:
        global video_downloader
        sites = video_downloader.get_supported_sites()
        
        result = "🌐 **支持的主要视频平台**:\n\n"
        for site in sites[:15]:  # 显示前15个
            result += f"• {site}\n"
        
        result += f"\n还支持更多平台... (共支持 {len(sites)}+ 个平台)"
        result += "\n\n**使用方法**: 直接提供视频URL即可，系统会自动识别平台"
        
        return result
        
    except Exception as e:
        return f"❌ 获取支持平台列表失败: {str(e)}"

@mcp.tool()  
def get_output_formats() -> str:
    """
    获取支持的输出格式说明
    
    Returns:
        输出格式说明
    """
    formats = {
        "text": "纯文本格式，只包含转录的文字内容",
        "srt": "SRT字幕格式，包含时间戳和文本，适合视频字幕",
        "vtt": "WebVTT格式，Web标准字幕格式",
        "json": "JSON结构化格式，包含详细的时间戳和元数据"
    }
    
    result = "📄 **支持的输出格式**:\n\n"
    for format_type, description in formats.items():
        result += f"• **{format_type}**: {description}\n"
    
    result += "\n**使用方法**: 在转录时设置 `output_format` 参数，例如 `output_format='srt'`"
    
    return result

def format_transcription_output(result: Dict[str, Any], output_format: str, video_info: Dict[str, Any]) -> str:
    """
    格式化转录输出
    
    Args:
        result: ASR转录结果
        output_format: 输出格式
        video_info: 视频信息
        
    Returns:
        格式化后的输出
    """
    try:
        if output_format == "text":
            return result.get("text", "")
        
        elif output_format == "json":
            return json.dumps({
                "video_info": video_info,
                "transcription": result
            }, ensure_ascii=False, indent=2)
        
        elif output_format == "srt":
            segments = result.get("segments", [])
            srt_content = ""
            
            for i, segment in enumerate(segments, 1):
                start_time = format_srt_time(segment["start"])
                end_time = format_srt_time(segment["end"])
                text = segment["text"].strip()
                
                srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
            
            return srt_content
        
        elif output_format == "vtt":
            segments = result.get("segments", [])
            vtt_content = "WEBVTT\n\n"
            
            for segment in segments:
                start_time = format_vtt_time(segment["start"])
                end_time = format_vtt_time(segment["end"])
                text = segment["text"].strip()
                
                vtt_content += f"{start_time} --> {end_time}\n{text}\n\n"
            
            return vtt_content
        
        else:
            return f"不支持的输出格式: {output_format}"
            
    except Exception as e:
        return f"格式化输出失败: {str(e)}"

def format_srt_time(seconds: float) -> str:
    """格式化SRT时间格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')

def format_vtt_time(seconds: float) -> str:
    """格式化VTT时间格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

def main():
    """主函数"""
    try:
        # 初始化服务
        initialize_services()
        
        # 运行MCP服务器
        mcp.run()
        
    except KeyboardInterrupt:
        print("\n👋 服务器已停止", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"❌ 服务器运行失败: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()