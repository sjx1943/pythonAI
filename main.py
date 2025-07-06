#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests
import tempfile
import uuid
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from typing import Optional, List
import json
from fastapi import UploadFile, File
import shutil
from fastapi.responses import FileResponse, StreamingResponse
import azure.cognitiveservices.speech as speechsdk
import time
from pydub import AudioSegment
import io
import noisereduce as nr
import numpy as np
from fastapi import Form
from pathlib import Path
import logging
import subprocess

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()

# Azure Speech服务配置
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION")

app = FastAPI(
    title="Azure Real-time Transcription Service with Language Identification",
    description="A high-performance API to transcribe audio using Azure AI Speech Real-time Transcription service with automatic language detection and multilingual support."
)

class AudioInput(BaseModel):
    audio_url: str = Field(
        ...,
        description="The public URL of the audio file to be transcribed.",
        example="https://www.book2.nl/book2/ZH/SOUND/0703.mp3"
    )
    language: Optional[str] = Field(
        default=None,
        description="Language code (e.g., en-US, zh-CN). If not provided or null, automatic language detection will be used.",
        example="zh-CN"
    )
    candidate_locales: Optional[List[str]] = Field(
        default=["zh-CN","ja-JP", "en-US", "es-ES"],
        description="List of candidate languages for automatic detection. If not provided, a comprehensive list will be used.",
        example=["zh-CN","ja-JP", "en-US", "es-ES"]
    )
    enable_diarization: bool = Field(
        default=False,
        description="Enable speaker diarization",
        example=False
    )
    language_identification_mode: str = Field(
        default="Continuous",
        description="Language identification mode: 'Continuous' or 'AtStart'",
        example="Continuous"
    )
    multilingual_detection: bool = Field(
        default=True,
        description="Enable multilingual detection for mixed-language audio",
        example=True
    )

async def download_audio_file(url: str) -> bytes:
    """异步下载音频文件并返回字节数据"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
                response.raise_for_status()
                return await response.read()
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio from URL: {str(e)}")

def get_default_candidate_locales() -> List[str]:
    """获取默认的候选语言列表，优化常用语言的检测顺序"""
    return [
        "en-US", "zh-CN", "ja-JP", "es-ES", "fr-FR",
        "de-DE", "pt-BR", "it-IT", "ru-RU", "ko-KR", "zh-TW"
    ]

def convert_audio_to_wav(audio_data: bytes) -> str:
    """
    将下载的音频数据转码为WAV格式，支持非常规音频格式
    """
    try:
        # # 设置ffmpeg路径
        # ffmpeg_path = Path(__file__).parent / "static_ffmpeg" / "ffmpeg"
        # if ffmpeg_path.exists():
        #     AudioSegment.converter = str(ffmpeg_path)
        #     logger.info(f"Using bundled ffmpeg from: {ffmpeg_path}")
        # else:
        #     logger.warning("Bundled ffmpeg not found. Relying on system-installed ffmpeg")

        logger.info("Relying on system-installed ffmpeg")
        # 使用pydub从内存中的字节数据加载音频
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))

        # 音频增强：降噪处理（关键改进点）
        audio_array = np.array(audio_segment.get_array_of_samples())
        audio_array = audio_array.astype(np.float32)
        reduced_noise = nr.reduce_noise(
            y=audio_array,
            sr=audio_segment.frame_rate,
            stationary=True
        )
        audio_segment = AudioSegment(
            reduced_noise.astype(np.int16).tobytes(),
            frame_rate=audio_segment.frame_rate,
            sample_width=audio_segment.sample_width,
            channels=audio_segment.channels
        )

        audio_segment = audio_segment.high_pass_filter(80)  # 过滤低频噪声
        audio_segment = audio_segment.normalize()

        # 确保音频为16kHz单声道，16-bit PCM
        audio_segment = audio_segment.set_frame_rate(16000)
        audio_segment = audio_segment.set_channels(1)
        audio_segment = audio_segment.set_sample_width(2)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', dir="/tmp", delete=False) as temp_wav_file:
            audio_segment.export(temp_wav_file.name, format="wav")
            return temp_wav_file.name

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to convert audio to WAV format: {str(e)}")


class RealTimeTranscriber:
    """Azure Speech SDK实时转录器"""

    def __init__(self, speech_key: str, service_region: str):
        self.speech_key = speech_key
        self.service_region = service_region
        self.results = []
        self.is_completed = False
        self.recognition_error = None

    def transcribe_audio_file(self, audio_file_path: str,
                              language: Optional[str] = None,
                              candidate_locales: Optional[List[str]] = None,
                              enable_diarization: bool = False,
                              multilingual_detection: bool = False) -> dict:
        """使用Azure Speech SDK转录音频文件"""
        try:
            audio_segment = AudioSegment.from_file(audio_file_path)
            logger.info(f"Audio properties: {len(audio_segment)}ms, "
                        f"{audio_segment.frame_rate}Hz, "
                        f"{audio_segment.channels}ch, "
                        f"{audio_segment.sample_width * 8}-bit, "
                        f"{audio_segment.dBFS}dBFS")
            speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.service_region)
            speech_config.output_format = speechsdk.OutputFormat.Detailed
            speech_config.request_word_level_timestamps()

            if enable_diarization:
                speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EnableSpeakerDiarization, "true")

            audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

            if multilingual_detection:
                if not candidate_locales:
                    candidate_locales = get_default_candidate_locales()

                if hasattr(speechsdk.PropertyId, 'SpeechServiceConnection_ContinuousLanguageIdPriority'):
                    speech_config.set_property(
                        speechsdk.PropertyId.SpeechServiceConnection_ContinuousLanguageIdPriority, "Accuracy"
                    )

                speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, "Continuous")

                auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=candidate_locales)

                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    auto_detect_source_language_config=auto_detect_source_language_config,
                    audio_config=audio_config
                )
            elif language:
                speech_config.speech_recognition_language = language
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )
            else:
                if not candidate_locales:
                    candidate_locales = get_default_candidate_locales()
                auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=candidate_locales)
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    auto_detect_source_language_config=auto_detect_source_language_config,
                    audio_config=audio_config
                )

            self.results = []
            self.is_completed = False
            self.recognition_error = None

            speech_recognizer.recognized.connect(self._on_recognized)
            speech_recognizer.session_stopped.connect(self._on_session_stopped)
            speech_recognizer.canceled.connect(self._on_canceled)

            speech_recognizer.start_continuous_recognition()

            timeout = 120
            start_time = time.time()
            while not self.is_completed and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            speech_recognizer.stop_continuous_recognition()

            if self.recognition_error:
                raise Exception(self.recognition_error)

            if not self.results and not self.is_completed:
                raise Exception("Recognition timed out.")

            return self._process_results()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Real-time transcription failed: {str(e)}")

    def _on_recognized(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            result_data = {
                'text': evt.result.text,
                'offset': evt.result.offset,
                'duration': evt.result.duration,
                'confidence': 0.0,
                'language': 'unknown',
                'speaker_id': None
            }

            if evt.result.properties:
                language_detection_result = evt.result.properties.get(speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult)
                if language_detection_result:
                    result_data['language'] = language_detection_result

                confidence_property = evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
                if confidence_property:
                    try:
                        json_result = json.loads(confidence_property)
                        if 'NBest' in json_result and json_result['NBest']:
                            result_data['confidence'] = json_result['NBest'][0].get('Confidence', 0.0)
                    except: pass

            if hasattr(evt.result, 'speaker_id'):
                result_data['speaker_id'] = evt.result.speaker_id

            self.results.append(result_data)

    def _on_session_stopped(self, evt):
        self.is_completed = True

    def _on_canceled(self, evt):
        if evt.reason == speechsdk.CancellationReason.Error:
            self.recognition_error = f"Recognition canceled: {evt.error_details}. Error code: {evt.error_code}"
        self.is_completed = True

    def _process_results(self) -> dict:
        if not self.results:
            return {"combinedPhrases": [{"channel": 0, "text": ""}], "phrases": [], "duration": 0, "multilingual_segments": [], "total_segments": 0}

        combined_text = " ".join([r['text'] for r in self.results if r['text'].strip()])
        phrases = []
        multilingual_segments = []

        for i, result in enumerate(self.results):
            if result['text'].strip():
                start_time = result['offset'] / 10000000.0
                end_time = start_time + (result['duration'] / 10000000.0)

                phrase = {
                    "channel": 0, "offset": result['offset'], "duration": result['duration'],
                    "text": result['text'], "confidence": result['confidence'],
                    "locale": result['language'], "detected_language": result['language']
                }
                if result['speaker_id']:
                    phrase['speaker'] = result['speaker_id']
                phrases.append(phrase)

                multilingual_segments.append({
                    "text": result['text'], "language": result['language'],
                    "start_time": start_time, "end_time": end_time,
                    "confidence": result['confidence'], "segment_index": i,
                    "speaker_id": result['speaker_id']
                })

        total_duration = (self.results[-1]['offset'] + self.results[-1]['duration']) / 10000.0 if self.results else 0

        return {
            "combinedPhrases": [{"channel": 0, "text": combined_text}], "phrases": phrases,
            "duration": total_duration, "multilingual_segments": multilingual_segments,
            "total_segments": len(multilingual_segments)
        }

def validate_audio_segment(audio_segment: AudioSegment):
    """验证音频段是否符合要求"""
    if audio_segment.frame_rate != 16000:
        logger.warning(f"Audio frame rate {audio_segment.frame_rate}Hz is not 16000Hz")
    if audio_segment.channels != 1:
        logger.warning(f"Audio has {audio_segment.channels} channels (expected 1)")
    if audio_segment.sample_width != 2:
        logger.warning(f"Audio sample width {audio_segment.sample_width} is not 2 (16-bit)")
    if audio_segment.dBFS < -45:
        logger.warning(f"Audio may be too quiet (dBFS: {audio_segment.dBFS})")

def transcribe_with_realtime_api(audio_data: bytes,
                                 language: Optional[str] = None,
                                 candidate_locales: Optional[List[str]] = None,
                                 enable_diarization: bool = False,
                                 multilingual_detection: bool = False) -> dict:

    audio_file_path = convert_audio_to_wav(audio_data)

    try:
        transcriber = RealTimeTranscriber(AZURE_SPEECH_KEY, AZURE_SPEECH_REGION)
        result = transcriber.transcribe_audio_file(
            audio_file_path=audio_file_path,
            language=language,
            candidate_locales=candidate_locales,
            enable_diarization=enable_diarization,
            multilingual_detection=multilingual_detection
        )
        return result
    finally:
        if os.path.exists(audio_file_path):
            os.unlink(audio_file_path)

# (extract_multilingual_info, extract_text_and_language_info, 和所有 @app 端点函数保持不变)
# ... The rest of the functions (extract_multilingual_info, extract_text_and_language_info, and all @app endpoints) remain the same.
# I am omitting them here for brevity, but they are part of the full solution.

# =========================================================================================
# The rest of the code is provided below for completeness
# =========================================================================================

def extract_multilingual_info(result: dict) -> tuple[str, List[str], dict]:
    """从多语言结果中提取信息"""
    try:
        # 提取合并文本
        transcribed_text = ""
        if "combinedPhrases" in result:
            for phrase in result["combinedPhrases"]:
                if "text" in phrase:
                    transcribed_text = phrase["text"]
                    break

        # 提取检测到的语言列表
        detected_languages = []
        language_details = {}

        if "multilingual_segments" in result:
            for segment in result["multilingual_segments"]:
                lang = segment.get("language", "unknown")
                if lang not in detected_languages and lang != "unknown":
                    detected_languages.append(lang)

            language_details = {
                "segments": result["multilingual_segments"],
                "language_count": len(detected_languages),
                "total_segments": len(result["multilingual_segments"]),
                "detected_locales": detected_languages
            }

        return transcribed_text, detected_languages, language_details

    except Exception as e:
        return "", [], {}

def extract_text_and_language_info(result: dict) -> tuple[str, str, dict]:
    """从API结果中提取文本、检测到的语言和详细语言信息"""
    try:
        transcribed_text = ""
        detected_language = "unknown"
        language_detection_details = {}

        # 处理Real-time Transcription API返回格式
        if "combinedPhrases" in result:
            text_parts = []
            for phrase in result["combinedPhrases"]:
                if "text" in phrase:
                    text_parts.append(phrase["text"])
            transcribed_text = " ".join(text_parts)

        # 从phrases中提取语言信息
        if "phrases" in result and result["phrases"]:
            detected_locales = []
            confidence_scores = {}

            for phrase in result["phrases"]:
                if "locale" in phrase and phrase["locale"]:
                    detected_locales.append(phrase["locale"])
                    if detected_language == "unknown":
                        detected_language = phrase["locale"]

                if "confidence" in phrase:
                    lang = phrase.get("locale", "unknown")
                    if lang not in confidence_scores:
                        confidence_scores[lang] = []
                    confidence_scores[lang].append(phrase["confidence"])

            # 计算平均置信度
            avg_confidence_scores = {}
            for lang, scores in confidence_scores.items():
                avg_confidence_scores[lang] = sum(scores) / len(scores) if scores else 0.0

            language_detection_details = {
                "detected_locales": list(set(detected_locales)),
                "confidence_scores": avg_confidence_scores
            }

        return transcribed_text, detected_language, language_detection_details

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from result: {str(e)}")

@app.post("/check-audio-format")
async def check_audio_format(file: UploadFile = File(...)):
    """检查音频文件格式"""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            audio = AudioSegment.from_file(tmp_path)
            return {
                "valid": True,
                "format": audio.file_format,
                "duration": len(audio),
                "sample_rate": audio.frame_rate,
                "channels": audio.channels
            }
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/fast-transcribe", summary="Fast Transcription API")
async def fast_transcription(
    audio_url: str = Form(None, description="Audio URL to transcribe"),
    audio_file: UploadFile = File(None, description="Audio file to upload"),
    locales: str = Form('[]', description="JSON array of locales to detect")
):
    """
    快速转录API，支持URL和文件上传两种方式
    使用Azure Speech-to-Text REST API进行转录
    """
    try:
        # 验证密钥配置
        if not AZURE_SPEECH_KEY:
            raise HTTPException(
                status_code=500,
                detail="Azure Speech Service credentials not configured"
            )

        # 准备表单数据
        data = aiohttp.FormData()
        if audio_url:
            # 下载音频数据
            audio_data = await download_audio_file(audio_url)
            data.add_field('audio', audio_data, filename='audio.wav', content_type='audio/wav')
            data.add_field('definition', f'{{"locales": {locales}}}')
        elif audio_file:
            # 使用上传的文件
            content = await audio_file.read()
            data.add_field('audio', content, filename=audio_file.filename, content_type=audio_file.content_type)
            data.add_field('definition', f'{{"locales": {locales}}}')
        else:
            raise HTTPException(
                status_code=400,
                detail="Either audio_url or audio_file must be provided"
            )

        # 准备请求头
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY
        }

        # 发送请求到Azure API
        api_url = "https://eastus2.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2024-11-15"
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, data=data) as response:
                if response.status != 200:
                    error_detail = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Azure API error: {error_detail}"
                    )
                return await response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fast transcription failed: {str(e)}"
        )


@app.post("/real-time-transcribe", summary="Real-time Transcribe Audio from URL with Language Detection")
async def real_time_transcription(input_data: AudioInput):
    """
    使用Azure Speech SDK Real-time API转录音频URL
    支持智能语言检测、指定语言转录和多语言混合识别
    """
    try:
        # 验证必要的环境变量
        if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
            raise HTTPException(
                status_code=500,
                detail="Azure Speech Service credentials not configured. Please set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION environment variables."
            )

        # 处理本地 URL，直接读取文件
        if input_data.audio_url.startswith("http://localhost:8002/audio/"):
            filename = input_data.audio_url.split("/audio/")[1]
            audio_file_path = os.path.join("temp_audio", filename)
            if not os.path.exists(audio_file_path):
                raise HTTPException(status_code=404, detail="Audio file not found in temp directory")
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
        else:
            # 异步下载远程 URL
            audio_data = await download_audio_file(input_data.audio_url)

        audio_file_path = convert_audio_to_wav(audio_data)

        # 创建异步生成器函数
        async def generate():
            transcriber = RealTimeTranscriber(AZURE_SPEECH_KEY, AZURE_SPEECH_REGION)
            audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

            # 使用队列来收集结果
            from collections import deque
            result_queue = deque()

            def on_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    try:
                        json_result = json.loads(evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
                        nbest = json_result.get('NBest', [])
                    except:
                        nbest = []

                    result = {
                        "Id": str(uuid.uuid4()),
                        "RecognitionStatus": "Success",
                        "Offset": evt.result.offset,
                        "Duration": evt.result.duration,
                        "PrimaryLanguage": {
                            "Language": evt.result.properties.get(speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult, "unknown"),
                            "Confidence": "Unknown"
                        },
                        "Channel": 0,
                        "DisplayText": evt.result.text,
                        "NBest": nbest
                    }
                    result_queue.append(result)

            # 配置识别器
            speech_config = speechsdk.SpeechConfig(
                subscription=AZURE_SPEECH_KEY,
                region=AZURE_SPEECH_REGION
            )
            speech_config.output_format = speechsdk.OutputFormat.Detailed
            speech_config.request_word_level_timestamps()

            # 配置说话人分离
            if input_data.enable_diarization:
                speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceConnection_EnableSpeakerDiarization,
                    "false"
                )

            # 多语言检测配置
            if input_data.multilingual_detection:
                candidate_locales = input_data.candidate_locales or get_default_candidate_locales()

                if hasattr(speechsdk.PropertyId, 'SpeechServiceConnection_ContinuousLanguageIdPriority'):
                    speech_config.set_property(
                        speechsdk.PropertyId.SpeechServiceConnection_ContinuousLanguageIdPriority,
                        "Accuracy"
                    )

                speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
                    input_data.language_identification_mode
                )

                auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=candidate_locales
                )

                recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    auto_detect_source_language_config=auto_detect_source_language_config,
                    audio_config=audio_config
                )
            elif input_data.language:
                # 单语言模式
                speech_config.speech_recognition_language = input_data.language
                recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )
            else:
                # 自动语言检测
                candidate_locales = input_data.candidate_locales or get_default_candidate_locales()
                auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=candidate_locales
                )
                recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    auto_detect_source_language_config=auto_detect_source_language_config,
                    audio_config=audio_config
                )

            recognizer.recognized.connect(on_recognized)
            recognizer.start_continuous_recognition()

            try:
                while not transcriber.is_completed:
                    if result_queue:
                        result = result_queue.popleft()
                        json_str = json.dumps(result, ensure_ascii=False)
                        # yield f"data: {json.dumps(result_queue.popleft())}\n\n"
                        yield f"data: {json_str}\n\n"
                    await asyncio.sleep(0.1)
            finally:
                recognizer.stop_continuous_recognition()
                if os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/supported-languages")
def get_supported_languages():
    """获取支持语言列表"""
    return {
        "supported_languages": get_default_candidate_locales(),
        "language_identification_modes": ["Continuous", "AtStart"],
        "total_languages": len(get_default_candidate_locales()),
        "multilingual_detection": "Available"
    }

@app.get("/health")
def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Azure Real-time Transcription API with Enhanced Language Detection",
        "region": AZURE_SPEECH_REGION,
        "key_configured": bool(AZURE_SPEECH_KEY),
        "features": ["multilingual_detection", "realtime_transcription", "speaker_diarization"]
    }

@app.get("/")
def root():
    """根端点，返回API信息"""
    return {
        "message": "ASR API is running on VPS",
        "version": "5.0",
        "docs": "/docs",
        "health": "/health",
        "supported_languages": "/supported-languages"
    }

from fastapi import Request

@app.post("/upload-audio")
async def upload_audio(request: Request, file: UploadFile = File(...)):
    """上传音频文件并自动转换非常规格式"""
    try:
        temp_dir = "temp_audio"
        os.makedirs(temp_dir, exist_ok=True)

        # 读取文件内容
        content = await file.read()
        original_filename = file.filename

        # 生成唯一临时文件名
        temp_filename = f"temp_{uuid.uuid4().hex}"

        # 如果是MP3/M4A等格式，先尝试转换
        if original_filename.lower().endswith(('.mp3', '.m4a', '.aac')):
            try:
                # 创建临时输入文件
                input_path = os.path.join(temp_dir, f"{temp_filename}_input")
                with open(input_path, 'wb') as f:
                    f.write(content)

                # 输出文件路径
                output_path = os.path.join(temp_dir, f"{temp_filename}.wav")

                # 使用ffmpeg转换
                cmd = f"ffmpeg -i {input_path} -ar 16000 -ac 1 -c:a pcm_s16le {output_path}"
                result = subprocess.run(cmd.split(), capture_output=True)

                if result.returncode != 0:
                    raise ValueError(f"Audio conversion failed: {result.stderr.decode()}")

                # 读取转换后的内容
                with open(output_path, 'rb') as f:
                    content = f.read()
                final_filename = f"{original_filename.rsplit('.', 1)[0]}.wav"

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")
            finally:
                # 清理临时文件
                for path in [input_path, output_path]:
                    if path and os.path.exists(path):
                        os.unlink(path)
        else:
            final_filename = original_filename

        # 保存最终文件
        file_path = os.path.join(temp_dir, final_filename)
        with open(file_path, 'wb') as f:
            f.write(content)

        base_url = str(request.base_url)
        return {
            "url": f"{base_url}audio/{final_filename}",
            "expires": "1 hour",
            "original_format": original_filename.split('.')[-1],
            "converted": original_filename != final_filename
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """提供音频文件访问"""
    file_path = os.path.join("temp_audio", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="audio/mpeg")


# 本地测试时启动
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)