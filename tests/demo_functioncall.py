import json

from zhipuai import ZhipuAI
client = ZhipuAI(api_key="f91c87d6b19446c3a5f7452e99dd1c3f.rFUZxLlrv5Cq2p68")
messages = []
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_flight_number",
            "description": "根据始发地、目的地和日期查询对应日期的航班号",
            "parameters": {
                "type": "object",
                "properties": {
                    "departure": {
                        "description": "始发地，例如北京、上海等",
                        "type": "string"
                    },
                    "destination": {
                        "description": "目的地，例如北京、上海等",
                        "type": "string"
                    },
                    "date": {
                        "description": "日期，例如2023-09-01",
                        "type": "string"
                    }
                },
                "required": ["departure", "destination", "date"]
            },

        }

    },{
        "type": "function",
        "function": {
            "name": "get_ticket_price",
                "description": "查询某航班在某日的票价",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "flight_number": {
                            "description": "航班号，例如CZ1234",
                            "type": "string"
                        },
                        "date": {
                            "description": "日期，例如2023-09-01",
                            "type": "string"
                        }
                    },
                    "required": ["flight_number", "date"]
                },
        }

    },

]




def get_flight_number(departure:str, destination:str, date:str):
    # 模拟查询航班号的逻辑
    flight_map = {
        "北京": {
            "上海": {
                "2023-09-01": "CZ1234",
                "2023-09-02": "CZ1235"
            },
            "广州": {
                "2023-09-01": "CZ1236",
                "2023-09-02": "CZ1237"
            }
        },
        "广州": {
            "上海"
                "2023-09-01": "CZ1238",
                "2023-09-05": "CZ1239"
            }
        }
    try:
        flight_number = flight_map[departure][destination][date]
        return {"flight_number":flight_number}
    except KeyError:
        return {"error": "没有找到对应的航班号，请检查输入的始发地、目的地和日期是否正确"}

def get_ticket_price(flight_number:str, date:str):
    # 模拟查询票价的逻辑
    price_map = {
        "CZ1234": {
            "2023-09-01": 1000,
            "2023-09-02": 1100
        },
        "CZ1235": {
            "2023-09-01": 1200,
            "2023-09-02": 1300
        },
        "CZ1236": {
            "2023-09-01": 900,
            "2023-09-02": 1000
        },
        "CZ1237": {
            "2023-09-01": 1100,
            "2023-09-02": 1200
        },
        "CZ1238": {
            "2023-09-01": 1300,
            "2023-09-02": 1400
        },
        "CZ1239": {
            "2023-09-01": 1500,
            "2023-09-05": 1600
        }
    }
    try:
        price = price_map[flight_number][date]
        return {"price":price}
    except KeyError:
        return {"error": "抱歉，暂无法查询您需要的航班票价信息，请稍后再试。"}


def parse_response(model_response,messages):
    # 第一步处理函数调用结果，根据模型返回参数，调用对应函数
    # 第二步调用函数返回结果构造tool消息，再次调用模型，将函数函数结果输入模型
    # 第三步模型将函数调用结果以自然语言的形式返回给用户

    if model_response.choices[0].message.tool_calls:
        tool_call = model_response.choices[0].message.tool_calls[0]
        function_args = tool_call.function.arguments
        function_result = {}
        if tool_call.function.name == "get_flight_number":
            function_result = get_flight_number(**json.loads(function_args))
        if tool_call.function.name == "get_ticket_price":
            function_result = get_ticket_price(**json.loads(function_args))
        messages.append({"role": "tool",
                         "content": f"{json.dumps(function_result)}",
                         "tool_call_id": tool_call.id
                         })
        response = client.chat.completions.create(
            messages=messages,
            model="glm-4",
            tools=tools,
        )
        print(response.choices[0].message)
        messages.append(response.choices[0].message.model_dump())  # 7. 保存响应到对话历史

messages.append({"role": "system", "content": "不要假设或猜测传入函数的参数值。如果用户的描述不明确，请用户提供必要的信息。"})
messages.append({"role": "user", "content": "查询2023年9月份北京到上海的航班"})
# messages.append({"role": "user", "content": "这趟航班的价格是多少？"})
response = client.chat.completions.create(
    messages=messages,
    model="glm-4",
    tools=tools,)
print(response.choices[0].message)
messages.append(response.choices[0].message.model_dump())  # 7. 保存响应到对话历史
parse_response(response,messages)