import requests
from typing import Optional, Dict, Any
from config import settings

class AgentClient:
    def __init__(self):
        self.base_url = f"http://{settings.AGENT_SERVICE_HOST}{settings.AGENT_SERVICE_BASE_PATH}"
        self.headers = {
            "Authorization": f"Bearer {settings.APP_KEY}",
            "Content-Type": "application/json"
        }
        self.current_session: Optional[str] = None

    def create_session(self) -> str:
        """创建新的会话"""
        url = f"{self.base_url}/createSession"
        data = {
            "agentCode": settings.AGENT_CODE,
            "agentVersion": ""
        }
        if settings.AGENT_VERSION:
            data["agentVersion"] = settings.AGENT_VERSION

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        print(result)
        if not result.get("success"):
            raise Exception(f"Failed to create session: {result.get('errorMsg')}")
        
        session_id = result.get("data", {}).get("uniqueCode")
        if not session_id:
            raise Exception("No session ID returned")
        
        self.current_session = session_id
        return session_id

    def clean_session(self, session_id: str) -> bool:
        """清理会话"""
        url = f"{self.base_url}/clearSession"
        response = requests.post(
            url,
            headers=self.headers,
            json={"sessionId": session_id}
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get("success", False)

    def call_agent(self, message: str, session_id: Optional[str] = None):
        """调用智能体"""
        if not session_id and not self.current_session:
            session_id = self.create_session()
        elif not session_id:
            session_id = self.current_session

        url = f"{self.base_url}/run"
        data = {
            "sessionId": session_id,
            "stream": True,  # 使用流式响应
            "delta": True,   # 使用增量响应
            "message": {
                "text": message,
                "metadata": {},
                "attachments": []
            }
        }

        response = requests.post(url, headers=self.headers, json=data, stream=True)
        response.raise_for_status()
        
        return response.iter_lines()

agent_client = AgentClient() 