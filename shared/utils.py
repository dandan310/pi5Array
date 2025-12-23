# 共享工具函数
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import hashlib

def setup_logging(name: str, level: str = "INFO", log_file: Optional[str] = None):
    """设置日志配置"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def load_json_config(config_path: str, default_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """加载JSON配置文件"""
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif default_config:
            # 创建默认配置文件
            save_json_config(config_path, default_config)
            return default_config
        else:
            return {}
    except Exception as e:
        logging.error(f"加载配置文件失败 {config_path}: {e}")
        return default_config or {}

def save_json_config(config_path: str, config: Dict[str, Any]):
    """保存JSON配置文件"""
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"保存配置文件失败 {config_path}: {e}")

def generate_filename(node_id: int, extension: str = "jpg") -> str:
    """生成带时间戳的文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return f"node_{node_id}_{timestamp}.{extension}"

def calculate_file_hash(file_path: str) -> Optional[str]:
    """计算文件MD5哈希值"""
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"计算文件哈希失败 {file_path}: {e}")
        return None

def ensure_directory(directory: str):
    """确保目录存在"""
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        logging.error(f"创建目录失败 {directory}: {e}")

async def retry_async(func, max_retries: int = 3, delay: float = 1.0, *args, **kwargs):
    """异步重试装饰器"""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            logging.warning(f"重试 {attempt + 1}/{max_retries}: {e}")
            await asyncio.sleep(delay * (attempt + 1))

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    import platform
    import psutil
    
    try:
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_usage": psutil.disk_usage('/').percent
        }
    except Exception as e:
        logging.error(f"获取系统信息失败: {e}")
        return {}

class AsyncTimer:
    """异步定时器"""
    def __init__(self, interval: float, callback, *args, **kwargs):
        self.interval = interval
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.task = None
        self.running = False
    
    async def start(self):
        """启动定时器"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run())
    
    async def stop(self):
        """停止定时器"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
    
    async def _run(self):
        """定时器运行循环"""
        while self.running:
            try:
                await asyncio.sleep(self.interval)
                if self.running:
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(*self.args, **self.kwargs)
                    else:
                        self.callback(*self.args, **self.kwargs)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"定时器回调异常: {e}")

def validate_ip_address(ip: str) -> bool:
    """验证IP地址格式"""
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def get_local_ip() -> Optional[str]:
    """获取本地IP地址"""
    import socket
    try:
        # 连接到一个远程地址来获取本地IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None