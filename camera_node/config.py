# 摄像头节点配置
import os
import socket
import json
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class NodeConfig:
    node_id: Optional[int] = None  # 支持自动分配ID
    
    # 网络配置
    master_ip: str = ""  # 支持自动发现
    master_port: int = 8080
    node_port: int = 8084  # 节点HTTP服务端口
    
    # 自动发现配置
    discovery_broadcast_port: int = 8085  # 广播发现端口
    discovery_timeout: int = 30  # 发现超时时间
    auto_register: bool = True  # 自动注册到主控制器
    
    # 本地IP配置
    local_ip: str = ""
    
    # 摄像头配置
    image_storage_path: str = "/tmp/camera_images"
    image_format: str = "jpg"
    image_quality: int = 95
    capture_resolution: tuple = (4608, 2592)  # Camera Module 3 最大分辨率
    preview_resolution: tuple = (1280, 720)
    
    # 系统配置
    log_level: str = "INFO"
    heartbeat_interval: int = 10  # 秒
    max_reconnect_attempts: int = 10  # 最大重连次数
    
    def __post_init__(self):
        # 获取本地IP
        if not self.local_ip:
            self.local_ip = self.get_local_ip()
        
        # 如果没有指定主控制器IP，尝试自动发现
        if not self.master_ip:
            self.master_ip = self.discover_master() or "192.168.1.100"
        
        # 创建存储目录
        if self.node_id:
            self.image_storage_path = f"/tmp/camera_images/node_{self.node_id}"
        else:
            self.image_storage_path = f"/tmp/camera_images/node_auto"
        
        # 确保存储目录存在
        os.makedirs(self.image_storage_path, exist_ok=True)
    
    def get_local_ip(self) -> str:
        """获取本地IP地址"""
        try:
            # 连接到一个远程地址来获取本地IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    def discover_master(self) -> Optional[str]:
        """自动发现主控制器IP"""
        try:
            # 广播发现请求
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(5)
            
            # 发送发现请求到广播地址
            discovery_msg = json.dumps({
                "type": "discover_master",
                "node_ip": self.local_ip
            })
            
            # 尝试多个网段
            broadcast_addresses = [
                "192.168.1.255",
                "192.168.0.255", 
                "10.0.0.255",
                "172.16.255.255"
            ]
            
            for broadcast_addr in broadcast_addresses:
                try:
                    sock.sendto(discovery_msg.encode(), (broadcast_addr, self.discovery_broadcast_port))
                except Exception:
                    continue
            
            # 等待响应
            try:
                data, addr = sock.recvfrom(1024)
                response = json.loads(data.decode())
                if response.get("type") == "master_response":
                    return addr[0]
            except socket.timeout:
                pass
            
            sock.close()
            
        except Exception as e:
            print(f"自动发现主控制器失败: {e}")
        
        return None
    
    def get_master_url(self) -> str:
        """获取主控制器URL"""
        return f"http://{self.master_ip}:{self.master_port}"
    
    def get_websocket_url(self) -> str:
        """获取WebSocket URL"""
        return f"ws://{self.master_ip}:{self.master_port}/ws"
    
    def save_config(self, config_file: str = "/opt/camera_node/node_config.json"):
        """保存配置到文件"""
        try:
            config_data = {
                "node_id": self.node_id,
                "master_ip": self.master_ip,
                "master_port": self.master_port,
                "local_ip": self.local_ip,
                "auto_register": self.auto_register
            }
            
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    @classmethod
    def load_config(cls, config_file: str = "/opt/camera_node/node_config.json") -> 'NodeConfig':
        """从文件加载配置"""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                return cls(
                    node_id=config_data.get("node_id"),
                    master_ip=config_data.get("master_ip", ""),
                    master_port=config_data.get("master_port", 8080),
                    local_ip=config_data.get("local_ip", ""),
                    auto_register=config_data.get("auto_register", True)
                )
        except Exception as e:
            print(f"加载配置失败: {e}")
        
        return cls()