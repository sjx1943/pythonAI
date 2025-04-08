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


                    }
                }

            }

        }

    },{}


]


#
# vn.ask('sgg上传的商品中，在售商品的数量有多少？')
# from vanna.flask import VannaFlaskApp
# VannaFlaskApp(vn).run()


