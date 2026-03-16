import asyncio
import websockets
import os
from datetime import datetime

# 创建一个专门存放抓拍图片的文件夹
SAVE_DIR = "received_images"
os.makedirs(SAVE_DIR, exist_ok=True)


async def handle_client(websocket):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ 手机端已成功连接到服务器！")
    try:
        # 持续监听通道里传来的消息
        async for message in websocket:
            # 判断如果收到的是字节流（二进制数据）
            if isinstance(message, bytes):
                # 根据当前时间生成一个文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                # 官方底层获取的 ByteArray 默认是 WebP 格式
                filename = f"glass_capture_{timestamp}.webp"
                filepath = os.path.join(SAVE_DIR, filename)

                # 将字节流写入文件并保存
                with open(filepath, "wb") as f:
                    f.write(message)

                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 📸 成功接收并保存图片: {filename} (大小: {len(message)} 字节)")



                # ================== 【新增代码】 ==================
                # 模拟大模型思考后生成的雅思口语题目，顺着通道发回手机
                question_text = "Please describe the environment you are looking at in English."
                await websocket.send(question_text)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 已下发题目: {question_text}")
                # =================================================
            # 如果收到的是普通的文本消息（备用）
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 💬 收到文本消息: {message}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 手机端连接已断开。")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 发生异常: {e}")


async def main():
    # 监听 0.0.0.0 表示允许局域网内任何设备连接，端口设为 8765
    print("🚀 WebSocket 服务器已启动！")
    print("正在监听 ws://0.0.0.0:8765 ... (等待手机端连接)")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()  # 让服务器永远运行下去不退出


if __name__ == "__main__":
    asyncio.run(main())