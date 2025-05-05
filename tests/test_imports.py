from fastapi import FastAPI

app = FastAPI()

# 假装这是从数据库读取的天气数据
weather_db = {"Beijing": "晴", "Shanghai": "多云"}


@app.get("/weather/{city}")
async def get_weather(city: str):
    return {"city": city, "weather": weather_db.get(city, "未知")}


@app.post("/weather/update")
async def update_weather(city: str, new_weather: str):
    weather_db[city] = new_weather
    return {"message": "天气数据已更新，但重启服务后会消失哦~"}