# NTP时间同步模块
import asyncio
import logging
import time
import socket
import struct
from typing import Optional, List
from datetime import datetime

class NTPClient:
    """NTP客户端，用于时间同步"""
    
    def __init__(self, servers: List[str] = None):
        self.servers = servers or [
            "pool.ntp.org",
            "time.nist.gov", 
            "time.google.com",
            "cn.pool.ntp.org"
        ]
        self.logger = logging.getLogger(__name__)
        self.time_offset = 0.0  # 与NTP服务器的时间偏移
        self.last_sync = 0.0
        
    async def sync_time(self) -> bool:
        """同步时间"""
        for server in self.servers:
            try:
                ntp_time = await self.get_ntp_time(server)
                if ntp_time:
                    local_time = time.time()
                    self.time_offset = ntp_time - local_time
                    self.last_sync = local_time
                    
                    self.logger.info(f"时间同步成功，服务器: {server}, 偏移: {self.time_offset:.3f}秒")
                    return True
                    
            except Exception as e:
                self.logger.warning(f"NTP服务器 {server} 同步失败: {e}")
                continue
        
        self.logger.error("所有NTP服务器同步失败")
        return False
    
    async def get_ntp_time(self, server: str, timeout: float = 5.0) -> Optional[float]:
        """获取NTP时间"""
        try:
            # NTP数据包格式
            ntp_packet = bytearray(48)
            ntp_packet[0] = 0x1B  # LI=0, VN=3, Mode=3
            
            # 创建UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            # 发送请求
            sock.sendto(ntp_packet, (server, 123))
            
            # 接收响应
            response, _ = sock.recvfrom(48)
            sock.close()
            
            # 解析时间戳 (从1900年开始的秒数)
            timestamp = struct.unpack("!I", response[40:44])[0]
            
            # 转换为Unix时间戳 (从1970年开始)
            ntp_time = timestamp - 2208988800  # 1900到1970的秒数
            
            return float(ntp_time)
            
        except Exception as e:
            self.logger.error(f"获取NTP时间失败 {server}: {e}")
            return None
    
    def get_synchronized_time(self) -> float:
        """获取同步后的时间"""
        return time.time() + self.time_offset
    
    def is_synchronized(self, max_age: float = 300.0) -> bool:
        """检查时间是否已同步且在有效期内"""
        if self.last_sync == 0:
            return False
        return (time.time() - self.last_sync) < max_age
    
    def format_time(self, timestamp: float = None) -> str:
        """格式化时间显示"""
        if timestamp is None:
            timestamp = self.get_synchronized_time()
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

class ScheduledCapture:
    """定时拍摄控制器"""
    
    def __init__(self, ntp_client: NTPClient):
        self.ntp_client = ntp_client
        self.logger = logging.getLogger(__name__)
        self.scheduled_tasks = {}  # 存储定时任务
        
    async def schedule_capture(self, session_id: str, delay_seconds: float = 0.5) -> float:
        """安排拍摄任务"""
        if not self.ntp_client.is_synchronized():
            await self.ntp_client.sync_time()
        
        # 计算拍摄时间
        current_time = self.ntp_client.get_synchronized_time()
        capture_time = current_time + delay_seconds
        
        self.logger.info(f"安排拍摄任务 {session_id}, 拍摄时间: {self.ntp_client.format_time(capture_time)}")
        
        return capture_time
    
    async def wait_for_capture_time(self, capture_time: float, callback=None):
        """等待到拍摄时间并执行回调"""
        while True:
            current_time = self.ntp_client.get_synchronized_time()
            time_diff = capture_time - current_time
            
            if time_diff <= 0:
                # 时间到了，执行拍摄
                if callback:
                    await callback()
                break
            elif time_diff > 1.0:
                # 还有超过1秒，等待1秒
                await asyncio.sleep(1.0)
            else:
                # 精确等待剩余时间
                await asyncio.sleep(time_diff)
    
    def generate_session_id(self) -> str:
        """生成拍摄会话ID"""
        timestamp = int(time.time() * 1000)  # 毫秒时间戳
        return f"capture_{timestamp}"
    
    def generate_filename(self, node_id: int, capture_time: float) -> str:
        """生成文件名：拍摄时间-从机序号.jpg"""
        dt = datetime.fromtimestamp(capture_time)
        time_str = dt.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 精确到毫秒
        return f"{time_str}-node{node_id:02d}.jpg"

# 全局NTP客户端实例
ntp_client = NTPClient()
scheduled_capture = ScheduledCapture(ntp_client)