import time
import uuid
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, AsyncGenerator
import json
import asyncio
import os
from pydantic import BaseModel
from starlette.background import BackgroundTask


from api.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    ChatCompletionUsage,
    ErrorResponse
)
from utils.agent_client import agent_client
from utils.key_manager import key_manager
from config import settings

app = FastAPI(title="Bright LLM Agent API")

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# 用于存储会话状态
sessions = {}

def get_api_key(authorization: Optional[str] = Header(None)) -> str:
    """从请求头中获取API密钥"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Missing or invalid API key"}}
        )
    return authorization.replace("Bearer ", "")

@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    """OpenAI兼容的聊天完成接口"""
    api_key = get_api_key(authorization)
    if not key_manager.validate_key(api_key):
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Invalid API key"}}
        )

    user_id = key_manager.get_user_id(api_key)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Invalid API key"}}
        )

    # 获取用户的最后一条消息
    last_message = request.messages[-1].content

    # 检查是否需要新建会话
    print(f'用户对话列表长度为：{len(request.messages)}')
    if user_id not in sessions or len(request.messages) == 1:
        if user_id in sessions:
            # 清理旧会话
            agent_client.clean_session(sessions[user_id])
        # 创建新会话
        session_id = agent_client.create_session()
        sessions[user_id] = session_id
    
    async def cleanup_session():
        """清理会话资源的异步函数"""
        try:
            if user_id in sessions:
                await agent_client.clean_session(sessions[user_id])
        except Exception as e:
            print(f"Error cleaning up session: {e}")

    async def generate_stream():
        response_stream = None
        try:
            # 调用智能体获取流式响应
            response_stream = await agent_client.call_agent(
                message=last_message,
                session_id=sessions[user_id]
            )

            for line in response_stream:
                if line:
                    try:
                        line = line.decode('utf-8')
                        if line.startswith('data:'):
                            data = line[5:].strip()
                            if data:
                                try:
                                    agent_response = json.loads(data)
                                    if agent_response.get("object") == "message.delta":
                                        # 转换为 OpenAI 格式
                                        content = ""
                                        for item in agent_response.get("content", []):
                                            if item.get("type") == "text":
                                                content = item.get("text", {}).get("value", "")
                                        
                                        response = {
                                            "id": f"chatcmpl-{str(uuid.uuid4())}",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": settings.MODEL_NAME,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {
                                                        "role": "assistant",
                                                        "content": content
                                                    },
                                                    "finish_reason": None if not agent_response.get("end") else "stop"
                                                }
                                            ]
                                        }
                                        yield f"data: {json.dumps(response)}\n\n"
                                except json.JSONDecodeError:
                                    continue
                    except Exception as e:
                        print(f"Error processing stream data: {e}")
                        break

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except asyncio.CancelledError:
            print("Stream generation cancelled by client disconnection")
            raise
        except Exception as e:
            print(f"Error in stream generation: {e}")
            error_response = {
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": 500
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"
        finally:
            if response_stream:
                try:
                    response_stream.close()
                except Exception as e:
                    print(f"Error closing response stream: {e}")

    if request.stream:
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            background=BackgroundTask(cleanup_session)
        )
    else:
        # 非流式响应
        response_text = ""
        try:
            async for chunk in generate_stream():
                if chunk.startswith("data: "):
                    data = json.loads(chunk[6:].strip())
                    if "choices" in data:
                        content = data["choices"][0].get("delta", {}).get("content", "")
                        if content:
                            response_text += content
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={"error": {"message": str(e)}}
            )

        return ChatCompletionResponse(
            id=f"chatcmpl-{str(uuid.uuid4())}",
            created=int(time.time()),
            model=settings.MODEL_NAME,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=response_text
                    ),
                    finish_reason="stop"
                )
            ],
            usage=ChatCompletionUsage()
        )

@app.get("/api/generate/apikey/{user_id}")
async def generate_api_key(user_id: str):
    """生成API密钥"""
    try:
        api_key = key_manager.generate_key(user_id)
        return JSONResponse(
            content={"api_key": api_key},
            status_code=200
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": str(e)}}
        )

@app.get("/")
async def read_root():
    """返回 Web 界面"""
    return FileResponse('web/templates/index.html')

class ValidateKeyRequest(BaseModel):
    api_key: str

@app.post("/api/validate-key")
async def validate_key(request: ValidateKeyRequest):
    """验证 API Key"""
    try:
        user_id = key_manager.get_user_id(request.api_key)
        return JSONResponse(
            content={
                "valid": user_id is not None,
                "user_id": user_id
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": str(e)}}
        )

if __name__ == "__main__":
    import uvicorn
    print('====启动光明大模型智能体后端服务=====')
    print('====桌面运维知识库API已启动，可通过UOS AI调用=====')

    uvicorn.run(app, host="0.0.0.0", port=8001) 
    