# 摄像头处理器
import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

try:
    from picamera2 import Picamera2
    from libcamera import controls
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    logging.warning("picamera2不可用，使用模拟模式")

class CameraHandler:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.camera = None
        self.initialized = False
        
    async def initialize(self):
        """初始化摄像头"""
        if not PICAMERA_AVAILABLE:
            self.logger.warning("摄像头模拟模式")
            self.initialized = True
            return
        
        try:
            self.camera = Picamera2()
            
            # 配置摄像头
            config = self.camera.create_still_configuration(
                main={
                    "size": (4608, 2592),  # Camera Module 3 最大分辨率
                    "format": "RGB888"
                },
                lores={
                    "size": (1280, 720),   # 预览分辨率
                    "format": "YUV420"
                },
                display="lores"
            )
            
            self.camera.configure(config)
            
            # 设置摄像头参数
            self.camera.set_controls({
                "AfMode": controls.AfModeEnum.Continuous,
                "AfSpeed": controls.AfSpeedEnum.Fast,
            })
            
            self.camera.start()
            
            # 等待摄像头稳定
            await asyncio.sleep(2)
            
            self.initialized = True
            self.logger.info(f"节点 {self.config.node_id} 摄像头初始化成功")
            
        except Exception as e:
            self.logger.error(f"摄像头初始化失败: {e}")
            raise
    
    async def capture_image(self, filename: str = None) -> Optional[str]:
        """拍摄图片"""
        if not self.initialized:
            self.logger.error("摄像头未初始化")
            return None
        
        try:
            # 生成文件名
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = f"node_{self.config.node_id}_{timestamp}.jpg"
            
            filepath = os.path.join(self.config.image_storage_path, filename)
            
            # 确保目录存在
            os.makedirs(self.config.image_storage_path, exist_ok=True)
            
            if PICAMERA_AVAILABLE and self.camera:
                # 实际拍摄
                self.camera.capture_file(filepath)
                self.logger.info(f"拍摄完成: {filepath}")
            else:
                # 模拟拍摄
                with open(filepath, 'w') as f:
                    f.write(f"模拟图片 - 节点 {self.config.node_id} - {filename}")
                self.logger.info(f"模拟拍摄完成: {filepath}")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"拍摄失败: {e}")
            return None
    
    def is_ready(self) -> bool:
        """检查摄像头是否就绪"""
        return self.initialized
    
    async def start_preview_stream(self):
        """开始预览流"""
        if not self.initialized:
            return
        
        if PICAMERA_AVAILABLE and self.camera:
            # 这里可以实现MJPEG流或其他格式的预览流
            pass
    
    async def stop_preview_stream(self):
        """停止预览流"""
        if not self.initialized:
            return
        
        if PICAMERA_AVAILABLE and self.camera:
            # 停止预览流
            pass
    
    async def cleanup(self):
        """清理摄像头资源"""
        if PICAMERA_AVAILABLE and self.camera:
            try:
                self.camera.stop()
                self.camera.close()
                self.logger.info(f"节点 {self.config.node_id} 摄像头资源清理完成")
            except Exception as e:
                self.logger.error(f"摄像头清理失败: {e}")
        
        self.initialized = False
        self.camera = None