#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import gradio as gr
import requests
import time

API_URL = "https://api.coze.cn"
API_KEY = os.getenv("COZE_API_KEY", "pat_ReVpP7tKqIelQf8qRFeOzr6GQyMz6oUHCAwEt96EUVqIKvnxyKpRiuot5e4dXTBW")
BOT_ID = os.getenv("COZE_BOT_ID", "7498247331134324745")

# 存储用户会话信息：{user_id: {"conversation_id": str, "chat_id": str}}
user_conversations = {}


def safe_decode(content):
    try:
        return content.encode("latin1").decode("utf-8")
    except Exception:
        return content


def is_system_message(text):
    try:
        obj = json.loads(text)
        return isinstance(obj, dict) and "msg_type" in obj
    except Exception:
        return False


def update_user_conversation(user_id, info):
    if user_id not in user_conversations:
        user_conversations[user_id] = {}
    user_conversations[user_id].update(info)
    print(f"已保存用户 {user_id} 的会话信息: {user_conversations[user_id]}")


def create_conversation(user_id, first_message):
    """创建新会话，返回会话ID和初始回复"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 准备创建会话的数据
    data = {
        "meta_data": {
            "uuid": user_id
        },
        "messages": [
            {
                "role": "user",
                "content": first_message or "你好",
                "content_type": "text"
            }
        ]
    }

    try:
        response = requests.post(f"{API_URL}/v1/conversation/create",
                                 headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()

        # 提取会话ID
        conversation_id = result.get("data", {}).get("id")
        if not conversation_id:
            raise Exception("未能获取到会话ID")

        # 返回会话ID和初始回复
        return conversation_id
    except Exception as e:
        print(f"创建会话失败: {str(e)}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应内容: {response.text}")
        raise e


def get_message_by_chat_id(user_id):
    """通过conversation_id获取完整消息内容"""
    user_info = user_conversations.get(user_id, {})
    conversation_id = user_info.get("conversation_id")
    chat_id = user_info.get("chat_id")
    if not conversation_id:
        return None

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(
            f"{API_URL}/v3/chat/message/list?conversation_id={conversation_id}&chat_id={chat_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # 获取最后一条助手消息
        messages = result.get("data", {}).get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content", "")

        return None
    except Exception as e:
        print(f"获取消息详情失败: {str(e)}")
        return None


def send_message_and_update(user_id, message, history):
    if not user_id.strip():
        history.append([message, "❌ 请先输入用户ID"])
        yield history
        return

    # 检查是否是第一次对话（不考虑欢迎消息）
    is_first_message = user_id not in user_conversations or not user_conversations[user_id].get("conversation_id")

    history.append([message, ""])
    yield history
    try:
        # 第一次对话，先创建会话
        if is_first_message:
            conversation_id = create_conversation(user_id, message)
            update_user_conversation(user_id, {"conversation_id": conversation_id})
        else:
            # 使用已有会话ID
            conversation_id = user_conversations[user_id]["conversation_id"]

        # 无论是首次还是后续对话，都通过/v3/chat接口获取真实回复
        for partial in send_message_with_context(user_id, message, conversation_id):
            history[-1][1] = partial
            yield history
    except Exception as e:
        history[-1][1] = f"❌ 处理失败: {e}"
        yield history


def send_message_with_context(user_id, message, conversation_id):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "bot_id": BOT_ID,
        "user_id": user_id,
        #data中不需要出现会话ID，需要在Query中添加
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

    # 记录原始会话ID
    original_conversation_id = conversation_id

    try:
        response = requests.post(f"{API_URL}/v3/chat?conversation_id={conversation_id}", headers=headers, json=data, stream=True, timeout=60)
        response.raise_for_status()

        full_content = ""
        content_received = False
        id_change_attempts = 0  # 计数器，记录尝试改变会话ID的次数

        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("data:"):
                json_part = line[len("data:"):].strip()
                if json_part == "[DONE]":
                    break

                try:
                    chunk = json.loads(json_part)
                except Exception as e:
                    print(f"非法json跳过: {line}, 异常: {e}")
                    continue

                # 仅保存chat_id，不更新conversation_id
                if "id" in chunk and chunk["id"]:
                    update_user_conversation(user_id, {"chat_id": chunk["id"]})

                # 记录但不更新conversation_id，除非真的需要
                if "conversation_id" in chunk and chunk["conversation_id"]:
                    new_conv_id = chunk["conversation_id"]
                    if new_conv_id != original_conversation_id:
                        id_change_attempts += 1
                        print(
                            f"检测到会话ID变化尝试 #{id_change_attempts}: {original_conversation_id} -> {new_conv_id}，但保持原ID不变")

                content_piece = chunk.get("content", "")
                if content_piece and not is_system_message(content_piece):
                    content_received = True
                    try:
                        decoded_piece = safe_decode(content_piece)
                        full_content += decoded_piece
                        yield full_content
                    except Exception as e:
                        print(f"内容解码错误: {e}")

                if chunk.get("status") == "completed":
                    break

        if not content_received:
            print("未接收到流式内容，尝试获取完整回复...")
            time.sleep(1)  # 等待服务器处理
            complete_response = get_message_by_chat_id(user_id)
            if complete_response:
                yield complete_response
            else:
                yield "❌ 未能收到回复，请重试"

    except Exception as e:
        err_msg = f"❌ 处理失败: {str(e)}"
        if 'response' in locals() and hasattr(response, 'text'):
            err_msg += f"\n响应内容: {response.text[:200]}..."
        print(err_msg)
        yield err_msg


with gr.Blocks(title="Coze AI 日语助手", analytics_enabled=False) as demo:
    with gr.Tab("日语对话"):
        gr.Markdown("## 🤖 Coze 日语助手（流式响应、完整上下文）")
        with gr.Row():
            uid = gr.Textbox(label="用户ID (必填)", placeholder="请输入用户ID", value="")
            msg = gr.Textbox(label="你的消息", placeholder="请输入问题...", lines=3, interactive=True)

        with gr.Row():
            send_btn = gr.Button("发送消息")
            clear_btn = gr.Button("清空聊天记录")

        # 初始显示欢迎消息
        chatbot = gr.Chatbot(label="对话框", height=500, value=[[None, "我是您的日语助手，请问有什么可以帮您？"]])

        send_btn.click(send_message_and_update, inputs=[uid, msg, chatbot], outputs=chatbot).then(lambda: "", None, msg)
        msg.submit(send_message_and_update, inputs=[uid, msg, chatbot], outputs=chatbot).then(lambda: "", None, msg)
        clear_btn.click(lambda: [[None, "我是您的日语助手，请问有什么可以帮您？"]], None, chatbot)

if __name__ == "__main__":
    if not API_KEY or not BOT_ID:
        print("⚠️ 请设置环境变量 COZE_API_KEY 和 COZE_BOT_ID 或在代码中配置API_KEY和BOT_ID")
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("COZE_PORT", "7861")), debug=True)