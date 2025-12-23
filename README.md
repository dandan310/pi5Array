# 树莓派多角度摄影系统

## 系统架构
- **主控制器**: 树莓派4 (Master Controller)
- **摄像头节点**: 多个树莓派5 + Camera Module 3 (Camera Nodes)
- **客户端**: iPad (通过WiFi连接)

## 功能特性
- 实时预览多个摄像头画面
- 摄像头画面切换
- 同步拍摄触发
- 自动图片传输到iPad

## 项目结构
```
├── master_controller/     # 树莓派4主控程序
├── camera_node/          # 树莓派5摄像头节点程序
├── ipad_client/          # iPad客户端程序
└── shared/               # 共享配置和协议
```

## 通信协议
- 主控与节点: GPIO + I2C/SPI
- 主控与iPad: WiFi (WebSocket + HTTP)