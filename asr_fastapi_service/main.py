#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv() # 2. 在使用环境变量之前调用它

AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION")

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="ASR Transcription Service",
    description="A simple API to transcribe audio from a URL using Azure Speech."
)


# --- 定义请求体模型 ---
# Coze插件调用时会发送这样的JSON结构
class AudioInput(BaseModel):
    audio_url: str = Field(
        ...,
        description="The public URL of the audio file to be transcribed.",
        example="https://example.com/path/to/audio.wav"
    )
    language: str = Field(
        default="en-US",
        description="The language of the audio in BCP-47 format (e.g., en-US, zh-CN).",
        example="zh-CN"
    )


# --- 核心转写函数 ---
def transcribe_from_url(url: str, lang: str) -> str:
    """Downloads audio from a URL and transcribes it using Azure Speech SDK."""

    # 1. 下载音频文件到内存
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 在请求中加入 headers
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()  # 检查请求是否成功 (e.g., 200 OK)
        audio_data = response.content
        print(f"Downloaded audio data size: {len(audio_data)} bytes")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio from URL: {e}")

    # 2. 配置Azure Speech SDK
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_recognition_language = lang

    # 从内存中的字节流创建音频配置
    audio_format = speechsdk.audio.AudioStreamFormat(
        compressed_stream_format=speechsdk.audio.AudioStreamContainerFormat.MP3
    )
    stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # 3. 创建识别器并进行识别
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    # 将音频数据推送到流中
    stream.write(audio_data)
    stream.close()
    print("Audio data pushed to the stream and stream closed.")

    # 4. 执行单次识别并获取结果
    print("Starting speech recognition...")
    result = recognizer.recognize_once()
    print(f"Recognition result reason: {result.reason}")

    # 5. 处理识别结果
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech recognized. Check audio content and format.")
        raise HTTPException(status_code=404, detail="No speech could be recognized from the audio.")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"Speech recognition canceled: {cancellation_details.reason}. Error: {cancellation_details.error_details}")
        raise HTTPException(status_code=500,
                            detail=f"Speech Recognition canceled: {cancellation_details.reason}. Error: {cancellation_details.error_details}")
    else:
        print(f"An unknown error occurred during speech recognition. Reason: {result.reason}")
        raise HTTPException(status_code=500,
                            detail=f"An unknown error occurred during speech recognition. Reason: {result.reason}")

# --- API 端点 (Endpoint) ---
@app.post("/transcribe", summary="Transcribe Audio from URL")
def create_transcription(input_data: AudioInput):
    """
    Receives an audio URL, transcribes the speech to text, and returns the result.
    """
    try:
        # 调用核心转写函数
        transcribed_text = transcribe_from_url(input_data.audio_url, input_data.language)
        # 以JSON格式返回结果，这是Coze插件期望的
        return {"asr_text": transcribed_text}
    except HTTPException as e:
        # 捕获并重新抛出HTTP异常
        raise e
    except Exception as e:
        # 捕获其他未知错误
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")