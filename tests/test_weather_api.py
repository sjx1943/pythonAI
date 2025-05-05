import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from test_imports import app, weather_db

class TestWeatherAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        weather_db.clear()  # 清空测试数据库
    
    def test_get_weather_unknown_city(self):
        response = self.client.get("/weather/unknown_city")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"city": "unknown_city", "weather": "未知"})
    
    def test_get_weather_known_city(self):
        weather_db["beijing"] = "晴天"
        response = self.client.get("/weather/beijing")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"city": "beijing", "weather": "晴天"})
    
    @patch('test_imports.weather_db', {})
    def test_update_weather(self):
        response = self.client.post(
            "/weather/update",
            params={"city": "shanghai", "new_weather": "多云"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "天气数据已更新，但重启服务后会消失哦~"})
        self.assertEqual(weather_db.get("shanghai"), "多云")
    
    def test_update_and_get_weather_flow(self):
        # 测试完整的更新后获取流程
        update_response = self.client.post(
            "/weather/update",
            params={"city": "guangzhou", "new_weather": "雷阵雨"}
        )
        self.assertEqual(update_response.status_code, 200)
        
        get_response = self.client.get("/weather/guangzhou")
        self.assertEqual(get_response.json(), {"city": "guangzhou", "weather": "雷阵雨"})

if __name__ == '__main__':
    unittest.main()
