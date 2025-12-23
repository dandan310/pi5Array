# Web服务器 - 与iPad通信
import asyncio
import logging
import json
from datetime import datetime
from aiohttp import web, WSMsgType
import aiohttp_cors
from typing import Set
import weakref

class WebServer:
    def __init__(self, camera_manager):
        self.camera_manager = camera_manager
        self.logger = logging.getLogger(__name__)
        self.app = None
        self.runner = None
        self.site = None
        self.websockets: Set = set()
        
    async def start(self):
        """启动Web服务器"""
        self.logger.info("启动Web服务器...")
        
        # 创建应用
        self.app = web.Application()
        
        # 配置CORS
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # 添加路由
        self.app.router.add_get('/', self.index_handler)
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/api/cameras', self.get_cameras_handler)
        self.app.router.add_post('/api/capture', self.capture_handler)
        self.app.router.add_post('/api/switch_camera', self.switch_camera_handler)
        self.app.router.add_get('/api/ready', self.check_ready_handler)  # 检查就绪状态
        self.app.router.add_post('/api/upload', self.upload_handler)  # 文件上传
        
        # 节点管理API
        self.app.router.add_post('/api/register', self.register_node_handler)  # 节点注册
        self.app.router.add_post('/api/node_online', self.node_online_handler)  # 节点上线
        self.app.router.add_post('/api/node_offline', self.node_offline_handler)  # 节点离线
        self.app.router.add_post('/api/heartbeat', self.heartbeat_handler)  # 心跳
        
        self.app.router.add_get('/stream/{node_id}', self.stream_handler)
        
        # 添加静态文件服务
        self.app.router.add_static('/', path='../ipad_client', name='static')
        
        # 为所有路由添加CORS
        for route in list(self.app.router.routes()):
            cors.add(route)
        
        # 启动服务器
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, '0.0.0.0', 8080)
        await self.site.start()
        
        self.logger.info("Web服务器启动成功，监听端口 8080")
    
    async def stop(self):
        """停止Web服务器"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        self.logger.info("Web服务器已停止")
    
    async def index_handler(self, request):
        """主页处理器"""
        return web.FileResponse('../ipad_client/index.html')
    
    async def websocket_handler(self, request):
        """WebSocket处理器"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # 添加到连接集合
        self.websockets.add(ws)
        self.logger.info("新的WebSocket连接")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_websocket_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({
                            'type': 'error',
                            'message': '无效的JSON格式'
                        }))
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f'WebSocket错误: {ws.exception()}')
        except Exception as e:
            self.logger.error(f'WebSocket处理异常: {e}')
        finally:
            self.websockets.discard(ws)
            self.logger.info("WebSocket连接关闭")
        
        return ws
    
    async def handle_websocket_message(self, ws, data):
        """处理WebSocket消息"""
        msg_type = data.get('type')
        
        if msg_type == 'get_cameras':
            cameras = self.camera_manager.get_node_list()
            await ws.send_str(json.dumps({
                'type': 'camera_list',
                'data': cameras
            }))
        
        elif msg_type == 'switch_camera':
            node_id = data.get('node_id')
            success = self.camera_manager.switch_preview_camera(node_id)
            await ws.send_str(json.dumps({
                'type': 'camera_switched',
                'success': success,
                'current_node': node_id if success else None
            }))
        
        elif msg_type == 'check_ready':
            # 检查所有节点就绪状态
            ready_status = await self.camera_manager.check_all_nodes_ready()
            await ws.send_str(json.dumps({
                'type': 'ready_status',
                'ready_status': ready_status
            }))
        
        elif msg_type == 'trigger_capture':
            # 触发定时拍摄
            delay_seconds = data.get('delay_seconds', 0.5)
            result = await self.camera_manager.trigger_scheduled_capture(delay_seconds)
            await ws.send_str(json.dumps({
                'type': 'capture_scheduled',
                'result': result
            }))
    
    async def get_cameras_handler(self, request):
        """获取摄像头列表API"""
        cameras = self.camera_manager.get_node_list()
        return web.json_response({
            'cameras': cameras,
            'current_preview': self.camera_manager.get_current_preview_node(),
            'online_count': self.camera_manager.get_online_node_count(),
            'ready_count': self.camera_manager.get_ready_node_count()
        })
    
    async def capture_handler(self, request):
        """拍摄API"""
        data = await request.json()
        delay_seconds = data.get('delay_seconds', 0.5)
        
        result = await self.camera_manager.trigger_scheduled_capture(delay_seconds)
        return web.json_response(result)
    
    async def switch_camera_handler(self, request):
        """切换摄像头API"""
        data = await request.json()
        node_id = data.get('node_id')
        
        if not node_id:
            return web.json_response({
                'success': False,
                'error': '缺少node_id参数'
            }, status=400)
        
        success = self.camera_manager.switch_preview_camera(node_id)
        return web.json_response({
            'success': success,
            'current_node': node_id if success else None
        })
    
    async def check_ready_handler(self, request):
        """检查就绪状态API"""
        ready_status = await self.camera_manager.check_all_nodes_ready()
        return web.json_response({
            'ready_status': ready_status
        })
    
    async def upload_handler(self, request):
        """文件上传处理器"""
        try:
            reader = await request.multipart()
            field = await reader.next()
            
            if field.name == 'image':
                filename = field.filename
                if not filename:
                    return web.json_response({
                        'success': False,
                        'error': '缺少文件名'
                    }, status=400)
                
                # 保存文件到指定目录
                storage_path = self.camera_manager.get_image_storage_path()
                file_path = f"{storage_path}/{filename}"
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)
                
                self.logger.info(f"接收到图片文件: {filename}")
                return web.json_response({
                    'success': True,
                    'filename': filename,
                    'path': file_path
                })
            
            return web.json_response({
                'success': False,
                'error': '无效的文件字段'
            }, status=400)
            
        except Exception as e:
            self.logger.error(f"文件上传失败: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def broadcast_to_clients(self, message):
        """向所有客户端广播消息"""
        if not self.websockets:
            return
        
        # 清理已关闭的连接
        closed_ws = set()
        for ws in self.websockets:
            if ws.closed:
                closed_ws.add(ws)
        
        for ws in closed_ws:
            self.websockets.discard(ws)
        
        # 广播消息
        if self.websockets:
            await asyncio.gather(
                *[ws.send_str(json.dumps(message)) for ws in self.websockets],
                return_exceptions=True
            )
    async def register_node_handler(self, request):
        """节点注册处理器"""
        try:
            data = await request.json()
            result = await self.camera_manager.register_node(data)
            
            # 广播节点列表更新
            if result.get('success'):
                await self.broadcast_camera_list()
            
            return web.json_response(result)
            
        except Exception as e:
            self.logger.error(f"节点注册处理失败: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def node_online_handler(self, request):
        """节点上线处理器"""
        try:
            data = await request.json()
            result = await self.camera_manager.node_online(data)
            
            # 广播节点列表更新
            if result.get('success'):
                await self.broadcast_camera_list()
            
            return web.json_response(result)
            
        except Exception as e:
            self.logger.error(f"节点上线处理失败: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def node_offline_handler(self, request):
        """节点离线处理器"""
        try:
            data = await request.json()
            result = await self.camera_manager.node_offline(data)
            
            # 广播节点列表更新
            if result.get('success'):
                await self.broadcast_camera_list()
            
            return web.json_response(result)
            
        except Exception as e:
            self.logger.error(f"节点离线处理失败: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def heartbeat_handler(self, request):
        """心跳处理器"""
        try:
            data = await request.json()
            await self.camera_manager.update_heartbeat(data)
            
            return web.json_response({
                'success': True,
                'timestamp': time.time()
            })
            
        except Exception as e:
            self.logger.error(f"心跳处理失败: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    async def broadcast_camera_list(self):
        """广播摄像头列表更新"""
        if not self.websockets:
            return
        
        cameras = self.camera_manager.get_node_list()
        message = {
            'type': 'camera_list_updated',
            'data': cameras,
            'online_count': self.camera_manager.get_online_node_count(),
            'ready_count': self.camera_manager.get_ready_node_count()
        }
        
        await self.broadcast_to_clients(message)
    
    async def stream_handler(self, request):
        """视频流处理器"""
        node_id = int(request.match_info['node_id'])
        
        # 这里应该返回摄像头的视频流
        # 暂时返回占位符
        return web.Response(
            text=f"摄像头 {node_id} 视频流占位符",
            content_type='text/plain'
        )