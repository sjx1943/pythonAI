#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import gradio as gr
import requests

API_URL = "https://api.coze.cn"
API_KEY = os.getenv("COZE_API_KEY", "pat_ReVpP7tKqIelQf8qRFeOzr6GQyMz6oUHdXTBW")
BOT_ID = os.getenv("COZE_BOT_ID", "749824733324745")

user_conversations = {}

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
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        # 获取或创建会话ID
        conversation_id = None
        if user_id in user_conversations:
            conversation_id = user_conversations[user_id].get("conversation_id")

        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "stream": True,
            "auto_save_history": True,
            "additional_messages": [{
                "role": "user",
                "content": message,
                "content_type": "text",
                "type": "question"
            }]
        }

        if conversation_id:
            data["conversation_id"] = conversation_id

        response = requests.post(f"{API_URL}/v3/chat", headers=headers, json=data, stream=True, timeout=60)
        response.raise_for_status()

        full_content = ""
        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("data:"):
                json_part = line[len("data:"):].strip()
                if json_part == "[DONE]":
                    break

                try:
                    if not json_part.endswith("}"):
                        json_part = json_part + "}"
                    chunk = json.loads(json_part)

                    # 保存会话ID
                    if "conversation_id" in chunk:
                        conversation_id = chunk["conversation_id"]
                        if user_id not in user_conversations:
                            user_conversations[user_id] = {}
                        user_conversations[user_id]["conversation_id"] = conversation_id

                    content_piece = chunk.get("content", "")
                    if content_piece and not is_system_message(content_piece):
                        full_content += safe_decode(content_piece)
                        yield full_content

                except Exception as e:
                    print(f"解析JSON出错: {str(e)}")
                    continue

        if not full_content:
            yield "❌ 未收到有效回复内容。"

    except Exception as e:
        yield f"❌ 处理失败: {str(e)}"

def init_conversation(user_id):
    if not user_id.strip():
        return [], gr.update(visible=True, value="请输入用户ID后再初始化会话")

    if user_id in user_conversations and user_conversations[user_id].get("conversation_id"):
        conv_id = user_conversations[user_id]["conversation_id"]
        if verify_conversation(conv_id):
            history = get_conversation_history(user_id)
            conv_info = f"会话ID: {conv_id}"
            return history, gr.update(visible=True, value=conv_info)

    conv_id = create_conversation(user_id)
    if not conv_id:
        return [], gr.update(visible=True, value="创建会话失败")

    welcome_msg = send_welcome_message(user_id, conv_id)
    history = [{"role": "assistant", "content": welcome_msg}] if welcome_msg else []
    return history, gr.update(visible=True, value=f"会话ID: {conv_id}")

def get_conversation_history(user_id):
    if user_id not in user_conversations:
        return []

    conversation_id = user_conversations[user_id].get("conversation_id")
    if not conversation_id:
        return []

    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.get(
            f"{API_URL}/v1/chat/message/list",
            headers=headers,
            params={"conversation_id": conversation_id}
        )
        response.raise_for_status()
        data = response.json()

        messages = data.get("data", {}).get("items", [])
        messages.sort(key=lambda x: x.get("create_time", 0))

        formatted_history = []
        pending_user_msg = None

        for msg in messages:
            if msg.get("role") == "user":
                pending_user_msg = msg.get("content")
            elif msg.get("role") == "assistant":
                if pending_user_msg:
                    formatted_history.extend([
                        {"role": "user", "content": pending_user_msg},
                        {"role": "assistant", "content": msg.get("content")}
                    ])
                    pending_user_msg = None
                else:
                    formatted_history.append({"role": "assistant", "content": msg.get("content")})

        if pending_user_msg:
            formatted_history.append({"role": "user", "content": pending_user_msg})

        return formatted_history
    except Exception:
        return []

def create_conversation(user_id):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "title": f"用户{user_id}的会话"
        }

        response = requests.post(f"{API_URL}/v1/conversation/create", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 0 and result.get("data"):
            conversation_id = result["data"].get("id")
            if conversation_id:
                user_conversations[user_id] = {"conversation_id": conversation_id}
                return conversation_id
        return None
    except Exception:
        return None

def verify_conversation(conversation_id):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.get(
            f"{API_URL}/v1/conversation/info",
            headers=headers,
            params={"conversation_id": conversation_id}
        )
        return response.status_code == 200 and response.json().get("code") == 0
    except Exception:
        return False

def send_welcome_message(user_id, conversation_id):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "您好，今天想练习什么口语？",
            "content_type": "text",
            "type": "answer"
        }

        response = requests.post(f"{API_URL}/v1/chat/message/create", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result.get("code") == 0 and data["content"]
    except Exception:
        return None

def send_message_and_update(user_id, message, history):
    if not user_id.strip():
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "❌ 请先输入用户ID"})
        yield history
        return

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": ""})
    yield history

    try:
        conversation_id = None
        if user_id in user_conversations:
            conversation_id = user_conversations[user_id].get("conversation_id")

        if not conversation_id:
            conversation_id = create_conversation(user_id)
            if not conversation_id:
                history[-1]["content"] = "❌ 创建会话失败"
                yield history
                return

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "stream": True,
            "additional_messages": [{
                "role": "user",
                "content": message,
                "content_type": "text",
                "type": "question"
            }]
        }

        response = requests.post(f"{API_URL}/v3/chat", headers=headers, json=data, stream=True, timeout=60)
        response.raise_for_status()

        full_content = ""
        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line.strip()
            if not line or line == "event:done":
                continue

            if line.startswith("data:"):
                json_part = line[len("data:"):].strip()
                if json_part == "[DONE]":
                    break

                try:
                    if not json_part.endswith("}"):
                        json_part = json_part + "}"
                    chunk = json.loads(json_part)

                    if "conversation_id" in chunk:
                        conversation_id = chunk["conversation_id"]
                        user_conversations[user_id] = {"conversation_id": conversation_id}

                    content_piece = chunk.get("content", "")
                    if content_piece and not is_system_message(content_piece):
                        full_content += safe_decode(content_piece)
                        history[-1]["content"] = full_content
                        yield history

                except Exception:
                    continue

        if not full_content:
            history[-1]["content"] = "❌ 未收到有效回复内容。"
            yield history

    except Exception as e:
        history[-1]["content"] = f"❌ 处理失败: {str(e)}"
        yield history

with gr.Blocks(title="Coze AI 对话") as demo:
    tabs = gr.Tabs()
    with tabs:
        with gr.Tab("单次对话"):
            gr.Markdown("## 🤖 Coze AI 对话接口")
            with gr.Row():
                user_id = gr.Textbox(label="用户ID (可选)", placeholder="留空将自动生成")
                message = gr.Textbox(label="你的消息", placeholder="请输入你想问的问题...", lines=3)
            chat_btn = gr.Button("发送并获取回复")
            output = gr.Textbox(label="AI回复", lines=15, show_copy_button=True)

            def wrapper(message, user_id):
                uid = user_id.strip() or ("user_" + os.urandom(4).hex())
                yield from chat_and_get_content_stream(message, uid)

            chat_btn.click(wrapper, [message, user_id], output)

        with gr.Tab("对话历史"):
            gr.Markdown("## 💬 Coze AI 持续对话")
            with gr.Row():
                chat_user_id = gr.Textbox(label="用户ID", placeholder="输入固定用户ID以保持会话连续")
                load_history_btn = gr.Button("加载历史消息")

            chatbot = gr.Chatbot(label="对话历史", height=500, type="messages")
            conv_info = gr.Textbox(label="会话信息", visible=False)

            with gr.Row():
                chat_input = gr.Textbox(label="发送消息", placeholder="请输入你想问的问题...", lines=3)
                chat_send = gr.Button("发送")

            clear_btn = gr.Button("清空聊天记录")

            load_history_btn.click(
                init_conversation,
                inputs=[chat_user_id],
                outputs=[chatbot, conv_info]
            )

            chat_send.click(
                send_message_and_update,
                inputs=[chat_user_id, chat_input, chatbot],
                outputs=chatbot
            ).then(lambda: "", None, chat_input)

            chat_input.submit(
                send_message_and_update,
                inputs=[chat_user_id, chat_input, chatbot],
                outputs=chatbot
            ).then(lambda: "", None, chat_input)

            clear_btn.click(lambda: [], None, chatbot)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
