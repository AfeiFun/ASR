import os
import tempfile
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

class VideoDownloader:
    """
    基于yt-dlp的视频下载器
    支持YouTube、Bilibili等多个视频平台
    """
    
    def __init__(self, yt_dlp_path: str = "yt-dlp"):
        """
        初始化视频下载器
        
        Args:
            yt_dlp_path (str): yt-dlp可执行文件路径，默认使用系统PATH中的yt-dlp
        """
        self.yt_dlp_path = yt_dlp_path
        self._check_yt_dlp()
    
    def _check_yt_dlp(self):
        """检查yt-dlp是否可用"""
        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode != 0:
                raise Exception(f"yt-dlp不可用: {result.stderr}")
            print(f"✅ yt-dlp版本: {result.stdout.strip()}")
        except FileNotFoundError:
            raise Exception(f"找不到yt-dlp，请确保已安装并在PATH中: {self.yt_dlp_path}")
        except subprocess.TimeoutExpired:
            raise Exception("yt-dlp响应超时")
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息
        
        Args:
            url (str): 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息
        """
        try:
            cmd = [
                self.yt_dlp_path,
                "--no-download",
                "--dump-json",
                "--no-warnings",
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise Exception(f"获取视频信息失败: {result.stderr}")
            
            # 解析JSON信息
            info = json.loads(result.stdout.strip())
            
            return {
                "id": info.get("id", ""),
                "title": info.get("title", "Unknown Title"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown Uploader"),
                "upload_date": info.get("upload_date", ""),
                "view_count": info.get("view_count", 0),
                "description": info.get("description", "")[:500] + "..." if info.get("description", "") else "",
                "formats_available": len(info.get("formats", [])),
                "ext": info.get("ext", "mp4"),
                "webpage_url": info.get("webpage_url", url)
            }
            
        except json.JSONDecodeError as e:
            raise Exception(f"解析视频信息JSON失败: {str(e)}")
        except subprocess.TimeoutExpired:
            raise Exception("获取视频信息超时")
        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")
    
    def download_video(
        self, 
        url: str, 
        output_dir: Optional[str] = None,
        format_selector: str = "best[height<=720]",
        audio_only: bool = False
    ) -> str:
        """
        下载视频
        
        Args:
            url (str): 视频URL
            output_dir (str, optional): 输出目录，默认使用临时目录
            format_selector (str): 格式选择器，默认选择720p以下最佳质量
            audio_only (bool): 是否只下载音频
            
        Returns:
            str: 下载的文件路径
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="video_download_")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 获取视频信息用于生成文件名
            info = self.get_video_info(url)
            safe_title = self._sanitize_filename(info["title"])
            
            # 构建输出模板
            if audio_only:
                output_template = str(output_dir / f"{safe_title}.%(ext)s")
                format_selector = "bestaudio/best"
            else:
                output_template = str(output_dir / f"{safe_title}.%(ext)s")
            
            if audio_only:
                cmd = [
                    self.yt_dlp_path,
                    "-o", output_template,
                    "--no-warnings",
                    url
                ]
            else:
                cmd = [
                    self.yt_dlp_path,
                    "-o", output_template,
                    "--no-warnings",
                    url
                ]
            
            # 如果只要音频，添加音频转换参数
            if audio_only:
                cmd.extend([
                    "--extract-audio",
                    "--audio-format", "wav",
                    "--audio-quality", "0"
                ])
            
            print(f"正在下载{'音频' if audio_only else '视频'}: {info['title']}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30分钟超时
            )
            
            if result.returncode != 0:
                raise Exception(f"下载失败: {result.stderr}")
            
            # 查找下载的文件
            downloaded_files = list(output_dir.glob(f"{safe_title}.*"))
            if not downloaded_files:
                raise Exception("未找到下载的文件")
            
            downloaded_file = str(downloaded_files[0])
            print(f"✅ 下载完成: {downloaded_file}")
            
            return downloaded_file
            
        except subprocess.TimeoutExpired:
            raise Exception("下载超时（30分钟）")
        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")
    
    def download_audio_only(self, url: str, output_dir: Optional[str] = None) -> str:
        """
        只下载音频
        
        Args:
            url (str): 视频URL
            output_dir (str, optional): 输出目录
            
        Returns:
            str: 下载的音频文件路径
        """
        return self.download_video(url, output_dir, audio_only=True)
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename (str): 原文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        # 移除前后空白字符
        filename = filename.strip()
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = "video"
        
        return filename
    
    def get_supported_sites(self) -> List[str]:
        """
        获取支持的网站列表
        
        Returns:
            List[str]: 支持的网站列表
        """
        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--list-extractors"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                extractors = result.stdout.strip().split('\n')
                # 过滤出主要的网站
                major_sites = [
                    site for site in extractors 
                    if any(keyword in site.lower() for keyword in [
                        'youtube', 'bilibili', 'twitter', 'tiktok', 
                        'instagram', 'facebook', 'vimeo', 'dailymotion'
                    ])
                ]
                return major_sites[:20]  # 返回前20个主要网站
            else:
                return ["YouTube", "Bilibili", "Twitter", "TikTok"]  # 默认列表
                
        except Exception:
            return ["YouTube", "Bilibili", "Twitter", "TikTok"]  # 默认列表
    
    def is_supported_url(self, url: str) -> bool:
        """
        检查URL是否被支持
        
        Args:
            url (str): 视频URL
            
        Returns:
            bool: 是否支持该URL
        """
        try:
            # 简单的URL验证
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 尝试获取视频信息来验证支持性
            info = self.get_video_info(url)
            return bool(info.get("title"))
            
        except Exception:
            return False