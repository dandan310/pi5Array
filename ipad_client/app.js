// 主应用程序
class CameraApp {
    constructor() {
        this.ws = null;
        this.cameras = [];
        this.currentCamera = null;
        this.captureHistory = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadCaptureHistory();
    }
    
    setupEventListeners() {
        // 拍摄按钮
        document.getElementById('capture-btn').addEventListener('click', () => {
            this.triggerCapture();
        });
        
        // 模态框关闭
        document.querySelector('.close').addEventListener('click', () => {
            document.getElementById('image-modal').style.display = 'none';
        });
        
        // 点击模态框外部关闭
        document.getElementById('image-modal').addEventListener('click', (e) => {
            if (e.target.id === 'image-modal') {
                document.getElementById('image-modal').style.display = 'none';
            }
        });
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket连接成功');
                this.updateConnectionStatus(true);
                this.reconnectAttempts = 0;
                this.requestCameraList();
            };
            
            this.ws.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket连接关闭');
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('WebSocket连接失败:', error);
            this.updateConnectionStatus(false);
            this.attemptReconnect();
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => {
                this.connectWebSocket();
            }, 3000 * this.reconnectAttempts);
        } else {
            console.error('达到最大重连次数，停止重连');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'camera_list':
                this.updateCameraList(data.data);
                this.updateCameraStats(data);
                break;
            case 'camera_list_updated':
                // 实时更新摄像头列表
                this.updateCameraList(data.data);
                this.updateCameraStats(data);
                this.showNotification(`摄像头列表已更新 (在线: ${data.online_count}, 就绪: ${data.ready_count})`, 'info');
                break;
            case 'camera_switched':
                this.handleCameraSwitched(data);
                break;
            case 'ready_status':
                this.handleReadyStatus(data);
                break;
            case 'capture_scheduled':
                this.handleCaptureScheduled(data);
                break;
            default:
                console.log('未知消息类型:', data.type);
        }
    }
    
    sendWebSocketMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.error('WebSocket未连接');
        }
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (connected) {
            statusElement.textContent = '在线';
            statusElement.className = 'status online';
        } else {
            statusElement.textContent = '离线';
            statusElement.className = 'status offline';
        }
    }
    
    requestCameraList() {
        this.sendWebSocketMessage({ type: 'get_cameras' });
    }
    
    updateCameraList(cameras) {
        this.cameras = cameras;
        this.renderCameraGrid();
        this.updateCaptureButton();
    }
    
    updateCameraStats(data) {
        // 更新统计信息
        const onlineCount = data.online_count || this.cameras.filter(c => c.status === 'online').length;
        const readyCount = data.ready_count || this.cameras.filter(c => c.is_ready).length;
        const totalCount = this.cameras.length;
        
        document.getElementById('camera-count').textContent = 
            `摄像头: ${onlineCount}/${totalCount} 在线, ${readyCount} 就绪`;
    }
    
    renderCameraGrid() {
        const grid = document.getElementById('camera-grid');
        grid.innerHTML = '';
        
        // 按节点ID排序
        const sortedCameras = [...this.cameras].sort((a, b) => a.node_id - b.node_id);
        
        sortedCameras.forEach(camera => {
            const card = document.createElement('div');
            card.className = `camera-card ${camera.status}`;
            if (this.currentCamera === camera.node_id) {
                card.classList.add('active');
            }
            if (camera.is_ready) {
                card.classList.add('ready');
            }
            
            // 计算最后心跳时间
            const lastHeartbeat = camera.last_heartbeat ? 
                Math.floor((Date.now() / 1000) - camera.last_heartbeat) : 0;
            
            card.innerHTML = `
                <div class="camera-info">
                    <h3>摄像头 ${camera.node_id}</h3>
                    <p class="camera-status ${camera.status}">${this.getStatusText(camera.status)}</p>
                    <p class="camera-ready ${camera.is_ready ? 'ready' : 'not-ready'}">
                        ${camera.is_ready ? '✓ 就绪' : '⚠ 未就绪'}
                    </p>
                    <p class="camera-ip">${camera.ip_address}:${camera.node_port || 8084}</p>
                    ${lastHeartbeat > 0 ? `<p class="camera-heartbeat">${lastHeartbeat}秒前</p>` : ''}
                </div>
            `;
            
            if (camera.status === 'online') {
                card.addEventListener('click', () => {
                    this.switchCamera(camera.node_id);
                });
            }
            
            grid.appendChild(card);
        });
        
        // 如果没有摄像头，显示提示
        if (sortedCameras.length === 0) {
            grid.innerHTML = `
                <div class="no-cameras">
                    <p>等待摄像头节点连接...</p>
                    <p>请确保摄像头节点已启动并连接到网络</p>
                </div>
            `;
        }
    }
    
    updateCaptureButton() {
        const readyCount = this.cameras.filter(c => c.is_ready).length;
        const onlineCount = this.cameras.filter(c => c.status === 'online').length;
        const captureBtn = document.getElementById('capture-btn');
        
        if (readyCount > 0) {
            captureBtn.disabled = false;
            captureBtn.innerHTML = `
                <span class="capture-icon">📷</span>
                拍摄 (${readyCount}个就绪)
            `;
        } else if (onlineCount > 0) {
            captureBtn.disabled = true;
            captureBtn.innerHTML = `
                <span class="capture-icon">📷</span>
                等待就绪... (${onlineCount}个在线)
            `;
        } else {
            captureBtn.disabled = true;
            captureBtn.innerHTML = `
                <span class="capture-icon">📷</span>
                等待连接...
            `;
        }
    }
    
    getStatusText(status) {
        const statusMap = {
            'online': '在线',
            'offline': '离线',
            'capturing': '拍摄中',
            'error': '错误'
        };
        return statusMap[status] || status;
    }
    
    updateCameraCount() {
        // 这个方法现在由updateCameraStats替代
        // 保留以防兼容性问题
    }
    
    switchCamera(nodeId) {
        this.sendWebSocketMessage({
            type: 'switch_camera',
            node_id: nodeId
        });
    }
    
    handleCameraSwitched(data) {
        if (data.success) {
            this.currentCamera = data.current_node;
            this.renderCameraGrid();
            this.updatePreview(data.current_node);
        }
    }
    
    updatePreview(nodeId) {
        const previewImage = document.getElementById('preview-image');
        const placeholder = document.getElementById('preview-placeholder');
        
        if (nodeId) {
            // 这里应该显示实际的摄像头预览流
            // 暂时显示占位符
            previewImage.src = `/stream/${nodeId}`;
            previewImage.style.display = 'block';
            placeholder.style.display = 'none';
        } else {
            previewImage.style.display = 'none';
            placeholder.style.display = 'flex';
        }
    }
    
    triggerCapture() {
        // 先检查就绪状态
        this.showLoading('检查摄像头就绪状态...');
        
        this.sendWebSocketMessage({
            type: 'check_ready'
        });
    }
    
    handleReadyStatus(data) {
        const readyNodes = Object.entries(data.ready_status)
            .filter(([nodeId, ready]) => ready)
            .map(([nodeId, ready]) => parseInt(nodeId));
        
        if (readyNodes.length === 0) {
            this.hideLoading();
            this.showNotification('没有就绪的摄像头，请检查设备状态', 'warning');
            return;
        }
        
        // 显示就绪状态并开始拍摄
        this.showLoading(`${readyNodes.length}个摄像头就绪，准备拍摄...`);
        
        setTimeout(() => {
            this.sendWebSocketMessage({
                type: 'trigger_capture',
                delay_seconds: 0.5
            });
        }, 1000);
    }
    
    handleCaptureScheduled(data) {
        this.hideLoading();
        
        const result = data.result;
        if (result.success) {
            const readyCount = result.ready_nodes.length;
            const captureTime = new Date(result.capture_time * 1000).toLocaleTimeString();
            
            // 添加到历史记录
            this.addCaptureHistory({
                timestamp: new Date(result.capture_time * 1000).toISOString(),
                session_id: result.session_id,
                ready_nodes: result.ready_nodes,
                capture_time_formatted: result.capture_time_formatted
            });
            
            this.showNotification(
                `拍摄已安排！${readyCount}个摄像头将在 ${captureTime} 同步拍摄`, 
                'success'
            );
        } else {
            this.showNotification(`拍摄安排失败: ${result.error}`, 'error');
        }
    }
    
    addCaptureHistory(capture) {
        this.captureHistory.unshift(capture);
        
        // 限制历史记录数量
        if (this.captureHistory.length > 10) {
            this.captureHistory = this.captureHistory.slice(0, 10);
        }
        
        this.renderCaptureHistory();
        this.saveCaptureHistory();
    }
    
    renderCaptureHistory() {
        const historyContainer = document.getElementById('capture-history');
        
        if (this.captureHistory.length === 0) {
            historyContainer.innerHTML = '<p class="no-history">暂无拍摄记录</p>';
            return;
        }
        
        historyContainer.innerHTML = this.captureHistory.map(capture => {
            const time = new Date(capture.timestamp).toLocaleString('zh-CN');
            
            if (capture.ready_nodes) {
                // 新格式：NTP定时拍摄
                return `
                    <div class="history-item">
                        <div class="history-time">${time}</div>
                        <div class="history-session">会话: ${capture.session_id}</div>
                        <div class="history-cameras">
                            就绪摄像头: ${capture.ready_nodes.join(', ')}
                        </div>
                        <div class="history-schedule">
                            拍摄时间: ${capture.capture_time_formatted}
                        </div>
                    </div>
                `;
            } else {
                // 旧格式：兼容性
                return `
                    <div class="history-item">
                        <div class="history-time">${time}</div>
                        <div class="history-cameras">
                            成功: ${capture.successCount}/${capture.totalCount} 个摄像头
                        </div>
                    </div>
                `;
            }
        }).join('');
    }
    
    showCaptureResult(successCount, totalCount) {
        if (successCount === totalCount) {
            this.showNotification(`拍摄成功！所有 ${totalCount} 个摄像头都已完成拍摄。`, 'success');
        } else {
            this.showNotification(`拍摄完成！${successCount}/${totalCount} 个摄像头拍摄成功。`, 'warning');
        }
    }
    
    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // 添加样式
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '15px 20px',
            borderRadius: '8px',
            color: 'white',
            fontWeight: '600',
            zIndex: '1000',
            maxWidth: '300px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
        });
        
        // 设置背景色
        const colors = {
            success: '#28a745',
            warning: '#ffc107',
            error: '#dc3545',
            info: '#007bff'
        };
        notification.style.backgroundColor = colors[type] || colors.info;
        
        document.body.appendChild(notification);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
    
    showLoading(message = '处理中...') {
        const loading = document.getElementById('loading');
        loading.querySelector('p').textContent = message;
        loading.style.display = 'flex';
    }
    
    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }
    
    loadCaptureHistory() {
        try {
            const saved = localStorage.getItem('captureHistory');
            if (saved) {
                this.captureHistory = JSON.parse(saved);
                this.renderCaptureHistory();
            }
        } catch (error) {
            console.error('加载历史记录失败:', error);
        }
    }
    
    saveCaptureHistory() {
        try {
            localStorage.setItem('captureHistory', JSON.stringify(this.captureHistory));
        } catch (error) {
            console.error('保存历史记录失败:', error);
        }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    window.cameraApp = new CameraApp();
});