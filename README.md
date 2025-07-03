# 实时语音转写服务

本服务提供基于 Azure 的实时语音转写功能，支持多语言识别和说话人分离等特性。以下是接口测试命令及功能说明。

## 接口测试命令

你可以使用 `curl` 命令来测试实时转写接口，示例如下：

```bash
curl -X POST "http://localhost:8002/real-time-transcribe" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "audio_url": "https://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0019_8k.wav",
  "language": null,
  "candidate_locales": [
    "zh-CN", 
    "ja-JP",
    "en-US",
    "es-ES"
  ],
  "enable_diarization": false,
  "language_identification_mode": "Continuous",
  "multilingual_detection": true
}'