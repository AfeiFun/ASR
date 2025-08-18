import os
import tempfile
import torch
import re
from funasr import AutoModel
from typing import Optional, Dict, Any, List

class ASRTranscriber:
    """
    基于FunASR的语音转文字转录器
    """
    
    def __init__(self, model_name="iic/SenseVoiceSmall", vad_model="fsmn-vad", device="auto", enable_vad=True):
        """
        初始化ASR转录器
        
        Args:
            model_name (str): ASR模型名称
            vad_model (str): VAD(语音活动检测)模型名称
            device (str): 设备类型 ("cpu", "cuda", "mps", "auto")
            enable_vad (bool): 是否启用VAD (默认: True)
        """
        self.model_name = model_name
        self.vad_model = vad_model if enable_vad else None
        self.enable_vad = enable_vad
        self.device = self._get_optimal_device(device)
        self.model = None
        self._load_model()
    
    def _get_optimal_device(self, device: str) -> str:
        """
        获取最优计算设备
        
        Args:
            device (str): 用户指定的设备或"auto"
            
        Returns:
            str: 最优设备名称
        """
        if device != "auto":
            return device
        
        # 自动检测最佳设备
        if torch.cuda.is_available():
            print("🚀 检测到CUDA GPU，使用GPU加速")
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print("🚀 检测到Apple GPU（MPS），使用GPU加速")
            return "mps"
        else:
            print("💻 使用CPU计算")
            return "cpu"
    
    def _load_model(self):
        """
        加载ASR模型
        """
        try:
            print(f"正在加载模型: {self.model_name}...")
            if self.enable_vad:
                print("VAD已启用，将使用智能语音分段")
                self.model = AutoModel(
                    model=self.model_name,
                    vad_model=self.vad_model,
                    vad_kwargs={"max_single_segment_time": 15000},  # VAD配置，15秒分段
                    device=self.device
                )
            else:
                print("VAD已禁用，将整体处理音频")
                self.model = AutoModel(
                    model=self.model_name,
                    device=self.device
                )
            print("模型加载成功！")
        except Exception as e:
            raise Exception(f"模型加载失败: {str(e)}")
    
    def transcribe_audio(self, audio_path: str, language: str = "auto", max_length: int = 1800, batch_size: int = 8) -> Dict[str, Any]:
        """
        转录音频文件 - 使用FunASR内置智能分段
        
        Args:
            audio_path (str): 音频文件路径
            language (str): 语言代码 ("auto", "zh", "en", "ja", "ko" 等)
            max_length (int): VAD分段最大长度(秒)，用于merge_length_s参数
            batch_size (int): 批处理大小
        
        Returns:
            Dict[str, Any]: 转录结果
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        if self.model is None:
            raise Exception("模型未正确加载")
        
        # 获取音频信息用于优化参数
        audio_info = self._get_audio_info(audio_path)
        print(f"音频时长: {audio_info['duration']:.1f}秒，使用FunASR智能分段处理")
        
        try:
            print(f"正在转录音频文件: {audio_path}")
            
            # 使用传入的batch_size作为batch_size_s（动态批处理秒数）
            # 如果batch_size较小，扩大到合理值以提高效率
            batch_size_s = min(batch_size, 6000)  # 最大6000秒批处理
            # 设置合理的合并长度，避免片段过短
            merge_length_s = min(max_length, 30)
            
            print(f"使用参数: batch_size_s={batch_size_s}, merge_length_s={merge_length_s}")
            
            # 执行转录，使用FunASR内置智能分段
            result = self.model.generate(
                input=audio_path,
                language=language if language != "auto" else None,
                batch_size_s=batch_size_s,    # 动态批处理大小(秒)
                hotword=None,                 # 热词增强
                use_itn=True,                # 使用逆文本规范化
                output_timestamp=True,        # 启用时间戳输出
                merge_vad=False,             # 默认不启用VAD合并
                # merge_length_s=merge_length_s, # VAD片段合并长度
                return_raw_text=True         # 返回原始文本
            )
            
            # 处理结果
            if isinstance(result, list) and len(result) > 0:
                transcription_result = result[0]
                
                # 调试：检查是否成功获取时间戳
                if self.device != "cpu":  # 只在非CPU模式下显示详细信息
                    timestamps = transcription_result.get("timestamp", [])
                    words = transcription_result.get("words", [])
                    print(f"获取到 {len(timestamps)} 个时间戳，{len(words)} 个词汇")
                
                # 清理文本中的标记符号
                raw_text = transcription_result.get("text", "")
                cleaned_text = self._clean_text(raw_text)
                
                # 处理时间戳和分词信息
                timestamps = transcription_result.get("timestamp", [])
                words = transcription_result.get("words", [])
                
                # 生成带时间戳的segments
                cleaned_segments = self._create_segments_from_timestamps(cleaned_text, timestamps, words)
                
                return {
                    "success": True,
                    "text": cleaned_text,
                    "segments": cleaned_segments,
                    "language": transcription_result.get("language", "unknown"),
                    "duration": transcription_result.get("duration", 0),
                    "confidence": transcription_result.get("confidence", 0)
                }
            else:
                return {
                    "success": False,
                    "error": "未获取到转录结果",
                    "text": "",
                    "segments": []
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"转录失败: {str(e)}",
                "text": "",
                "segments": []
            }
    
    def transcribe_with_timestamps(self, audio_path: str, language: str = "auto", max_length: int = 1800, batch_size: int = 8) -> Dict[str, Any]:
        """
        转录音频并返回带时间戳的结果
        
        Args:
            audio_path (str): 音频文件路径
            language (str): 语言代码
            max_length (int): 最大处理长度(秒)，超过将分段处理
            batch_size (int): 批处理大小
        
        Returns:
            Dict[str, Any]: 带时间戳的转录结果
        """
        result = self.transcribe_audio(audio_path, language, max_length, batch_size)
        
        if result["success"] and result["segments"]:
            formatted_segments = []
            for i, segment in enumerate(result["segments"]):
                if isinstance(segment, dict):
                    formatted_segments.append({
                        "index": i + 1,
                        "start_time": segment.get("start", 0),
                        "end_time": segment.get("end", 0),
                        "text": segment.get("text", ""),
                        "confidence": segment.get("confidence", 0)
                    })
                else:
                    # 如果segment是字符串，创建一个简单的结构
                    formatted_segments.append({
                        "index": i + 1,
                        "start_time": 0,
                        "end_time": 0,
                        "text": str(segment),
                        "confidence": 0
                    })
            
            result["formatted_segments"] = formatted_segments
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """
        清理文本中的标记符号
        
        Args:
            text (str): 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        
        # 移除各种标记符号
        # 匹配模式：<|...| >
        cleaned_text = re.sub(r'<\|[^|]*\|>', '', text)
        
        # 移除多余的空格
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        # 移除首尾空格
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text
    
    def _clean_segments(self, segments: List[Any]) -> List[Any]:
        """
        清理segments中的文本标记
        
        Args:
            segments (List[Any]): 原始segments
            
        Returns:
            List[Any]: 清理后的segments
        """
        cleaned_segments = []
        
        for segment in segments:
            if isinstance(segment, dict):
                # 复制segment字典
                cleaned_segment = segment.copy()
                # 清理text字段
                if "text" in cleaned_segment:
                    cleaned_segment["text"] = self._clean_text(cleaned_segment["text"])
                cleaned_segments.append(cleaned_segment)
            else:
                # 如果是字符串，直接清理
                cleaned_segments.append(self._clean_text(str(segment)))
        
        return cleaned_segments
    
    def _clean_segments_with_timestamps(self, segments: List[Any]) -> List[Any]:
        """
        清理segments中的文本标记，保留时间戳信息
        
        Args:
            segments (List[Any]): 原始segments
            
        Returns:
            List[Any]: 清理后的segments，保留时间戳
        """
        cleaned_segments = []
        
        for segment in segments:
            if isinstance(segment, dict):
                # 复制segment字典，保留所有时间戳信息
                cleaned_segment = segment.copy()
                # 清理text字段
                if "text" in cleaned_segment:
                    cleaned_segment["text"] = self._clean_text(cleaned_segment["text"])
                # 保留时间戳字段：start, end, timestamp等
                cleaned_segments.append(cleaned_segment)
            else:
                # 如果是字符串，转换为字典格式
                cleaned_segments.append({
                    "text": self._clean_text(str(segment)),
                    "start": None,
                    "end": None
                })
        
        return cleaned_segments
    
    def _create_segments_from_timestamps(self, text: str, timestamps: List[List[int]], words: List[str]) -> List[Dict[str, Any]]:
        """
        从时间戳和词汇信息创建segments
        
        Args:
            text (str): 清理后的文本
            timestamps (List[List[int]]): 时间戳列表，以毫秒为单位
            words (List[str]): 词汇列表
            
        Returns:
            List[Dict[str, Any]]: 带时间戳的segments
        """
        if not timestamps or not words or len(timestamps) != len(words):
            return []
        
        # 按句子分组时间戳
        segments = []
        current_segment = {
            "text": "",
            "start": None,
            "end": None,
            "words": []
        }
        
        for i, (word, timestamp) in enumerate(zip(words, timestamps)):
            # 跳过标记符号
            if word.startswith('<|') and word.endswith('|>'):
                continue
                
            start_ms, end_ms = timestamp
            start_sec = start_ms / 1000.0
            end_sec = end_ms / 1000.0
            
            # 设置segment开始时间
            if current_segment["start"] is None:
                current_segment["start"] = start_sec
            
            # 添加词汇到当前segment
            current_segment["text"] += word
            current_segment["end"] = end_sec
            current_segment["words"].append({
                "word": word,
                "start": start_sec,
                "end": end_sec
            })
            
            # 判断是否应该结束当前segment（遇到句号、问号、感叹号）
            if word in ['。', '！', '？', '.', '!', '?',',','，'] or i == len(words) - 1:
                if current_segment["text"].strip():
                    segments.append({
                        "text": current_segment["text"],
                        "start": current_segment["start"],
                        "end": current_segment["end"],
                        "words": current_segment["words"]
                    })
                
                # 重置当前segment
                current_segment = {
                    "text": "",
                    "start": None,
                    "end": None,
                    "words": []
                }
        
        return segments

    def get_supported_languages(self) -> List[str]:
        """
        获取支持的语言列表
        
        Returns:
            List[str]: 支持的语言代码列表
        """
        return ["auto", "zh", "en", "ja", "ko", "es", "fr", "de", "it", "pt", "ru"]
    
    def format_transcription_output(self, result: Dict[str, Any], output_format: str = "text") -> str:
        """
        格式化转录输出
        
        Args:
            result (Dict[str, Any]): 转录结果
            output_format (str): 输出格式 ("text", "srt", "vtt", "json")
        
        Returns:
            str: 格式化后的输出
        """
        if not result["success"]:
            return f"转录失败: {result.get('error', '未知错误')}"
        
        if output_format == "text":
            return result["text"]
        
        elif output_format == "srt":
            return self._format_as_srt(result)
        
        elif output_format == "vtt":
            return self._format_as_vtt(result)
        
        elif output_format == "json":
            import json
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        else:
            return result["text"]
    
    def _format_as_srt(self, result: Dict[str, Any]) -> str:
        """格式化为SRT字幕格式"""
        srt_content = ""
        
        # 优先使用formatted_segments（带时间戳）
        if "formatted_segments" in result and result["formatted_segments"]:
            segments = result["formatted_segments"]
            for segment in segments:
                start_time = self._seconds_to_srt_time(segment["start_time"])
                end_time = self._seconds_to_srt_time(segment["end_time"])
                
                srt_content += f"{segment['index']}\n"
                srt_content += f"{start_time} --> {end_time}\n"
                srt_content += f"{segment['text']}\n\n"
        
        # 使用真实时间戳的segments
        elif "segments" in result and result["segments"]:
            segments = result["segments"]
            
            for i, segment in enumerate(segments):
                if isinstance(segment, dict) and "start" in segment and "end" in segment:
                    # 使用FunASR返回的真实时间戳
                    start_time = self._seconds_to_srt_time(segment["start"])
                    end_time = self._seconds_to_srt_time(segment["end"])
                    text = segment.get("text", "")
                    
                    srt_content += f"{i + 1}\n"
                    srt_content += f"{start_time} --> {end_time}\n"
                    srt_content += f"{text}\n\n"
        
        # 最后兜底：使用全文本，智能分句
        else:
            text = result.get("text", "")
            if text:
                # 改进的句子分割：同时按句号、问号、感叹号分割
                sentences = re.split(r'[。！？.!?]', text)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                current_time = 0
                for i, sentence in enumerate(sentences):
                    # 根据句子长度动态计算时间
                    duration = max(2.0, len(sentence) * 0.4)  # 最少2秒
                    start_time = self._seconds_to_srt_time(current_time)
                    end_time = self._seconds_to_srt_time(current_time + duration)
                    current_time += duration
                    
                    # 恢复标点符号
                    if not sentence.endswith(('。', '！', '？', '.', '!', '?')):
                        sentence += '。'
                    
                    srt_content += f"{i + 1}\n"
                    srt_content += f"{start_time} --> {end_time}\n"
                    srt_content += f"{sentence}\n\n"
        
        return srt_content
    
    def _format_as_vtt(self, result: Dict[str, Any]) -> str:
        """格式化为VTT字幕格式"""
        vtt_content = "WEBVTT\n\n"
        
        # 优先使用formatted_segments（带时间戳）
        if "formatted_segments" in result and result["formatted_segments"]:
            segments = result["formatted_segments"]
            for segment in segments:
                start_time = self._seconds_to_vtt_time(segment["start_time"])
                end_time = self._seconds_to_vtt_time(segment["end_time"])
                
                vtt_content += f"{start_time} --> {end_time}\n"
                vtt_content += f"{segment['text']}\n\n"
        
        # 使用原始segments中的真实时间戳
        elif "segments" in result and result["segments"]:
            segments = result["segments"]
            for i, segment in enumerate(segments):
                if isinstance(segment, dict):
                    # 如果有真实的时间戳，使用它们
                    if "start" in segment and "end" in segment:
                        start_time = self._seconds_to_vtt_time(segment["start"])
                        end_time = self._seconds_to_vtt_time(segment["end"])
                    else:
                        # 否则根据段落长度估算更合理的时间
                        text = segment.get("text", "")
                        duration = max(2.0, len(text) * 0.4)
                        start_time = self._seconds_to_vtt_time(i * duration)
                        end_time = self._seconds_to_vtt_time((i + 1) * duration)
                    
                    text = segment.get("text", str(segment))
                else:
                    # 字符串类型的segment
                    text = str(segment)
                    duration = max(2.0, len(text) * 0.4)
                    start_time = self._seconds_to_vtt_time(i * duration)
                    end_time = self._seconds_to_vtt_time((i + 1) * duration)
                
                vtt_content += f"{start_time} --> {end_time}\n"
                vtt_content += f"{text}\n\n"
        
        # 最后兜底：使用全文本，智能分句
        else:
            text = result.get("text", "")
            if text:
                # 改进的句子分割
                sentences = re.split(r'[。！？.!?]', text)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                current_time = 0
                for i, sentence in enumerate(sentences):
                    # 根据句子长度动态计算时间
                    duration = max(2.0, len(sentence) * 0.4)
                    start_time = self._seconds_to_vtt_time(current_time)
                    end_time = self._seconds_to_vtt_time(current_time + duration)
                    current_time += duration
                    
                    # 恢复标点符号
                    if not sentence.endswith(('。', '！', '？', '.', '!', '?')):
                        sentence += '。'
                    
                    vtt_content += f"{start_time} --> {end_time}\n"
                    vtt_content += f"{sentence}\n\n"
        
        return vtt_content
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """将秒数转换为VTT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def _get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """
        获取音频文件信息
        
        Args:
            audio_path (str): 音频文件路径
            
        Returns:
            Dict[str, Any]: 音频信息
        """
        try:
            import soundfile as sf
            data, samplerate = sf.read(audio_path)
            duration = len(data) / samplerate
            return {
                "duration": duration,
                "sample_rate": samplerate,
                "channels": data.shape[1] if len(data.shape) > 1 else 1,
                "samples": len(data)
            }
        except Exception as e:
            raise Exception(f"无法读取音频文件信息: {str(e)}")
    
