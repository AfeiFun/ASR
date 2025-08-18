import os
import tempfile
from moviepy import VideoFileClip
import soundfile as sf

def extract_audio_from_video(video_path, output_audio_path=None):
    """
    从视频文件中提取音频
    
    Args:
        video_path (str): 视频文件路径
        output_audio_path (str, optional): 输出音频文件路径，如果不提供则使用临时文件
    
    Returns:
        str: 音频文件路径
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    
    if output_audio_path is None:
        # 创建临时音频文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            output_audio_path = tmp_file.name
    
    try:
        # 加载视频文件
        video = VideoFileClip(video_path)
        
        # 提取音频
        audio = video.audio
        
        # 保存音频文件
        audio.write_audiofile(output_audio_path, logger=None)
        
        # 关闭资源
        audio.close()
        video.close()
        
        return output_audio_path
        
    except Exception as e:
        raise Exception(f"提取音频失败: {str(e)}")

def validate_audio_file(audio_path):
    """
    验证音频文件是否有效
    
    Args:
        audio_path (str): 音频文件路径
    
    Returns:
        dict: 音频文件信息
    """
    try:
        data, samplerate = sf.read(audio_path)
        duration = len(data) / samplerate
        
        return {
            "valid": True,
            "duration": duration,
            "sample_rate": samplerate,
            "channels": data.shape[1] if len(data.shape) > 1 else 1,
            "samples": len(data)
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

def get_supported_video_formats():
    """
    获取支持的视频格式列表
    
    Returns:
        list: 支持的视频格式扩展名
    """
    return ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']

def validate_video_file(video_path):
    """
    验证视频文件是否有效且支持
    
    Args:
        video_path (str): 视频文件路径
    
    Returns:
        dict: 验证结果
    """
    if not os.path.exists(video_path):
        return {"valid": False, "error": "文件不存在"}
    
    file_ext = os.path.splitext(video_path)[1].lower()
    if file_ext not in get_supported_video_formats():
        return {
            "valid": False, 
            "error": f"不支持的视频格式: {file_ext}。支持的格式: {', '.join(get_supported_video_formats())}"
        }
    
    try:
        video = VideoFileClip(video_path)
        duration = video.duration
        fps = video.fps
        size = video.size
        video.close()
        
        return {
            "valid": True,
            "duration": duration,
            "fps": fps,
            "size": size,
            "format": file_ext
        }
    except Exception as e:
        return {"valid": False, "error": f"无法读取视频文件: {str(e)}"}