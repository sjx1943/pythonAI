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
        """确保密钥文件存在且包含有效的 JSON"""
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        if not os.path.exists(self.key_file):
            # 创建新文件并写入空的 JSON 对象
            with open(self.key_file, 'w') as f:
                json.dump({}, f, indent=2)

    def _load_keys(self) -> Dict[str, str]:
        """加载密钥"""
        try:
            with open(self.key_file, 'r') as f:
                content = f.read().strip()
                if not content:  # 如果文件为空
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            # 如果 JSON 解析失败，重置为空对象
            with open(self.key_file, 'w') as f:
                json.dump({}, f, indent=2)
            return {}

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