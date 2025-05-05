#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
from math import trunc
import time
import gradio as gr
import requests

API_URL = "https://api.coze.cn"
API_KEY = os.getenv("COZE_API_KEY", "pat_ReVpP7tKqIelQf8qRFeOzr6GQyMz6oUHCAwEt96EUVqIKvnxyKpRiuot5e4dXTBW")
BOT_ID = os.getenv("COZE_BOT_ID", "7498247331134324745")

def safe_decode(content):
    try:
        return content.encode('latin1').decode('utf-8')
    except Exception:
        return content

def is_system_message(text):
    try:
        obj = json.loads(text)
        return isinstance(obj, dict) and "msg_type" in obj
    except Exception:
        return False

def chat_and_get_content_stream(message, user_id="user_" + os.urandom(4).hex()):
    """
    流式生成器：每收到一段content就yield出去，实现Gradio页面边生成边显示
    """
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "stream": True,
            "auto_save_history": True,
            "additional_messages": [
                {
                    "role": "user",
                    "content": message,
                    "content_type": "text",
                    "type": "question"
                }
            ]
        }

        response = requests.post(f"{API_URL}/v3/chat", headers=headers, json=data, stream=True, timeout=60)
        response.raise_for_status()

        full_content = ""
        status = None
        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                json_part = line[len("data:"):].strip()
                try:
                    chunk = json.loads(json_part)
                except Exception as e:
                    print(f"DEBUG 非法json跳过: {line}，异常: {e}")
                    continue

                content_piece = chunk.get("content", "")
                if content_piece and not is_system_message(content_piece):
                    decoded_piece = safe_decode(content_piece)
                    full_content += decoded_piece
                    yield full_content  # 每次yield当前累计内容
                elif content_piece:
                    print(f"DEBUG 系统消息跳过: {content_piece}")

                status = chunk.get("status")
                if status == "completed":
                    print("DEBUG status completed，停止读取流")
                    break
            else:
                print(f"DEBUG 非data行跳过: {line}")

        if not full_content:
            print("DEBUG 流式响应中未获取到有效内容")
            yield "❌ 未收到有效回复内容。"

    except Exception as e:
        err_msg = f"❌ 处理失败: {str(e)}"
        if 'response' in locals() and hasattr(response, 'text'):
            err_msg += f"\n响应内容: {response.text}"
        print(err_msg)
        yield err_msg

# Gradio界面
with gr.Blocks(title="Coze AI 对话") as demo:
    gr.Markdown("## 🤖 Coze AI 对话接口（流式响应，边生成边显示）")

    with gr.Row():
        user_id = gr.Textbox(label="用户ID (可选)", placeholder="留空将自动生成", value="")
        message = gr.Textbox(
            label="你的消息",
            placeholder="请输入你想问的问题...",
            lines=3,
            interactive=True,
        )

    chat_btn = gr.Button("发送并获取回复")
    output = gr.Textbox(
        label="AI回复",
        lines=15,
        placeholder="AI回复将显示在这里...",
        interactive=False,
        show_copy_button=True,
    )

    def wrapper(message, user_id):
        uid = user_id.strip() or ("user_" + os.urandom(4).hex())
        # 将返回生成器改为使用yield from迭代生成器
        yield from chat_and_get_content_stream(message, uid)

    chat_btn.click(
        wrapper,
        inputs=[message, user_id],
        outputs=output,
        api_name="chat_stream",
        show_progress=True,
    )

if __name__ == "__main__":
    debug_mode = True
    if not API_KEY:
        print("⚠️ 警告：未设置COZE_API_KEY环境变量或直接在代码中配置API_KEY")
    if not BOT_ID:
        print("⚠️ 警告：未设置COZE_BOT_ID环境变量或直接在代码中配置BOT_ID")

    demo.launch(
        debug=debug_mode,
        server_name="0.0.0.0",
        server_port=int(os.getenv("COZE_PORT", "7860")),
        share=False,
    )
