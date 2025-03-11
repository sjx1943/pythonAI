import time
import uuid
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, AsyncGenerator
import json
import asyncio

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

    async def generate_stream():
        try:
            # 调用智能体获取流式响应
            response_stream = agent_client.call_agent(
                message=last_message,
                session_id=sessions[user_id]
            )

            for line in response_stream:
                if line:
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

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            error_response = {
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": 500
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"

    if request.stream:
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream"
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


# 添加根URL路由
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Bright LLM Agent API"}


# 添加favicon路由
@app.get("/favicon.ico")
async def read_favicon():
    return JSONResponse(content={}, status_code=204)


if __name__ == "__main__":
    import uvicorn

    print('====启动光明大模型智能体后端服务=====')
    uvicorn.run(app, host="0.0.0.0", port=8001)
    print('====省信通信创运维知识库API已启动，可通过UOS AI调用=====')