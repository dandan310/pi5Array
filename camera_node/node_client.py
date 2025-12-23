#!/usr/bin/env python3
# 树莓派5摄像头节点程序
import asyncio
import logging
import signal
import sys
import time
import aiohttp
import json
from camera_handler import CameraHandler
from node_server import NodeServer
from config import NodeConfig
from shared.ntp_sync import ntp_client, scheduled_capture

class CameraNode:
    def __init__(self, node_id: int = None):
        # 先加载配置，如果没有指定node_id则尝试从配置文件加载或自动分配
        if node_id:
            self.config = NodeConfig(node_id=node_id)
        else:
            self.config = NodeConfig.load_config()
        
        self.node_id = self.config.node_id
        self.camera_handler = CameraHandler(self.config)
        self.node_server = NodeServer(self.config, self.camera_handler)
        self.running = False
        self.registered = False
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - Node{self.node_id or "Auto"} - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """启动摄像头节点"""
        self.logger.info(f"启动摄像头节点 {self.node_id or '自动分配ID'}...")
        
        try:
            # 同步NTP时间
            self.logger.info("正在同步NTP时间...")
            if await ntp_client.sync_time():
                self.logger.info(f"NTP时间同步成功，当前时间: {ntp_client.format_time()}")
            else:
                self.logger.warning("NTP时间同步失败，使用本地时间")
            
            # 如果没有node_id，尝试自动注册
            if not self.node_id:
                await self.auto_register()
            
            # 初始化摄像头
            await self.camera_handler.initialize()
            
            # 启动HTTP服务器
            await self.node_server.start()
            
            # 注册到主控制器
            await self.register_to_master()
            
            # 启动心跳和NTP同步
            asyncio.create_task(self.heartbeat_loop())
            asyncio.create_task(self.ntp_sync_loop())
            
            self.running = True
            self.logger.info(f"节点 {self.node_id} 启动成功")
            
            # 主循环
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"节点 {self.node_id} 启动失败: {e}")
            await self.stop()
    
    async def auto_register(self):
        """自动注册到主控制器并获取节点ID"""
        try:
            self.logger.info("正在自动注册到主控制器...")
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.config.get_master_url()}/api/register"
                data = {
                    "local_ip": self.config.local_ip,
                    "node_port": self.config.node_port,
                    "capabilities": {
                        "camera": True,
                        "preview": True,
                        "capture": True
                    }
                }
                
                async with session.post(url, json=data, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            self.node_id = result.get('node_id')
                            self.config.node_id = self.node_id
                            
                            # 更新存储路径
                            self.config.image_storage_path = f"/tmp/camera_images/node_{self.node_id}"
                            import os
                            os.makedirs(self.config.image_storage_path, exist_ok=True)
                            
                            # 保存配置
                            self.config.save_config()
                            
                            self.logger.info(f"自动注册成功，分配节点ID: {self.node_id}")
                            return True
                        else:
                            self.logger.error(f"自动注册失败: {result.get('error')}")
                    else:
                        self.logger.error(f"自动注册HTTP错误: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"自动注册异常: {e}")
        
        return False
    
    async def register_to_master(self):
        """注册到主控制器"""
        if self.registered:
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.config.get_master_url()}/api/node_online"
                data = {
                    "node_id": self.node_id,
                    "local_ip": self.config.local_ip,
                    "node_port": self.config.node_port,
                    "status": "online",
                    "capabilities": {
                        "camera": True,
                        "preview": True,
                        "capture": True
                    }
                }
                
                async with session.post(url, json=data, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            self.registered = True
                            self.logger.info(f"节点 {self.node_id} 注册成功")
                        else:
                            self.logger.error(f"节点注册失败: {result.get('error')}")
                    else:
                        self.logger.error(f"节点注册HTTP错误: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"节点注册异常: {e}")
    
    async def ntp_sync_loop(self):
        """定期NTP时间同步"""
        while self.running:
            try:
                await asyncio.sleep(300)  # 每5分钟同步一次
                if self.running:
                    await ntp_client.sync_time()
            except Exception as e:
                self.logger.error(f"NTP同步循环异常: {e}")
    
    async def stop(self):
        """停止摄像头节点"""
        self.logger.info(f"正在停止节点 {self.node_id}...")
        self.running = False
        
        # 通知主控制器节点离线
        if self.registered:
            await self.notify_offline()
        
        await self.node_server.stop()
        await self.camera_handler.cleanup()
        
        self.logger.info(f"节点 {self.node_id} 已停止")
    
    async def notify_offline(self):
        """通知主控制器节点离线"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.config.get_master_url()}/api/node_offline"
                data = {
                    "node_id": self.node_id,
                    "local_ip": self.config.local_ip
                }
                
                async with session.post(url, json=data, timeout=5) as response:
                    if response.status == 200:
                        self.logger.info(f"节点 {self.node_id} 离线通知发送成功")
                        
        except Exception as e:
            self.logger.error(f"发送离线通知失败: {e}")
    
    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                # 发送心跳到主控制器
                await self.send_heartbeat()
                await asyncio.sleep(self.config.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"心跳发送失败: {e}")
                await asyncio.sleep(5)  # 错误时等待5秒重试
    
    async def send_heartbeat(self):
        """发送心跳"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.config.get_master_url()}/api/heartbeat"
                data = {
                    "node_id": self.node_id,
                    "status": "online",
                    "timestamp": time.time(),
                    "is_ready": self.camera_handler.is_ready(),
                    "local_ip": self.config.local_ip
                }
                async with session.post(url, json=data, timeout=5) as response:
                    if response.status == 200:
                        pass  # 心跳成功
        except Exception as e:
            # 心跳失败不影响主要功能，但记录错误
            if self.running:  # 只在运行时记录错误
                self.logger.debug(f"心跳发送失败: {e}")
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"节点 {self.node_id} 收到信号 {signum}，准备退出...")
        asyncio.create_task(self.stop())

async def main():
    node_id = None
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        try:
            node_id = int(sys.argv[1])
        except ValueError:
            print("错误: node_id 必须是整数")
            sys.exit(1)
    
    node = CameraNode(node_id)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, node.signal_handler)
    signal.signal(signal.SIGTERM, node.signal_handler)
    
    try:
        await node.start()
    except KeyboardInterrupt:
        await node.stop()
    except Exception as e:
        logging.error(f"节点程序异常退出: {e}")
        await node.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())