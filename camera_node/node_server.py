# 摄像头节点HTTP服务器
import asyncio
import logging
import json
import aiohttp
from aiohttp import web
from datetime import datetime
from shared.ntp_sync import ntp_client, scheduled_capture

class NodeServer:
    def __init__(self, config, camera_handler):
        self.config = config
        self.camera_handler = camera_handler
        self.logger = logging.getLogger(__name__)
        self.app = None
        self.runner = None
        self.site = None
        self.scheduled_captures = {}  # 存储定时拍摄任务
        
    async def start(self):
        """启动HTTP服务器"""
        self.logger.info(f"启动节点 {self.config.node_id} HTTP服务器...")
        
        # 创建应用
        self.app = web.Application()
        
        # 添加路由
        self.app.router.add_get('/ready', self.ready_handler)
        self.app.router.add_post('/capture', self.capture_handler)
        self.app.router.add_get('/status', self.status_handler)
        self.app.router.add_get('/stream', self.stream_handler)
        
        # 启动服务器
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, '0.0.0.0', 8084)
        await self.site.start()
        
        self.logger.info(f"节点 {self.config.node_id} HTTP服务器启动成功，监听端口 8084")
    
    async def stop(self):
        """停止HTTP服务器"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        self.logger.info(f"节点 {self.config.node_id} HTTP服务器已停止")
    
    async def ready_handler(self, request):
        """就绪状态检查"""
        is_ready = self.camera_handler.is_ready()
        return web.json_response({
            'ready': is_ready,
            'node_id': self.config.node_id,
            'timestamp': ntp_client.get_synchronized_time(),
            'time_synchronized': ntp_client.is_synchronized()
        })
    
    async def capture_handler(self, request):
        """接收拍摄指令"""
        try:
            data = await request.json()
            capture_time = data.get('capture_time')
            session_id = data.get('session_id')
            
            if not capture_time or not session_id:
                return web.json_response({
                    'success': False,
                    'error': '缺少必要参数'
                }, status=400)
            
            # 检查摄像头是否就绪
            if not self.camera_handler.is_ready():
                return web.json_response({
                    'success': False,
                    'error': '摄像头未就绪'
                }, status=400)
            
            # 安排定时拍摄
            task = asyncio.create_task(
                self.execute_scheduled_capture(capture_time, session_id)
            )
            self.scheduled_captures[session_id] = task
            
            self.logger.info(f"接收拍摄指令，会话ID: {session_id}, 拍摄时间: {ntp_client.format_time(capture_time)}")
            
            return web.json_response({
                'success': True,
                'session_id': session_id,
                'capture_time': capture_time,
                'node_id': self.config.node_id
            })
            
        except Exception as e:
            self.logger.error(f"处理拍摄指令失败: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def execute_scheduled_capture(self, capture_time: float, session_id: str):
        """执行定时拍摄"""
        try:
            # 等待到拍摄时间
            await scheduled_capture.wait_for_capture_time(
                capture_time, 
                lambda: self.perform_capture(session_id, capture_time)
            )
            
        except Exception as e:
            self.logger.error(f"定时拍摄执行失败 {session_id}: {e}")
        finally:
            # 清理任务
            if session_id in self.scheduled_captures:
                del self.scheduled_captures[session_id]
    
    async def perform_capture(self, session_id: str, capture_time: float):
        """执行拍摄"""
        self.logger.info(f"开始拍摄，会话ID: {session_id}")
        
        try:
            # 生成文件名
            filename = scheduled_capture.generate_filename(self.config.node_id, capture_time)
            
            # 拍摄照片
            image_path = await self.camera_handler.capture_image(filename)
            
            if image_path:
                self.logger.info(f"拍摄完成: {image_path}")
                
                # 上传图片到主控制器
                await self.upload_image_to_master(image_path, filename)
            else:
                self.logger.error(f"拍摄失败，会话ID: {session_id}")
                
        except Exception as e:
            self.logger.error(f"拍摄执行异常 {session_id}: {e}")
    
    async def upload_image_to_master(self, image_path: str, filename: str):
        """上传图片到主控制器"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.config.get_master_url()}/api/upload"
                
                with open(image_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('image', f, filename=filename, content_type='image/jpeg')
                    
                    async with session.post(url, data=data, timeout=30) as response:
                        if response.status == 200:
                            result = await response.json()
                            if result.get('success'):
                                self.logger.info(f"图片上传成功: {filename}")
                            else:
                                self.logger.error(f"图片上传失败: {result.get('error')}")
                        else:
                            self.logger.error(f"图片上传HTTP错误: {response.status}")
                            
        except Exception as e:
            self.logger.error(f"上传图片异常 {filename}: {e}")
    
    async def status_handler(self, request):
        """状态查询"""
        return web.json_response({
            'node_id': self.config.node_id,
            'status': 'online',
            'camera_ready': self.camera_handler.is_ready(),
            'time_synchronized': ntp_client.is_synchronized(),
            'current_time': ntp_client.get_synchronized_time(),
            'scheduled_captures': len(self.scheduled_captures)
        })
    
    async def stream_handler(self, request):
        """视频流处理器"""
        # 这里可以实现MJPEG流
        return web.Response(
            text=f"节点 {self.config.node_id} 视频流",
            content_type='text/plain'
        )