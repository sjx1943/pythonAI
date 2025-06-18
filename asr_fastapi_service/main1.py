#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests
import tempfile
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from typing import Optional, List
import json
from fastapi import UploadFile, File
import shutil
from fastapi.responses import FileResponse
import azure.cognitiveservices.speech as speechsdk
import time
from pydub import AudioSegment
import io
import noisereduce as nr
import numpy as np

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
        default=None,
        description="List of candidate languages for automatic detection. If not provided, a comprehensive list will be used.",
        example=["zh-CN", "en-US", "ja-JP"]
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
        default=False,
        description="Enable multilingual detection for mixed-language audio",
        example=False
    )

def download_audio_file(url: str) -> bytes:
    """下载音频文件并返回字节数据"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio from URL: {str(e)}")

def get_default_candidate_locales() -> List[str]:
    """获取默认的候选语言列表，优化常用语言的检测顺序"""
    return [
        "en-US", "zh-CN", "ja-JP", "es-ES", "fr-FR",
        "de-DE", "pt-BR", "it-IT", "ru-RU", "ko-KR"
    ]

def convert_audio_to_wav(audio_data: bytes) -> str:
    """
    将下载的音频数据（如MP3）正确转码为WAV格式并保存到临时文件。
    这是修复 SPXERR_INVALID_HEADER 错误的关键。
    """

    try:
        # 使用pydub从内存中的字节数据加载音频
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
        # 音频增强：降噪处理
        audio_array = np.array(audio_segment.get_array_of_samples())
        audio_array = audio_array.astype(np.float32)
        reduced_noise = nr.reduce_noise(y=audio_array, sr=audio_segment.frame_rate)
        audio_segment = AudioSegment(
            reduced_noise.astype(np.int16).tobytes(),
            frame_rate=audio_segment.frame_rate,
            sample_width=audio_segment.sample_width,
            channels=audio_segment.channels
        )


        # 确保音频为16kHz单声道，16-bit PCM，这是Azure SDK推荐的格式
        audio_segment = audio_segment.set_frame_rate(16000)
        audio_segment = audio_segment.set_channels(1)
        audio_segment = audio_segment.set_sample_width(2)

        # 创建一个临时文件来保存WAV数据
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav_file:
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
            speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.service_region)
            speech_config.output_format = speechsdk.OutputFormat.Detailed
            speech_config.request_word_level_timestamps()

            if enable_diarization:
                speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EnableSpeakerDiarization, "true")

            audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

            if multilingual_detection:
                if not candidate_locales:
                    candidate_locales = get_default_candidate_locales()

                    # --- 关键优化：设置此属性以提高多语言识别准确性 ---
                if hasattr(speechsdk.PropertyId, 'SpeechServiceConnection_ContinuousLanguageIdPriority'):
                    # --- 关键优化：设置此属性以提高多语言识别准确性 ---
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

                # --- 逻辑优化结束 ---

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

@app.post("/transcribe", summary="Real-time Transcribe Audio from URL with Language Detection")
def create_realtime_transcription(input_data: AudioInput):
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

        # 1. 下载音频文件
        audio_data = download_audio_file(input_data.audio_url)

        # 2. 使用Real-time Transcription API进行转录
        transcription_result = transcribe_with_realtime_api(
            audio_data=audio_data,
            language=input_data.language,
            candidate_locales=input_data.candidate_locales,
            enable_diarization=input_data.enable_diarization,
            multilingual_detection=input_data.multilingual_detection
        )

        # 3. 根据是否启用多语言检测处理结果
        if input_data.multilingual_detection and not input_data.language:
            # 多语言模式
            transcribed_text, detected_languages, language_details = extract_multilingual_info(transcription_result)

            return {
                "asr_text": transcribed_text,
                "language_specified": input_data.language,
                "languages_detected": detected_languages,
                "language_timeline": transcription_result.get("multilingual_segments", []),
                "language_detection_details": language_details,
                "candidate_locales_used": input_data.candidate_locales or get_default_candidate_locales(),
                "auto_detection_used": input_data.language is None,
                "language_identification_mode": input_data.language_identification_mode,
                "service": "azure_realtime_transcription",
                "enhanced_detection": True,
                "multilingual_mode": True,
                "total_segments": transcription_result.get("total_segments", 1),
                "raw_result": transcription_result
            }
        else:
            # 单语言模式
            transcribed_text, detected_language, language_details = extract_text_and_language_info(transcription_result)

            # 5. 返回增强的结果
            return {
                "asr_text": transcribed_text,
                "language_specified": input_data.language,
                "language_detected": detected_language,
                "language_detection_details": language_details,
                "candidate_locales_used": input_data.candidate_locales or get_default_candidate_locales() if not input_data.language else None,
                "auto_detection_used": input_data.language is None,
                "language_identification_mode": input_data.language_identification_mode if not input_data.language else None,
                "service": "azure_realtime_transcription",
                "enhanced_detection": True,
                "multilingual_mode": False,
                "raw_result": transcription_result
            }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/supported-languages")
def get_supported_languages():
    """获取支持的语言列表"""
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
        "message": "Azure Real-time Transcription Service with Enhanced Language Identification & Multilingual Support",
        "version": "5.0",
        "docs": "/docs",
        "health": "/health",
        "supported_languages": "/supported-languages"
    }

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """上传音频文件并返回临时访问URL"""
    try:
        temp_dir = "temp_audio"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"url": f"http://localhost:8000/audio/{file.filename}", "expires": "1 hour"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """提供音频文件访问"""
    file_path = os.path.join("temp_audio", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="audio/mpeg")
