// 摄像头查看器 - 处理视频流和图片查看
class CameraViewer {
    constructor() {
        this.currentStream = null;
        this.streamUrl = null;
        this.isStreaming = false;
        
        this.init();
    }
    
    init() {
        this.setupImageModal();
    }
    
    setupImageModal() {
        // 为历史记录中的图片添加点击事件
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('history-image')) {
                this.showImageModal(e.target.src, e.target.alt);
            }
        });
    }
    
    startPreviewStream(nodeId) {
        if (this.isStreaming && this.currentStream === nodeId) {
            return; // 已经在播放相同的流
        }
        
        this.stopPreviewStream();
        
        const previewImage = document.getElementById('preview-image');
        const placeholder = document.getElementById('preview-placeholder');
        
        // 构建流URL
        this.streamUrl = `/stream/${nodeId}`;
        this.currentStream = nodeId;
        
        // 尝试加载MJPEG流
        this.loadMJPEGStream(previewImage, placeholder);
    }
    
    loadMJPEGStream(imageElement, placeholderElement) {
        const img = new Image();
        
        img.onload = () => {
            imageElement.src = this.streamUrl;
            imageElement.style.display = 'block';
            placeholderElement.style.display = 'none';
            this.isStreaming = true;
            
            console.log(`开始播放摄像头 ${this.currentStream} 的预览流`);
        };
        
        img.onerror = () => {
            console.error(`无法加载摄像头 ${this.currentStream} 的预览流`);
            this.showStreamError(placeholderElement);
        };
        
        // 设置一个较短的超时时间来测试流是否可用
        setTimeout(() => {
            if (!this.isStreaming) {
                console.warn(`摄像头 ${this.currentStream} 预览流加载超时，使用静态预览`);
                this.showStaticPreview(imageElement, placeholderElement);
            }
        }, 3000);
        
        img.src = this.streamUrl;
    }
    
    showStaticPreview(imageElement, placeholderElement) {
        // 显示静态预览图或摄像头信息
        placeholderElement.innerHTML = `
            <div class="camera-preview-info">
                <h3>摄像头 ${this.currentStream}</h3>
                <p>预览流暂不可用</p>
                <p>点击拍摄按钮进行拍照</p>
            </div>
        `;
        placeholderElement.style.display = 'flex';
        imageElement.style.display = 'none';
    }
    
    showStreamError(placeholderElement) {
        placeholderElement.innerHTML = `
            <div class="camera-preview-error">
                <h3>⚠️ 预览错误</h3>
                <p>无法连接到摄像头 ${this.currentStream}</p>
                <p>请检查摄像头状态</p>
            </div>
        `;
        placeholderElement.style.display = 'flex';
        this.isStreaming = false;
    }
    
    stopPreviewStream() {
        if (this.isStreaming) {
            const previewImage = document.getElementById('preview-image');
            const placeholder = document.getElementById('preview-placeholder');
            
            previewImage.src = '';
            previewImage.style.display = 'none';
            placeholder.innerHTML = '<p>选择摄像头开始预览</p>';
            placeholder.style.display = 'flex';
            
            this.isStreaming = false;
            this.currentStream = null;
            this.streamUrl = null;
            
            console.log('停止预览流');
        }
    }
    
    showImageModal(imageSrc, imageInfo) {
        const modal = document.getElementById('image-modal');
        const modalImage = document.getElementById('modal-image');
        const modalInfo = document.getElementById('modal-info-text');
        
        modalImage.src = imageSrc;
        modalInfo.textContent = imageInfo || '查看图片';
        modal.style.display = 'block';
    }
    
    captureSnapshot() {
        if (!this.isStreaming) {
            console.warn('没有活动的预览流，无法捕获快照');
            return null;
        }
        
        try {
            const previewImage = document.getElementById('preview-image');
            
            // 创建canvas来捕获当前帧
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = previewImage.naturalWidth || previewImage.width;
            canvas.height = previewImage.naturalHeight || previewImage.height;
            
            ctx.drawImage(previewImage, 0, 0, canvas.width, canvas.height);
            
            // 转换为数据URL
            const dataURL = canvas.toDataURL('image/jpeg', 0.8);
            
            console.log('捕获预览快照成功');
            return dataURL;
            
        } catch (error) {
            console.error('捕获预览快照失败:', error);
            return null;
        }
    }
    
    downloadImage(imageSrc, filename) {
        try {
            const link = document.createElement('a');
            link.href = imageSrc;
            link.download = filename || `camera_image_${Date.now()}.jpg`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            console.log('图片下载开始:', filename);
        } catch (error) {
            console.error('图片下载失败:', error);
        }
    }
    
    // 获取当前预览的摄像头ID
    getCurrentCamera() {
        return this.currentStream;
    }
    
    // 检查是否正在播放预览流
    isPreviewActive() {
        return this.isStreaming;
    }
}

// 创建全局实例
document.addEventListener('DOMContentLoaded', () => {
    window.cameraViewer = new CameraViewer();
    
    // 将查看器集成到主应用中
    if (window.cameraApp) {
        // 扩展主应用的摄像头切换功能
        const originalUpdatePreview = window.cameraApp.updatePreview;
        window.cameraApp.updatePreview = function(nodeId) {
            originalUpdatePreview.call(this, nodeId);
            if (nodeId) {
                window.cameraViewer.startPreviewStream(nodeId);
            } else {
                window.cameraViewer.stopPreviewStream();
            }
        };
    }
});