# 摄像头管理器
import asyncio
import logging
import time
import aiohttp
import json
import socket
from typing import Dict, List, Optional
from dataclasses import dataclass
from shared.ntp_sync import scheduled_capture, ntp_client
from shared.protocol import MessageType, ScheduledCaptureCommand

@dataclass
class CameraNode:
    node_id: int
    ip_address: str
    node_port: int = 8084
    status: str = "offline"  # offline, online, ready, capturing, error
    last_heartbeat: float = 0
    is_ready: bool = False  # 是否就绪拍摄
    capabilities: dict = None  # 节点能力
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = {"camera": True, "preview": True, "capture": True}
    
class CameraManager:
    def __init__(self):
        self.nodes: Dict[int, CameraNode] = {}
        self.current_preview_node = None
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.image_storage_path = "/opt/camera_images"  # 主机图片存储路径
        self.next_node_id = 1  # 下一个可分配的节点ID
        self.discovery_server = None  # 发现服务器
        
    async def start(self):
        """启动摄像头管理器"""
        self.logger.info("启动摄像头管理器...")
        self.running = True
        
        # 创建图片存储目录
        import os
        os.makedirs(self.image_storage_path, exist_ok=True)
        
        # 启动节点发现服务
        asyncio.create_task(self.start_discovery_server())
        
        # 启动心跳检测
        asyncio.create_task(self.heartbeat_monitor())
        
        # 启动节点状态广播
        asyncio.create_task(self.broadcast_node_status())
        
    async def stop(self):
        """停止摄像头管理器"""
        self.logger.info("停止摄像头管理器...")
        self.running = False
        
        if self.discovery_server:
            self.discovery_server.close()
    
    async def start_discovery_server(self):
        """启动节点发现服务器"""
        try:
            self.discovery_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_server.bind(('', 8085))  # 监听发现端口
            self.discovery_server.setblocking(False)
            
            self.logger.info("节点发现服务器启动成功，监听端口 8085")
            
            while self.running:
                try:
                    data, addr = await asyncio.get_event_loop().sock_recvfrom(self.discovery_server, 1024)
                    await self.handle_discovery_request(data, addr)
                except Exception as e:
                    if self.running:
                        await asyncio.sleep(0.1)
                        
        except Exception as e:
            self.logger.error(f"启动节点发现服务器失败: {e}")
    
    async def handle_discovery_request(self, data: bytes, addr: tuple):
        """处理节点发现请求"""
        try:
            message = json.loads(data.decode())
            if message.get("type") == "discover_master":
                # 响应发现请求
                response = json.dumps({
                    "type": "master_response",
                    "master_ip": "192.168.1.100",  # 主控制器IP
                    "master_port": 8080
                })
                
                await asyncio.get_event_loop().sock_sendto(
                    self.discovery_server, 
                    response.encode(), 
                    addr
                )
                
                self.logger.info(f"响应节点发现请求，来自: {addr[0]}")
                
        except Exception as e:
            self.logger.error(f"处理发现请求失败: {e}")
    
    async def register_node(self, node_data: dict) -> dict:
        """注册新节点"""
        try:
            local_ip = node_data.get("local_ip")
            node_port = node_data.get("node_port", 8084)
            capabilities = node_data.get("capabilities", {})
            
            if not local_ip:
                return {"success": False, "error": "缺少节点IP地址"}
            
            # 分配节点ID
            node_id = self.allocate_node_id()
            
            # 创建节点
            node = CameraNode(
                node_id=node_id,
                ip_address=local_ip,
                node_port=node_port,
                status="online",
                last_heartbeat=time.time(),
                capabilities=capabilities
            )
            
            self.nodes[node_id] = node
            
            # 如果是第一个节点，设为默认预览节点
            if self.current_preview_node is None:
                self.current_preview_node = node_id
            
            self.logger.info(f"注册新节点 {node_id}: {local_ip}:{node_port}")
            
            return {
                "success": True,
                "node_id": node_id,
                "message": f"节点注册成功，分配ID: {node_id}"
            }
            
        except Exception as e:
            self.logger.error(f"注册节点失败: {e}")
            return {"success": False, "error": str(e)}
    
    def allocate_node_id(self) -> int:
        """分配新的节点ID"""
        while self.next_node_id in self.nodes:
            self.next_node_id += 1
        
        allocated_id = self.next_node_id
        self.next_node_id += 1
        return allocated_id
    
    async def node_online(self, node_data: dict) -> dict:
        """节点上线通知"""
        try:
            node_id = node_data.get("node_id")
            local_ip = node_data.get("local_ip")
            node_port = node_data.get("node_port", 8084)
            capabilities = node_data.get("capabilities", {})
            
            if node_id in self.nodes:
                # 更新现有节点
                node = self.nodes[node_id]
                node.ip_address = local_ip
                node.node_port = node_port
                node.status = "online"
                node.last_heartbeat = time.time()
                node.capabilities = capabilities
                
                self.logger.info(f"节点 {node_id} 重新上线: {local_ip}:{node_port}")
            else:
                # 创建新节点
                node = CameraNode(
                    node_id=node_id,
                    ip_address=local_ip,
                    node_port=node_port,
                    status="online",
                    last_heartbeat=time.time(),
                    capabilities=capabilities
                )
                self.nodes[node_id] = node
                
                self.logger.info(f"新节点 {node_id} 上线: {local_ip}:{node_port}")
            
            return {"success": True, "message": "节点上线成功"}
            
        except Exception as e:
            self.logger.error(f"节点上线处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def node_offline(self, node_data: dict) -> dict:
        """节点离线通知"""
        try:
            node_id = node_data.get("node_id")
            
            if node_id in self.nodes:
                self.nodes[node_id].status = "offline"
                self.nodes[node_id].is_ready = False
                
                # 如果是当前预览节点，切换到其他在线节点
                if self.current_preview_node == node_id:
                    self.switch_to_next_online_node()
                
                self.logger.info(f"节点 {node_id} 离线")
            
            return {"success": True, "message": "节点离线处理成功"}
            
        except Exception as e:
            self.logger.error(f"节点离线处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    def switch_to_next_online_node(self):
        """切换到下一个在线节点"""
        for node_id, node in self.nodes.items():
            if node.status == "online":
                self.current_preview_node = node_id
                self.logger.info(f"切换预览到节点 {node_id}")
                return
        
        self.current_preview_node = None
    
    async def update_heartbeat(self, heartbeat_data: dict):
        """更新节点心跳"""
        try:
            node_id = heartbeat_data.get("node_id")
            is_ready = heartbeat_data.get("is_ready", False)
            
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.last_heartbeat = time.time()
                node.is_ready = is_ready
                
                if node.status == "offline":
                    node.status = "online"
                    self.logger.info(f"节点 {node_id} 恢复在线")
                    
        except Exception as e:
            self.logger.error(f"更新心跳失败: {e}")
    
    async def heartbeat_monitor(self):
        """心跳监测"""
        while self.running:
            current_time = time.time()
            for node in self.nodes.values():
                if current_time - node.last_heartbeat > 30:  # 30秒超时
                    if node.status != "offline":
                        node.status = "offline"
                        node.is_ready = False
                        self.logger.warning(f"节点 {node.node_id} 心跳超时，标记为离线")
                        
                        # 如果是当前预览节点，切换到其他节点
                        if self.current_preview_node == node.node_id:
                            self.switch_to_next_online_node()
            
            await asyncio.sleep(10)  # 每10秒检查一次
    
    async def broadcast_node_status(self):
        """定期广播节点状态给客户端"""
        while self.running:
            try:
                # 这里可以通过WebSocket广播节点状态更新
                await asyncio.sleep(5)  # 每5秒广播一次
            except Exception as e:
                self.logger.error(f"广播节点状态失败: {e}")
    
    async def check_all_nodes_ready(self) -> Dict[int, bool]:
        """检查所有节点就绪状态"""
        ready_status = {}
        
        for node in self.nodes.values():
            if node.status == "online":
                try:
                    is_ready = await self.check_node_ready(node.node_id)
                    ready_status[node.node_id] = is_ready
                    node.is_ready = is_ready
                except Exception as e:
                    self.logger.error(f"检查节点 {node.node_id} 就绪状态失败: {e}")
                    ready_status[node.node_id] = False
                    node.is_ready = False
            else:
                ready_status[node.node_id] = False
                node.is_ready = False
        
        return ready_status
    
    async def check_node_ready(self, node_id: int) -> bool:
        """检查单个节点就绪状态"""
        if node_id not in self.nodes:
            return False
            
        node = self.nodes[node_id]
        if node.status != "online":
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{node.ip_address}:{node.node_port}/ready"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('ready', False)
            return False
        except Exception as e:
            self.logger.error(f"检查节点 {node_id} 就绪状态异常: {e}")
            return False
    
    async def trigger_scheduled_capture(self, delay_seconds: float = 0.5) -> Dict[str, any]:
        """触发定时拍摄"""
        self.logger.info("开始定时拍摄流程...")
        
        # 检查所有节点就绪状态
        ready_status = await self.check_all_nodes_ready()
        ready_nodes = [node_id for node_id, ready in ready_status.items() if ready]
        
        if not ready_nodes:
            return {
                "success": False,
                "error": "没有就绪的摄像头节点",
                "ready_status": ready_status
            }
        
        # 生成拍摄会话ID和时间
        session_id = scheduled_capture.generate_session_id()
        capture_time = await scheduled_capture.schedule_capture(session_id, delay_seconds)
        
        # 发送定时拍摄指令到所有就绪节点
        command = ScheduledCaptureCommand(
            capture_time=capture_time,
            session_id=session_id,
            delay_seconds=delay_seconds
        )
        
        send_results = {}
        for node_id in ready_nodes:
            try:
                success = await self.send_capture_command(node_id, command)
                send_results[node_id] = success
            except Exception as e:
                self.logger.error(f"发送拍摄指令到节点 {node_id} 失败: {e}")
                send_results[node_id] = False
        
        return {
            "success": True,
            "session_id": session_id,
            "capture_time": capture_time,
            "ready_nodes": ready_nodes,
            "send_results": send_results,
            "capture_time_formatted": ntp_client.format_time(capture_time)
        }
    
    async def send_capture_command(self, node_id: int, command: ScheduledCaptureCommand) -> bool:
        """发送拍摄指令到节点"""
        if node_id not in self.nodes:
            return False
            
        node = self.nodes[node_id]
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{node.ip_address}:{node.node_port}/capture"
                data = {
                    "capture_time": command.capture_time,
                    "session_id": command.session_id,
                    "delay_seconds": command.delay_seconds
                }
                
                async with session.post(url, json=data, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.logger.info(f"节点 {node_id} 接收拍摄指令成功")
                        return result.get('success', False)
                    else:
                        self.logger.error(f"节点 {node_id} 拒绝拍摄指令: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"发送拍摄指令到节点 {node_id} 异常: {e}")
            return False
    
    def get_node_list(self) -> List[dict]:
        """获取节点列表"""
        return [
            {
                "node_id": node.node_id,
                "ip_address": node.ip_address,
                "node_port": node.node_port,
                "status": node.status,
                "is_ready": node.is_ready,
                "last_heartbeat": node.last_heartbeat,
                "capabilities": node.capabilities
            }
            for node in self.nodes.values()
        ]
    
    def switch_preview_camera(self, node_id: int) -> bool:
        """切换预览摄像头"""
        if node_id in self.nodes and self.nodes[node_id].status == "online":
            self.current_preview_node = node_id
            self.logger.info(f"切换预览到节点 {node_id}")
            return True
        return False
    
    def get_current_preview_node(self) -> Optional[int]:
        """获取当前预览节点"""
        return self.current_preview_node
    
    def get_image_storage_path(self) -> str:
        """获取图片存储路径"""
        return self.image_storage_path
    
    def get_online_node_count(self) -> int:
        """获取在线节点数量"""
        return len([node for node in self.nodes.values() if node.status == "online"])
    
    def get_ready_node_count(self) -> int:
        """获取就绪节点数量"""
        return len([node for node in self.nodes.values() if node.is_ready])