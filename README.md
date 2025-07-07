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
...

也可以用curl 命令来测试快速转写接口,示例如下:
```bash
//通过url转录
curl -X POST "http://localhost:8002/fast-transcribe" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "audio_url=https://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0019_8k.wav" \
  -F "locales=[]"
//通过文件上传转录,示例中音频未见位于同级目录的temp_audio文件夹下
curl -X POST "http://localhost:8002/fast-transcribe" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "audio_file=@\"temp_audio/OSR_us_000_0019_8k.wav\"" \
  -F "locales=[]"
```
为了适配coze的请求体格式，请求体必须是有效的JSON字符串，故重新起了新端点，实现application/json格式的url转录：
```bash
curl -X POST "http://localhost:9000/transcribe-json"   -H "accept: application/json"   -H "Content-Type: application/json"   -d '{
    "audio_url": "https://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0019_8k.wav",
    "locales": "[]"
  }'
```

## 注意事项

音频转换用到了ffmpeg，在mac测试环境下要使用系统自身的ffmpeg：

        # ffmpeg_path = Path(__file__).parent / "static_ffmpeg" / "ffmpeg"
        # if ffmpeg_path.exists():
        #     AudioSegment.converter = str(ffmpeg_path)
        #     logger.info(f"Using bundled ffmpeg from: {ffmpeg_path}")
        # else:
        #     logger.warning("Bundled ffmpeg not found. Relying on system-installed ffmpeg")

        logger.info("Relying on system-installed ffmpeg")
在生产环境是可以引用导入的ffmpeg库，都是基于linux环境：
         ffmpeg_path = Path(__file__).parent / "static_ffmpeg" / "ffmpeg"
         if ffmpeg_path.exists():
             AudioSegment.converter = str(ffmpeg_path)
             logger.info(f"Using bundled ffmpeg from: {ffmpeg_path}")
         else:
             logger.warning("Bundled ffmpeg not found. Relying on system-installed ffmpeg")

        #logger.info("Relying on system-installed ffmpeg")
