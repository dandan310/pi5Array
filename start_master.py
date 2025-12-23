#!/usr/bin/env python3
# 主控制器启动脚本
import sys
import os

# 添加项目路径到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入主控制器
from master_controller.main import main
import asyncio

if __name__ == "__main__":
    print("启动树莓派多角度摄影系统主控制器...")
    asyncio.run(main())