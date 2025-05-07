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


# 添加一个字典来存储用户ID与conversation_id和chat_id的映射关系
user_conversations = {}  # 格式: {user_id: {"conversation_id": xxx, "chat_id": xxx}}


# 修改chat_and_get_content_stream函数，捕获conversation_id和chat_id
def chat_and_get_content_stream(message, user_id="user_" + os.urandom(4).hex()):
    """流式生成器：每收到一段content就yield出去，实现Gradio页面边生成边显示"""
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
        conversation_id = None
        chat_id = None

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

                # 捕获conversation_id和chat_id
                if "id" in chunk and "conversation_id" in chunk:
                    conversation_id = chunk.get("conversation_id")
                    chat_id = chunk.get("id")
                    # 保存用户的conversation信息
                    if user_id and conversation_id and chat_id:
                        user_conversations[user_id] = {
                            "conversation_id": conversation_id,
                            "chat_id": chat_id
                        }
                        print(f"已保存用户 {user_id} 的会话信息: {user_conversations[user_id]}")

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


# 修改获取历史消息的函数
def get_conversation_history(user_id):
    """获取用户的对话历史"""
    if user_id not in user_conversations:
        print(f"未找到用户 {user_id} 的会话信息")
        # 先创建一个会话
        conversation_id = create_conversation(user_id)
        if not conversation_id:
            return []

    conversation_data = user_conversations[user_id]
    conversation_id = conversation_data.get("conversation_id")
    chat_id = conversation_data.get("chat_id")

    if not conversation_id or not chat_id:
        print(f"用户 {user_id} 的会话ID不完整")
        return []

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        url = f"{API_URL}/v3/chat/message/list"
        params = {
            "conversation_id": conversation_id,
            "chat_id": chat_id
        }

        print(f"请求历史消息URL: {url}, 参数: {params}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        # 处理消息数据
        messages = data.get("data", [])
        if not isinstance(messages, list):
            print("意外的消息格式:", messages)
            return []

        # 转换为Gradio chatbot格式 [(user_msg, bot_msg), ...]
        history = []
        user_messages = {}  # 用于存储用户消息 {id: content}

        # 首先收集所有用户消息
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                user_messages[msg.get("id")] = msg.get("content")

        # 然后处理助手消息，只保留类型为"answer"的消息
        for msg in messages:
            if (msg.get("role") == "assistant" and
                    msg.get("type") == "answer" and
                    msg.get("content")):
                # 找到对应的用户消息（简单匹配最近的一条）
                user_content = "用户提问"  # 默认占位
                if user_messages:
                    user_content = list(user_messages.values())[-1]
                    user_messages.popitem()  # 移除已匹配的用户消息

                history.append([user_content, msg.get("content")])

        return history
    except Exception as e:
        print(f"获取历史消息失败: {str(e)}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应内容: {response.text}")
        return []


# 对话历史界面中增加显示当前会话ID的信息
def load_history(user_id):
    if not user_id.strip():
        return [], gr.update(visible=True, value="请输入用户ID后再加载历史")

    history = get_conversation_history(user_id)

    # 如果用户有会话信息，显示会话ID
    if user_id in user_conversations:
        conv_info = f"会话ID: {user_conversations[user_id].get('conversation_id')}\n"
        conv_info += f"聊天ID: {user_conversations[user_id].get('chat_id')}"
        return history, gr.update(visible=True, value=conv_info)

    return history, gr.update(visible=False)

# 添加会话创建功能
def create_conversation(user_id):
    """创建新会话"""
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "title": f"用户{user_id}的会话",  # 自定义会话标题
            "first_message": "您好，我是您的商务日语助手，有什么可以帮您的吗？"  # 可选的首条消息
        }

        url = f"{API_URL}/v1/conversation/create"
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        # 修改这里：正确获取会话ID
        if result.get("code") == 0 and result.get("data"):
            # 从data.id中获取会话ID，而不是data.conversation_id
            conversation_id = result["data"].get("id")
            # 储存会话ID
            if conversation_id:
                if user_id not in user_conversations:
                    user_conversations[user_id] = {}
                user_conversations[user_id]["conversation_id"] = conversation_id
                print(f"已为用户 {user_id} 创建新会话: {conversation_id}")
                return conversation_id

        print(f"创建会话失败，响应: {result}")
        return None
    except Exception as e:
        print(f"创建会话出错: {str(e)}")
        return None


def verify_conversation(conversation_id):
    """验证会话是否有效，接受API可能返回的不同会话ID"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        url = f"{API_URL}/v1/conversation/info"
        params = {"conversation_id": conversation_id}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            result = response.json()
            # 即使返回的会话ID与请求不同，只要API响应成功就认为有效
            if result.get("code") == 0:
                return True
        return False
    except Exception as e:
        print(f"验证会话有效性出错: {str(e)}")
        return False


def send_message_and_update(user_id, message, history):
    """发送新消息并实时更新对话历史"""
    if not user_id.strip():
        error_message = "❌ 请先输入用户ID"
        history.append([message, error_message])
        yield history
        return

    history.append([message, ""])
    yield history

    try:
        # 尝试使用已有会话ID
        conversation_id = None
        if user_id in user_conversations:
            conversation_id = user_conversations[user_id].get("conversation_id")

        # 若没有可用会话ID则创建新会话
        if not conversation_id:
            conversation_id = create_conversation(user_id)
            if not conversation_id:
                error_message = "❌ 创建会话失败"
                history[-1][1] = error_message
                yield history
                return

        # 发送消息请求
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "bot_id": BOT_ID,
            "user_id": user_id,
            "conversation_id": conversation_id,
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
        api_conversation_id = None

        for raw_line in response.iter_lines(decode_unicode=True):
            # 解析返回的数据行
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("data:"):
                try:
                    json_part = line[len("data:"):].strip()
                    chunk = json.loads(json_part)

                    # 保存API返回的会话ID
                    if "conversation_id" in chunk:
                        api_conversation_id = chunk["conversation_id"]
                        # 如果API返回的会话ID与当前不同，更新为API的值
                        if api_conversation_id != conversation_id:
                            print(f"会话ID从 {conversation_id} 更新为 {api_conversation_id}")
                            conversation_id = api_conversation_id

                        # 更新用户会话信息
                        if "id" in chunk:
                            update_user_conversation(user_id, {
                                "conversation_id": api_conversation_id,
                                "chat_id": chunk["id"]
                            })

                    # 处理内容
                    content_piece = chunk.get("content", "")
                    if content_piece and not is_system_message(content_piece):
                        decoded_piece = safe_decode(content_piece)
                        full_content += decoded_piece
                        history[-1][1] = full_content
                        yield history
                except Exception as e:
                    print(f"解析JSON出错: {str(e)}, 行: {line}")
            else:
                print(f"DEBUG 非data行跳过: {line}")

        if not full_content:
            print("DEBUG 流式响应中未获取到有效内容")
            history[-1][1] = "❌ 未收到有效回复内容。"
            yield history

    except Exception as e:
        error_message = f"❌ 处理失败: {str(e)}"
        if 'response' in locals() and hasattr(response, 'text'):
            error_message += f"\n响应内容: {response.text}"
        print(error_message)
        history[-1][1] = error_message
        yield history

def update_user_conversation(user_id, conversation_data):
    """更新用户会话信息"""
    # 只更新提供的字段，保留其他已有信息
    if user_id not in user_conversations:
        user_conversations[user_id] = {}

    user_conversations[user_id].update(conversation_data)

    print(f"已保存用户 {user_id} 的会话信息: {user_conversations[user_id]}")

    # 保存到持久化存储中
    try:
        with open('user_conversations.json', 'w') as f:
            json.dump(user_conversations, f)
    except Exception as e:
        print(f"保存用户会话信息失败: {str(e)}")

# Gradio界面
with gr.Blocks(title="Coze AI 对话") as demo:
    with gr.Tabs():
        # 第一个Tab: 原始单次对话界面
        with gr.Tab("单次对话"):
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
                yield from chat_and_get_content_stream(message, uid)


            chat_btn.click(
                wrapper,
                inputs=[message, user_id],
                outputs=output,
                api_name="chat_stream",
                show_progress=True,
            )

        # 第二个Tab: 新增的对话历史界面
        with gr.Tab("对话历史"):
            gr.Markdown("## 💬 Coze AI 持续对话（带历史记录）")

            with gr.Row():
                chat_user_id = gr.Textbox(label="用户ID", placeholder="输入固定用户ID以保持会话连续", value="")
                load_history_btn = gr.Button("加载历史消息")

            # 对话历史显示区域
            chatbot = gr.Chatbot(label="对话历史", height=500, elem_id="chat_history")

            with gr.Row():
                chat_input = gr.Textbox(
                    label="发送消息",
                    placeholder="请输入你想问的问题...",
                    lines=3,
                    interactive=True,
                )
                chat_send = gr.Button("发送")

            # 清空历史按钮
            clear_btn = gr.Button("清空聊天记录")


            # 加载历史消息
            def load_history(user_id):
                if not user_id.strip():
                    return [], gr.update(visible=True, value="请输入用户ID后再加载历史")
                return get_conversation_history(user_id), gr.update(visible=False)


            # 在加载历史按钮后添加
            conv_info = gr.Textbox(label="会话信息", visible=False, interactive=False)

            # 修改事件绑定
            load_history_btn.click(
                load_history,
                inputs=[chat_user_id],
                outputs=[chatbot, conv_info]
            )

            chat_send.click(
                send_message_and_update,
                inputs=[chat_user_id, chat_input, chatbot],
                outputs=chatbot,
            ).then(lambda: "", None, chat_input)  # 发送后清空输入框

            chat_input.submit(
                send_message_and_update,
                inputs=[chat_user_id, chat_input, chatbot],
                outputs=chatbot,
            ).then(lambda: "", None, chat_input)  # 回车发送也清空输入框

            # 清空聊天记录
            clear_btn.click(lambda: [], None, chatbot)

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