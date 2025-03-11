from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Agent Service Configuration
    AGENT_SERVICE_HOST: str = "25.90.181.163"  # 智能体服务地址
    AGENT_SERVICE_BASE_PATH: str = "/xlm-gateway-qvpcwi/sfm-api-gateway/gateway/agent/api"  # 基础路径
    APP_KEY: str = "BZABwYDB8mJbr0z9PCBjeRvK0apPgw0n"  # APP_KEY
    AGENT_CODE: str = "9a51d16c-34f6-48b5-b785-d28e876cf13c"  # 智能体编码
    AGENT_VERSION: str = ""  # 智能体版本（可选）
    
    # API Configuration
    API_KEY_FILE: str = "data/api_keys.json"  # API密钥存储文件
    
    # OpenAI API Compatible Configuration
    MODEL_NAME: str = "xc-pc-agent"  # 模型名称
    MAX_TOKENS: int = 4096  # 最大token数
    TEMPERATURE: float = 0.7  # 温度参数
    
    class Config:
        env_file = ".env"

settings = Settings() 