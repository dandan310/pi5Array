#!/usr/bin/env python3
# 摄像头节点启动脚本
import sys
import os

# 添加项目路径到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入节点客户端
from camera_node.node_client import main
import asyncio

if __name__ == "__main__":
    print("启动树莓派摄像头节点...")
    print("支持自动发现主控制器和自动分配节点ID")
    asyncio.run(main())