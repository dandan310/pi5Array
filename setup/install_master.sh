#!/bin/bash
# 树莓派4主控制器安装脚本

echo "=== 树莓派多角度摄影系统 - 主控制器安装 ==="

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用sudo运行此脚本"
    exit 1
fi

# 更新系统
echo "更新系统包..."
apt update && apt upgrade -y

# 安装Python依赖
echo "安装Python和pip..."
apt install -y python3 python3-pip python3-venv

# 安装系统依赖
echo "安装系统依赖..."
apt install -y git curl wget

# 配置时间同步服务
echo "配置时间同步..."
# 使用systemd-timesyncd替代ntp
systemctl enable systemd-timesyncd
systemctl start systemd-timesyncd

# 配置时间同步服务器
cat > /etc/systemd/timesyncd.conf << EOF
[Time]
NTP=pool.ntp.org time.nist.gov time.google.com cn.pool.ntp.org
FallbackNTP=0.debian.pool.ntp.org 1.debian.pool.ntp.org 2.debian.pool.ntp.org 3.debian.pool.ntp.org
RootDistanceMaxSec=5
PollIntervalMinSec=32
PollIntervalMaxSec=2048
EOF

# 重启时间同步服务
systemctl restart systemd-timesyncd

# 创建项目目录
PROJECT_DIR="/opt/camera_array"
echo "创建项目目录: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 创建Python虚拟环境
echo "创建Python虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装Python包
echo "安装Python依赖包..."
pip install --upgrade pip
pip install aiohttp aiohttp-cors asyncio ntplib

# 复制项目文件
echo "复制项目文件..."
# 这里应该复制实际的项目文件
# cp -r /path/to/source/* $PROJECT_DIR/

# 设置权限
echo "设置文件权限..."
chown -R pi:pi $PROJECT_DIR
chmod +x $PROJECT_DIR/start_master.py

# 创建图片存储目录
mkdir -p /opt/camera_images
chown pi:pi /opt/camera_images

# 创建systemd服务
echo "创建systemd服务..."
cat > /etc/systemd/system/camera-master.service << EOF
[Unit]
Description=Camera Array Master Controller
After=network.target systemd-timesyncd.service

[Service]
Type=simple
User=pi
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/start_master.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
echo "启用服务..."
systemctl daemon-reload
systemctl enable camera-master.service

# 配置网络
echo "配置网络..."
# 设置静态IP (可选)
# 这里可以添加网络配置代码

# 创建日志目录
mkdir -p /var/log/camera-array
chown pi:pi /var/log/camera-array

echo "=== 主控制器安装完成 ==="
echo "使用以下命令启动服务:"
echo "sudo systemctl start camera-master"
echo "查看服务状态:"
echo "sudo systemctl status camera-master"
echo "查看日志:"
echo "journalctl -u camera-master -f"