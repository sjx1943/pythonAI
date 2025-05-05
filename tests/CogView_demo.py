from zhipuai import ZhipuAI
client = ZhipuAI(api_key="f91c87d6b19446c3a5f7452e99dd1c3f.rFUZxLlrv5Cq2p68")

response = client.images.generations(
    model="cogview-3",
    prompt="a cat sitting on a chair",
)

print(response.data[0].url)