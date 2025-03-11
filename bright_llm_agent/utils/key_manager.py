import json
import os
import uuid
from typing import Dict, Optional
from config import settings

class KeyManager:
    def __init__(self):
        self.key_file = settings.API_KEY_FILE
        self._ensure_key_file()
        self.keys: Dict[str, str] = self._load_keys()

    def _ensure_key_file(self):
        """确保密钥文件存在"""
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        if not os.path.exists(self.key_file):
            with open(self.key_file, 'w') as f:
                json.dump({}, f)

    def _load_keys(self) -> Dict[str, str]:
        """加载密钥"""
        with open(self.key_file, 'r') as f:
            return json.load(f)

    def _save_keys(self):
        """保存密钥"""
        with open(self.key_file, 'w') as f:
            json.dump(self.keys, f, indent=2)

    def generate_key(self, user_id: str) -> str:
        """生成新的API密钥"""
        api_key = f"sk-{str(uuid.uuid4())}"
        self.keys[user_id] = api_key
        self._save_keys()
        return api_key

    def get_user_id(self, api_key: str) -> Optional[str]:
        """通过API密钥获取用户ID"""
        for user_id, key in self.keys.items():
            if key == api_key:
                return user_id
        return None

    def validate_key(self, api_key: str) -> bool:
        """验证API密钥是否有效"""
        return any(key == api_key for key in self.keys.values())

key_manager = KeyManager() 