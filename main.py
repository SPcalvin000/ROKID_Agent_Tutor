import asyncio
import websockets
import os
import base64
from datetime import datetime
from openai import AsyncOpenAI  # 引入异步的 OpenAI 客户端

# ================= 核心配置区 =================
# 🚨 替换为您在阿里云百炼申请的真实 API Key
DASHSCOPE_API_KEY = "sk-1b296af163cc432483a8393a6eda87b0"

# 初始化异步客户端，指向阿里云的兼容接口
client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
# ============================================

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

                # ================== 【接入 VLM 大脑】 ==================
                try:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 正在呼叫 Qwen-VL 大脑分析图片...")

                    # 1. 将内存中刚收到的字节流直接转换为 Base64 编码
                    base64_image = base64.b64encode(message).decode('utf-8')

                    # 2. 调用千问视觉大模型 (qwen-vl-plus)
                    response = await client.chat.completions.create(
                        model="qwen-vl-plus",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/webp;base64,{base64_image}"}
                                    },
                                    {
                                        "type": "text",
                                        # 🎯 全新升级的 Prompt：要求返回描述 + 关联问题，并用 ||| 分隔
                                        "text": "你是一个雅思口语考官。请看这张第一人称视角的图片。\n"
                                                "1. 先用英文极简地描述图片内容（约10个单词）。\n"
                                                "2. 然后根据该场景，提出一个雅思口语 Part 1 风格的英文问题。\n"
                                                "请严格使用 '|||' 作为分隔符，格式必须为：描述内容|||英文问题"
                                    }
                                ]
                            }
                        ]
                    )

                    # 3. 提取生成的复合文本 (例如: "I see a laptop on a desk.|||How often do you use a computer for work or study?")
                    vlm_question = response.choices[0].message.content

                    # 4. 顺着通道发回手机
                    await websocket.send(vlm_question)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 已下发 VLM 复合题目: {vlm_question}")

                except Exception as api_error:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ VLM 调用失败: {api_error}")
                    # 容错机制：兜底文本也要加上 ||| 分隔符，保证眼镜端解析不报错
                    fallback_text = "I notice the connection is unstable.|||Could you just describe what is in front of you right now?"
                    await websocket.send(fallback_text)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 已下发兜底题目: {fallback_text}")
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