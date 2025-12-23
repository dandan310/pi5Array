# 主控制器配置
import os
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class CameraNodeConfig:
    node_id: int
    ip_address: str
    name: str = ""

@dataclass
class MasterConfig:
    # 网络配置
    master_ip: str = "192.168.1.124"
    web_server_port: int = 8080
    websocket_port: int = 8081
    
    # 摄像头节点配置
    camera_nodes: List[CameraNodeConfig] = None
    
    # 图片存储配置
    image_storage_path: str = "/opt/camera_images"
    image_format: str = "jpg"
    image_quality: int = 95
    
    # NTP时间同步配置
    ntp_sync_interval: int = 300  # 5分钟
    capture_delay_seconds: float = 0.5  # 默认拍摄延迟
    
    # 系统配置
    log_level: str = "INFO"
    max_capture_timeout: int = 30  # 秒
    heartbeat_interval: int = 10   # 秒
    
    def __post_init__(self):
        if self.camera_nodes is None:
            self.camera_nodes = [
                CameraNodeConfig(1, "192.168.1.101", "前方摄像头"),
                CameraNodeConfig(2, "192.168.1.102", "左侧摄像头"),
                CameraNodeConfig(3, "192.168.1.103", "右侧摄像头"),
                CameraNodeConfig(4, "192.168.1.104", "后方摄像头"),
            ]
        
        # 确保存储目录存在
        os.makedirs(self.image_storage_path, exist_ok=True)
    
    @classmethod
    def from_file(cls, config_file: str) -> 'MasterConfig':
        """从配置文件加载配置"""
        # 这里可以实现从JSON/YAML文件加载配置
        # 暂时返回默认配置
        return cls()
    
    def get_node_config(self, node_id: int) -> CameraNodeConfig:
        """获取指定节点配置"""
        for node in self.camera_nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def get_all_node_ips(self) -> List[str]:
        """获取所有节点IP地址"""
        return [node.ip_address for node in self.camera_nodes]