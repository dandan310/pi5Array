#!/usr/bin/env python3
# 树莓派4主控程序
import asyncio
import logging
import signal
import sys
import os
from camera_manager import CameraManager
from web_server import WebServer
from config import MasterConfig
from shared.ntp_sync import ntp_client

class MasterController:
    def __init__(self):
        self.config = MasterConfig()
        self.camera_manager = CameraManager()
        self.web_server = WebServer(self.camera_manager)
        self.running = False
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """启动主控制器"""
        self.logger.info("启动树莓派多角度摄影系统主控制器...")
        
        try:
            # 同步NTP时间
            self.logger.info("正在同步NTP时间...")
            if await ntp_client.sync_time():
                self.logger.info(f"NTP时间同步成功，当前时间: {ntp_client.format_time()}")
            else:
                self.logger.warning("NTP时间同步失败，使用本地时间")
            
            # 启动摄像头管理器
            await self.camera_manager.start()
            
            # 启动Web服务器
            await self.web_server.start()
            
            # 启动定期NTP同步
            asyncio.create_task(self.ntp_sync_loop())
            
            self.running = True
            self.logger.info("主控制器启动成功")
            
            # 主循环
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"主控制器启动失败: {e}")
            await self.stop()
    
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
        """停止主控制器"""
        self.logger.info("正在停止主控制器...")
        self.running = False
        
        await self.web_server.stop()
        await self.camera_manager.stop()
        
        self.logger.info("主控制器已停止")
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"收到信号 {signum}，准备退出...")
        asyncio.create_task(self.stop())

async def main():
    controller = MasterController()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, controller.signal_handler)
    signal.signal(signal.SIGTERM, controller.signal_handler)
    
    try:
        await controller.start()
    except KeyboardInterrupt:
        await controller.stop()
    except Exception as e:
        logging.error(f"程序异常退出: {e}")
        await controller.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())