# 通信协议定义
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import json
import time

class MessageType(Enum):
    # 主控到节点
    SCHEDULED_CAPTURE = "scheduled_capture"  # 定时拍摄指令
    START_PREVIEW = "start_preview"
    STOP_PREVIEW = "stop_preview"
    GET_STATUS = "get_status"
    TIME_SYNC = "time_sync"  # 时间同步
    
    # 节点到主控
    STATUS_RESPONSE = "status_response"
    CAPTURE_COMPLETE = "capture_complete"
    PREVIEW_FRAME = "preview_frame"
    ERROR = "error"
    READY_STATUS = "ready_status"  # 就绪状态
    
    # iPad到主控
    REQUEST_PREVIEW = "request_preview"
    SWITCH_CAMERA = "switch_camera"
    TRIGGER_CAPTURE = "trigger_capture"
    GET_CAMERA_LIST = "get_camera_list"
    CHECK_READY = "check_ready"  # 检查就绪状态

@dataclass
class ScheduledCaptureCommand:
    """定时拍摄命令"""
    capture_time: float  # Unix时间戳
    session_id: str      # 拍摄会话ID
    delay_seconds: float = 0.5  # 延迟时间（秒）

@dataclass
class Message:
    type: MessageType
    node_id: Optional[int] = None
    data: Optional[dict] = None
    timestamp: Optional[float] = None
    
    def to_json(self) -> str:
        return json.dumps({
            'type': self.type.value,
            'node_id': self.node_id,
            'data': self.data,
            'timestamp': self.timestamp
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        return cls(
            type=MessageType(data['type']),
            node_id=data.get('node_id'),
            data=data.get('data'),
            timestamp=data.get('timestamp')
        )

# NTP时间同步配置
class NTPConfig:
    NTP_SERVERS = [
        "pool.ntp.org",
        "time.nist.gov", 
        "time.google.com"
    ]
    SYNC_INTERVAL = 300  # 5分钟同步一次
    CAPTURE_DELAY = 0.5  # 拍摄延迟500ms

# 网络配置
class NetworkConfig:
    MASTER_IP = "192.168.1.100"
    WEB_SERVER_PORT = 8080
    WEBSOCKET_PORT = 8081
    CAMERA_STREAM_PORT = 8082
    FILE_TRANSFER_PORT = 8083  # 文件传输端口