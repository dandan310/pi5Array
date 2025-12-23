#!/bin/bash
# 树莓派5摄像头节点安装脚本

echo "=== 树莓派多角度摄影系统 - 摄像头节点安装 ==="

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

# 安装摄像头相关依赖
echo "安装摄像头依赖..."
apt install -y python3-picamera2 python3-libcamera python3-kms++
apt install -y python3-prctl libatlas-base-dev ffmpeg

# 安装时间同步服务
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

# 启用摄像头
echo "启用摄像头..."
raspi-config nonint do_camera 0

# 创建项目目录
PROJECT_DIR="/opt/camera_node"
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
pip install asyncio aiohttp ntplib

# 复制项目文件
echo "复制项目文件..."
# 这里应该复制实际的项目文件
# cp -r /path/to/source/camera_node/* $PROJECT_DIR/
# cp -r /path/to/source/shared $PROJECT_DIR/

# 设置权限
echo "设置文件权限..."
chown -R pi:pi $PROJECT_DIR
chmod +x $PROJECT_DIR/start_node.py

# 创建systemd服务（支持自动分配ID）
echo "创建systemd服务..."
cat > /etc/systemd/system/camera-node.service << EOF
[Unit]
Description=Camera Array Node (Auto ID)
After=network.target systemd-timesyncd.service

[Service]
Type=simple
User=pi
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/start_node.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
echo "启用服务..."
systemctl daemon-reload
systemctl enable camera-node.service

# 创建图片存储目录
mkdir -p /tmp/camera_images
chown pi:pi /tmp/camera_images

# 创建日志目录
mkdir -p /var/log/camera-node
chown pi:pi /var/log/camera-node

echo "=== 摄像头节点安装完成 ==="
echo "节点将自动发现主控制器并分配ID"
echo "重启系统以应用配置:"
echo "sudo reboot"
echo ""
echo "重启后使用以下命令启动服务:"
echo "sudo systemctl start camera-node"
echo "查看服务状态:"
echo "sudo systemctl status camera-node"
echo "查看日志:"
echo "journalctl -u camera-node -f"
echo ""
echo "也可以手动启动测试:"
echo "python3 /opt/camera_node/start_node.py"