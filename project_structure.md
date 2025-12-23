# 项目目录结构

```
raspberry_pi_camera_array/
├── master_controller/              # 树莓派4主控程序
│   ├── main.py                    # 主程序入口
│   ├── camera_manager.py          # 摄像头管理
│   ├── web_server.py              # Web服务器(与iPad通信)
│   ├── gpio_controller.py         # GPIO控制
│   └── config.py                  # 配置文件
├── camera_node/                   # 树莓派5节点程序
│   ├── node_client.py             # 节点客户端
│   ├── camera_handler.py          # 摄像头处理
│   ├── gpio_listener.py           # GPIO监听
│   └── config.py                  # 节点配置
├── ipad_client/                   # iPad客户端
│   ├── index.html                 # 主界面
│   ├── app.js                     # 前端逻辑
│   ├── style.css                  # 样式
│   └── camera_viewer.js           # 摄像头查看器
├── shared/                        # 共享文件
│   ├── protocol.py                # 通信协议定义
│   └── utils.py                   # 工具函数
└── setup/                         # 安装脚本
    ├── install_master.sh          # 主控安装脚本
    └── install_node.sh            # 节点安装脚本
```