# 启动脚本
# 用于启动FastAPI后端服务

import sys
import uvicorn
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.config import config


def main():
    """启动服务"""
    uvicorn.run(
        "app.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
