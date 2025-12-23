#!/usr/bin/env python3
# 时间同步测试脚本
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.ntp_sync import ntp_client

async def test_time_sync():
    """测试时间同步功能"""
    print("=== 时间同步测试 ===")
    
    print("1. 测试systemd-timesyncd同步...")
    success = await ntp_client.sync_time()
    
    if success:
        print(f"✓ 时间同步成功")
        print(f"  当前时间: {ntp_client.format_time()}")
        print(f"  时间偏移: {ntp_client.time_offset:.3f}秒")
        print(f"  同步状态: {'已同步' if ntp_client.is_synchronized() else '未同步'}")
    else:
        print("✗ 时间同步失败")
        return False
    
    print("\n2. 测试定时拍摄调度...")
    from shared.ntp_sync import scheduled_capture
    
    session_id = scheduled_capture.generate_session_id()
    capture_time = await scheduled_capture.schedule_capture(session_id, 2.0)
    
    print(f"  会话ID: {session_id}")
    print(f"  计划拍摄时间: {ntp_client.format_time(capture_time)}")
    
    # 测试文件名生成
    filename = scheduled_capture.generate_filename(1, capture_time)
    print(f"  生成文件名: {filename}")
    
    print("\n✓ 所有测试通过！")
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_time_sync())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试失败: {e}")
        sys.exit(1)