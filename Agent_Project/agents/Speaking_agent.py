# agents/Speaking_agent.py
import asyncio
import base64

import json
from datetime import datetime


import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

# load_dotenv() 会自动向上一级一层层寻找 .env 文件并加载
load_dotenv()

# 从环境变量中安全读取 API Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

if not DASHSCOPE_API_KEY:
    raise ValueError("⚠️ 找不到 API Key！请检查根目录的 .env 文件配置。")

# 初始化异步客户端
client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
# ================= 核心配置区 =================
"""
# 🚨 替换为您在阿里云百炼申请的真实 API Key
DASHSCOPE_API_KEY = "sk-1b296af163cc432483a8393a6eda87b01"

# 初始化异步客户端
client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
"""
# ============================================


# ---------------------------------------------------------
# 节点一：视觉感知层 (Perception Node - VLM)
# 职责：只做客观的图像结构化提取，不带考官人设。
# ---------------------------------------------------------
async def vlm_perception_node(session_id, base64_image):
    print(f"[雅思口语模块] Session {session_id}: 👀 正在呼叫 VLM 作为眼睛解析图片...")
    try:
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
                            "text": (
                                "你是一个图像实体提取器。请分析这张第一人称视角的图片，提取出场景的客观信息。\n"
                                "请严格以 JSON 格式输出，必须包含以下三个字段：\n"
                                "1. 'scene' (主场景，如 cafe, bedroom)\n"
                                "2. 'objects' (显著物体列表，使用英文，不超过5个)\n"
                                "3. 'mood' (场景氛围描述)\n"
                                "不要输出任何多余的解释文字，只输出一段合法的 JSON。"
                            )
                        }
                    ]
                }
            ]
        )
        vlm_json_str = response.choices[0].message.content

        # 容错处理：清洗大模型可能带有的 Markdown 格式块 (```json ... ```)
        if vlm_json_str.startswith("```"):
            vlm_json_str = vlm_json_str.strip("`").replace("json\n", "", 1)

        vlm_data = json.loads(vlm_json_str)

        # 🎯 核心需求：在后端控制台进行过程可视化，不返回给用户
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 [节点一] VLM 视觉提取结果 (内部感知数据):")
        print(json.dumps(vlm_data, indent=2, ensure_ascii=False))
        print("-" * 50)

        return vlm_data

    except Exception as e:
        print(f"[雅思口语模块] ❌ VLM 解析失败: {e}")
        # 兜底数据，防止流程中断
        return {"scene": "unknown place", "objects": ["nothing clear"], "mood": "unknown"}


# ---------------------------------------------------------
# 节点二：大脑认知层 (Cognition Node - 纯文本 LLM)
# 职责：结合 VLM 传来的 JSON，扮演考官提问。
# ---------------------------------------------------------
async def llm_cognition_node_mock(session_id, vlm_data):
    print(f"[雅思口语模块] Session {session_id}: 🧠 正在呼叫 LLM 大脑生成问题...")

    # 这里目前是一个轻量级的占位逻辑，未来将接入 Qwen-Max 和 LangGraph
    scene = vlm_data.get("scene", "somewhere")
    objects = ", ".join(vlm_data.get("objects", []))

    # 模拟纯文本 LLM 接收了感知数据后做出的决策
    generated_question = f"I notice you are currently at a {scene}. I can see {objects} around you. How often do you spend time in places like this?"

    return generated_question


# ---------------------------------------------------------
# 流水线编排 (Pipeline Orchestration)
# ---------------------------------------------------------
async def process_image(session_id, base64_data):
    try:
        # 1. (可选) 保存图片日志
        image_bytes = base64.b64decode(base64_data)
        save_dir = "received_images/ielts"
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{save_dir}/img_{session_id}_{datetime.now().strftime('%H%M%S')}.webp"
        with open(filename, "wb") as f:
            f.write(image_bytes)

        # 2. 触发节点一：调用 VLM 获取结构化 JSON
        vlm_extracted_data = await vlm_perception_node(session_id, base64_data)

        # 3. 触发节点二：将 JSON 传给大脑生成真正的考官对话
        # 这样前端 Tester.html 收到的就只是一句干练的英文问题了
        final_question = await llm_cognition_node_mock(session_id, vlm_extracted_data)

        return final_question

    except Exception as e:
        print(f"[雅思口语模块] ❌ 图像流程处理失败: {e}")
        return "I'm having trouble seeing your environment right now. Could you describe where you are?"


async def process_audio(session_id, base64_data):
    print(f"[雅思口语模块] Session {session_id}: 🎙️ 正在处理语音回答...")
    return "This is a placeholder for ASR processing."


# ⭐ 这是暴露给主网关(Agent_Main)的统一入口
async def handle_request(event_type, session_id, payload):
    if event_type == "upload_image":
        base64_img = payload.get("data")
        result = await process_image(session_id, base64_img)
        return {"status": "success", "data": result}
    elif event_type == "upload_audio":
        base64_audio = payload.get("data")
        result = await process_audio(session_id, base64_audio)
        return {"status": "success", "data": result}
    else:
        return {"status": "error", "message": f"雅思模块不支持该动作: {event_type}"}