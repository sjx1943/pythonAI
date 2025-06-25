import sys
from pathlib import Path

# 将项目根目录添加到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from asr_main import app  # 现在可以直接导入
from mangum import Mangum

handler = Mangum(app)

def lambda_handler(event, context):
    return handler(event, context)