# agents/Speaking_agent.py
import asyncio
import uuid
import base64
import json
import os
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional
import redis  # 🌟 新增：引入 Redis 库
import dashscope
from dotenv import load_dotenv
from openai import AsyncOpenAI
import dashscope
from dashscope import MultiModalConversation
# 导入 LangChain & LangGraph 核心组件
# 把它删掉！我们不再需要臃肿的 langchain_openai
# from langchain_openai import ChatOpenAI

# 这行也可以删掉，因为我们现在使用的是原生字典格式 {"role": "user", "content": "..."}
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
# 🌟 引入刚配置好的数据库基建
from pymilvus import MilvusClient
# 加载环境变量
# load_dotenv() 会自动向上一级一层层寻找 .env 文件并加载
load_dotenv()

# ================= 新增：防止本地代理(Clash/VPN)拦截阿里云请求 =================
os.environ["NO_PROXY"] = "dashscope.aliyuncs.com,aliyuncs.com"
# =========================================================================

# 从环境变量中安全读取 API Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
# 🌟 新增：配置原生 SDK 的 API Key
dashscope.api_key = DASHSCOPE_API_KEY

if not DASHSCOPE_API_KEY:
    raise ValueError("⚠️ 找不到 API Key！请检查根目录的 .env 文件配置。")

# 初始化原生异步客户端（专供 VLM 节点使用）
native_client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
# =========================================================
# 🌟 全局初始化 Milvus 检索引擎客户端 (RAG 底座)
# =========================================================
try:
    print("[系统初始化] 🔌 正在连接 Milvus 长期记忆库...")
    # 我们刚刚已经证明了 localhost 是通的！
    rag_client = MilvusClient(uri="http://localhost:19530")
    print("[系统初始化] 🟢 长期记忆库就绪！")
except Exception as e:
    print(f"[系统初始化] ⚠️ Milvus 未启动或连接失败，将降级为无记忆模式: {e}")
    rag_client = None
# =========================================================
# 🌟 全局初始化 Redis 状态机缓存 (接管 Session Memory)
# =========================================================
try:
    print("[系统初始化] 🔌 正在连接 Docker Redis 状态机缓存 (Port: 6379)...")
    # decode_responses=True 确保直接取出的就是字符串而不是 bytes
    redis_client = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True, socket_timeout=5.0)
    redis_client.ping()  # 触发一次真实连接测试
    print("[系统初始化] 🟢 Redis 状态缓存器已成功挂载！")
except Exception as e:
    print(f"[系统初始化] ⚠️ Redis 连接失败，将降级为本地内存模式: {e}")
    redis_client = None

# 为了保证绝对的物理隔离和安全，你可以保留一个空的字典作为极端情况下的降级备用
session_memory: Dict[str, Dict[str, Any]] = {}
# =========================================================
# 1. 定义图状态 (AgentState)
# =========================================================
class AgentState(TypedDict):
    chat_history: List[Dict[str, str]]
    visual_context: Dict[str, Any]

    # 🌟 为雅思业务逻辑新增的核心状态变量
    current_part: int  # 当前考试阶段 (例如: 2 代表 Part 2, 3 代表 Part 3)
    depth_level: int  # 提问深度层级 (1: 个人层面, 2: 社会层面, 3: 宏观/未来层面)

    turn_count: int
    user_profile: str
    current_image_base64: Optional[str]
    current_user_text: Optional[str]


# =========================================================
# 全局会话状态内存数据库 (Session Memory)
# =========================================================
session_memory: Dict[str, Dict[str, Any]] = {}

# =========================================================
# 全局会话状态内存数据库 (短时 Session Memory)
# =========================================================
session_memory: Dict[str, Dict[str, Any]] = {}


# 辅助函数：实时请求阿里云把场景词变成向量
async def get_query_embedding(text: str) -> list:
    response = await native_client.embeddings.create(
        model="text-embedding-v3",
        input=text
    )
    return response.data[0].embedding


# =========================================================
# 🌟 状态持久化核心逻辑 (Redis 读写)
# =========================================================

async def save_session_to_redis(session_id: str, state: Dict[str, Any]):
    """便利函数：将最新的状态序列化打入 Redis，并设置 24 小时过期保护"""
    if redis_client:
        try:
            # ex=86400 (24小时)，防止死数据永远占用内存
            redis_client.set(f"session:{session_id}", json.dumps(state), ex=86400)
        except Exception as e:
            print(f"[状态机底座] ❌ 同步状态到 Redis 失败: {e}")
    else:
        # 降级方案
        session_memory[session_id] = state


# =========================================================
# 🌟 状态持久化核心逻辑 (Redis 读写)
# =========================================================

async def save_session_to_redis(session_id: str, state: Dict[str, Any]):
    """将最新状态序列化打入 Redis，并设置 24 小时过期保护"""
    if redis_client:
        try:
            redis_client.set(f"session:{session_id}", json.dumps(state), ex=86400)
        except Exception as e:
            print(f"[状态机底座] ❌ 同步状态到 Redis 失败: {e}")


async def get_or_init_session(session_id: str, current_scene: str = "unknown place") -> Dict[str, Any]:
    """从 Redis 读取或初始化会话状态，并融合 Milvus 长期记忆"""

    # 1. 尝试从 Redis 恢复记忆
    if redis_client:
        try:
            saved_state_json = redis_client.get(f"session:{session_id}")
            if saved_state_json:
                print(f"[状态机底座] 💾 成功从 Docker Redis 恢复 Session [{session_id}] 的上下文。")
                return json.loads(saved_state_json)
        except Exception as e:
            print(f"[状态机底座] ⚠️ 从 Redis 读取异常: {e}")

    # 2. 如果 Redis 里没有，初始化全新考局
    print(f"[状态机底座] 🆕 未发现历史 Session，正在为 [{session_id}] 建立全新会话锁...")
    retrieved_profile = ""

    # 触发 Milvus 检索 (提取弱点画像)
    if rag_client and current_scene != "unknown place":
        try:
            search_vec = await get_query_embedding(f"User weakness related to {current_scene}")
            search_results = rag_client.search(
                collection_name="user_weakness_vector_db", data=[search_vec], limit=1, output_fields=["content"]
            )
            if search_results and search_results[0]:
                retrieved_profile = search_results[0][0].get("entity", {}).get("content", "")
        except Exception as e:
            print(f"[RAG 检索模块] ⚠️ 检索失败: {e}")

    # 🌟 3. 构造全新的、带有业务深度的初始状态！
    new_session_state = {
        "chat_history": [],
        "visual_context": {"scene": current_scene, "objects": [], "mood": "unknown"},
        "current_part": 2,  # 👈 默认从 Part 2 开始 (看图描述)
        "depth_level": 1,  # 👈 默认深度 1 (基于个人的基础提问)
        "turn_count": 0,
        "user_profile": retrieved_profile,
        "current_image_base64": None,
        "current_user_text": None
    }

    # 立刻落盘！
    await save_session_to_redis(session_id, new_session_state)
    return new_session_state


# =========================================================
# 2. 编写图节点 (Graph Nodes)
# =========================================================

async def vlm_perception_node(state: AgentState) -> Dict[str, Any]:
    """
    节点一：视觉感知层 (Perception Node - VLM)
    职责：只做客观的图像结构化提取，更新图状态中的 visual_context
    """
    base64_image = state.get("current_image_base64")
    if not base64_image:
        print("[感知节点] ℹ️ 当轮交互未检测到图像输入，跳过视觉解析。")
        return {}

    print("[感知节点] 👀 正在呼叫 Qwen-VL-Plus 解析图片环境...")
    try:
        response = await native_client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{base64_image}"}},
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

        # 容错清洗
        if vlm_json_str.startswith("```"):
            vlm_json_str = vlm_json_str.strip("`").replace("json\n", "", 1)

        vlm_data = json.loads(vlm_json_str)
        print(f"[感知节点] 🔍 VLM 内部感知数据可视化:\n{json.dumps(vlm_data, indent=2, ensure_ascii=False)}")

        # 核心：将提取的视觉上下文作为状态更新返回
        return {"visual_context": vlm_data}

    except Exception as e:
        print(f"[感知节点] ❌ VLM 解析失败: {e}")
        return {}  # 失败时不破坏原有的 visual_context


async def llm_cognition_node(state: AgentState) -> Dict[str, Any]:
    print("[认知节点] 🧠 正在呼叫文本大模型生成考官追问...")

    visual_context = state.get("visual_context", {})
    current_part = state.get("current_part", 2)
    depth_level = state.get("depth_level", 1)
    turn_count = state.get("turn_count", 0)
    user_profile = state.get("user_profile", "")

    # ==========================================================
    # 1. 状态机自动流转 (严格贴合 6 轮规划)
    # ==========================================================
    if turn_count == 2 and current_part == 2:
        current_part = 3
        depth_level = 1
        print(f"[状态机] 🔄 进入 Part 3 - 深度 {depth_level} (身边人)")
    elif turn_count == 3 and current_part == 3:
        depth_level = 2
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level} (社会现象)")
    elif turn_count == 4 and current_part == 3:
        depth_level = 3
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level} (纵向时间线)")
    elif turn_count == 5 and current_part == 3:
        depth_level = 4
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level} (利弊影响)")
    elif turn_count == 6 and current_part == 3:
        depth_level = 5
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level} (差异与解决建议)")
    elif turn_count >= 7 and current_part == 3:
        current_part = 4
        print(f"[状态机] 🛑 达到预设轮数，考试正式结束！")

    # ==========================================================
    # 2. 动态生成 System Prompt (修复复读机与机械化缺陷)
    # ==========================================================
    system_prompt = (
        f"You are a strict, professional, and natural IELTS Speaking Examiner.\n"
        f"Currently, you are conducting **Part {current_part}** of the speaking test.\n"
        "Crucial Rules:\n"
        "1. DO NOT use repetitive, robotic transition phrases like 'I understand that...', 'I see', or 'Let's move on'. Just ask the question directly and naturally.\n"
        "2. Keep your questions concise. NEVER reveal you are an AI.\n\n"
    )

    if current_part == 2:
        if turn_count == 0:
            system_prompt += (
                "Task: The candidate has just entered Part 2. Give them a Cue Card topic based on the image trigger below. "
                "Output the standard instructions: 'I'd like you to describe... You should say... You have one minute to prepare...'. "
                "DO NOT ask any follow-up questions yet.\n"
            )
            if visual_context and visual_context.get("scene") != "unknown place":
                system_prompt += f"[Topic Trigger from Image]: {visual_context.get('scene')}. Visible objects: {', '.join(visual_context.get('objects', []))}.\n"
        else:
            system_prompt += (
                "Task: The candidate has just finished their 2-minute long turn for Part 2. "
                "Ask ONE short, simple follow-up question regarding their personal feelings or a specific detail they mentioned. DO NOT repeat the Cue Card.\n"
            )


    elif current_part == 3:

        system_prompt += (

            "In Part 3, you are conducting a macroscopic, abstract discussion.\n"
            "⚠️ CRITICAL RULES (VIOLATION WILL RESULT IN PENALTY):\n"
            "1. ASK ONLY ONE QUESTION AT A TIME. Never list multiple questions.\n"
            "2. DO NOT ASK PERSONAL QUESTIONS. Never use phrases like 'your own experience', 'your family', or 'you personally'. Talk about 'people', 'society', 'the government', or 'the public'.\n"
            "3. NEVER REPEAT OR REPHRASE PREVIOUS QUESTIONS. You must strictly follow the new 'Current Depth Focus' provided below and actively shift the topic direction.\n\n"

        )
        system_prompt += f">>> CURRENT DEPTH FOCUS (YOU MUST ASK A QUESTION STRICTLY ABOUT THIS): <<<\n"
        if depth_level == 1:
            system_prompt += "[Focus]: How the topic affects DIFFERENT DEMOGRAPHICS (e.g., children vs. adults, men vs. women) in general society. Do not ask about the candidate's personal friends.\n"
        elif depth_level == 2:
            system_prompt += "[Focus]: The underlying REASONS or CAUSES of this societal phenomenon. (e.g., 'Why do you think it is common that...')\n"
        elif depth_level == 3:
            system_prompt += "[Focus]: TIME COMPARISON. Compare the current situation with the past (20 years ago) or predict future trends. Force a shift in timeline.\n"
        elif depth_level == 4:
            system_prompt += "[Focus]: PROS and CONS. Ask about the broader advantages or disadvantages to society, culture, or public health.\n"
        elif depth_level == 5:
            system_prompt += "[Focus]: SOLUTIONS and RESPONSIBILITY. Ask what the government, schools, or communities should do to improve the situation or solve the problems discussed.\n"

    elif current_part == 4:
        system_prompt += (
            "The speaking test is now officially over. "
            "You MUST NOT ask any more questions. "
            "Simply output EXACTLY this closing phrase: 'This is the end of the speaking test. Thank you very much for your time. You can now leave the room.' and nothing else."
        )

    # ==========================================================
    # 3. 组装历史消息并调用 API
    # ==========================================================
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in state.get("chat_history", []):
        api_messages.append(msg)

    updated_history = list(state.get("chat_history", []))
    if state.get("current_user_text"):
        user_text = state["current_user_text"]
        api_messages.append({"role": "user", "content": user_text})
        updated_history.append({"role": "user", "content": user_text})

    try:
        response = await native_client.chat.completions.create(
            model="qwen-max", messages=api_messages, temperature=0.7
        )
        ai_content = response.choices[0].message.content
        print(f"[认知节点] ✅ 生成完毕 (Part {current_part}, Depth {depth_level}): {ai_content}")
    except Exception as e:
        print(f"[认知节点] ❌ 大模型请求失败: {e}")
        ai_content = "I'm having a little trouble hearing you. Could you repeat that?"

    # 🌟 极度关键：将 AI 的回复追加到历史记录中。如果少了这行，就会触发 list index out of range！
    updated_history.append({"role": "assistant", "content": ai_content})

    return {
        "chat_history": updated_history,
        "turn_count": turn_count + 1,
        "current_part": current_part,
        "depth_level": depth_level,
        "current_user_text": None,
        "current_image_base64": None
    }
# =========================================================
# 3. 构建 StateGraph 编排流
# =========================================================

def route_by_input(state: AgentState):
    """路由函数：判定是否包含图片触发视觉感知层"""
    if state.get("current_image_base64"):
        return "vlm_perception"
    return "llm_cognition"


workflow = StateGraph(AgentState)

# 注册节点
workflow.add_node("vlm_perception", vlm_perception_node)
workflow.add_node("llm_cognition", llm_cognition_node)

# 动态条件路由作为入口
workflow.set_conditional_entry_point(
    route_by_input,
    {
        "vlm_perception": "vlm_perception",
        "llm_cognition": "llm_cognition"
    }
)

# 依赖边连接
workflow.add_edge("vlm_perception", "llm_cognition")
workflow.add_edge("llm_cognition", END)

# 编译状态机
compiled_agent = workflow.compile()


# =========================================================
# 4. 流水线核心触发器与外部接口对接
# =========================================================

async def process_image(session_id, base64_data):
    try:
        # 1. 持久化日志 (保持不变)
        image_bytes = base64.b64decode(base64_data)
        save_dir = "received_images/ielts"
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{save_dir}/img_{session_id}_{datetime.now().strftime('%H%M%S')}.webp"
        with open(filename, "wb") as f:
            f.write(image_bytes)

        # 🌟 2. 核心调整：因为 RAG 需要依赖“当前场景”进行搜索，
        # 我们必须稍微改变一下图的流转顺序。先让感知节点（VLM）单独跑一次拿场景词，再初始化 Session！

        # 临时组装一个只含图片的 fake_state 让 VLM 单跑
        fake_state_for_eyes = {"current_image_base64": base64_data}
        vlm_result = await vlm_perception_node(fake_state_for_eyes)
        current_scene = vlm_result.get("visual_context", {}).get("scene", "unknown place")

        # 🌟 3. 带着场景词去初始化 Session（触发我们刚才写的 Milvus 检索）
        session_state = await get_or_init_session(session_id, current_scene=current_scene)

        # 将刚刚看懂的视觉数据正式压入真实状态机
        session_state["visual_context"] = vlm_result.get("visual_context", {})
        # session_state["current_image_base64"] = base64_data
        session_state["current_user_text"] = None

        # 4. 启动图状态机 (流转到大脑节点)
        final_state = await compiled_agent.ainvoke(session_state)

        # 🌟 替换掉这行：session_memory[session_id] = final_state
        await save_session_to_redis(session_id, final_state)

        return final_state["chat_history"][-1]["content"]



    except Exception as e:
        print(f"[雅思口语模块] ❌ 图像图计算流程失败: {e}")
        return "I'm having trouble understanding the environment right now. Could you tell me where you are?"


async def process_audio(session_id, base64_data):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [雅思口语模块] Session {session_id}: 🎙️ 正在处理真实语音输入...")
    try:
        # 1. 解码并持久化音频
        audio_bytes = base64.b64decode(base64_data)
        save_dir = "received_audio"
        os.makedirs(save_dir, exist_ok=True)

        # 🎯 核心修复 1：获取绝对路径，并将 Windows 的反斜杠 \ 强行转为正斜杠 /
        # 这是为了严格符合 DashScope SDK对 file:// URI 的规范
        audio_path = os.path.abspath(f"{save_dir}/user_{session_id}_{uuid.uuid4().hex[:6]}.webm").replace('\\', '/')
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        print("[语音模块] 👂 正在调用阿里云 Qwen-Audio (原生多模态) 绕过限制进行识别...")

        # 🎯 核心修复 2：封装原生同步调用，准备丢入线程池（防止阻塞异步高并发网关）
        def call_qwen_audio():
            return MultiModalConversation.call(
                model='qwen-audio-turbo',
                messages=[{
                    'role': 'user',
                    'content': [
                        {'audio': f'file://{audio_path}'},  # SDK 会暗中自动把它传到云端！
                        {
                            'text': 'Please transcribe this English audio. Output strictly the transcribed text without any translation or extra explanations.'}
                    ]
                }]
            )

        # 使用 asyncio.to_thread 完美兼容我们现有的异步框架
        response = await asyncio.to_thread(call_qwen_audio)

        # 容错处理
        if response.status_code != 200:
            raise Exception(f"Qwen-Audio 接口报错: {response.code} - {response.message}")

        # 解析多模态返回的特有嵌套 JSON 结构
        content = response.output.choices[0].message.content
        if isinstance(content, list):
            user_text = "".join([item.get('text', '') for item in content if 'text' in item])
        else:
            user_text = content

        print(f"[语音模块] ✅ 识别出用户回答: \"{user_text}\"")

        # 3. 提取现有状态并推进图状态机
        session_state = await get_or_init_session(session_id)
        session_state["current_user_text"] = user_text
        session_state["current_image_base64"] = None

        print("[认知节点] 🧠 正在结合上下文生成考官追问...")
        final_state = await compiled_agent.ainvoke(session_state)

        # 🌟 替换掉这行：session_memory[session_id] = final_state
        await save_session_to_redis(session_id, final_state)



        # 4. 提取考官纯文本返回给前端（未来给眼镜直接 TTS）
        examiner_reply = final_state["chat_history"][-1]["content"]
        print(f"[语音模块] 📤 准备返回纯文本指令: {examiner_reply}")

        return examiner_reply

    except Exception as e:
        print(f"[雅思口语模块] ❌ 语音处理全流程失败: {e}")
        return "Sorry, I encountered an error recognizing your voice. Could you please say that again?"


async def process_text(session_id, text):
    """🌟 新增：开发者专用的纯文本直达接口 (跳过 ASR)"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [雅思口语模块] Session {session_id}: ⌨️ 收到文本直达测试...")
    try:
        session_state = await get_or_init_session(session_id)
        session_state["current_user_text"] = text
        session_state["current_image_base64"] = None

        final_state = await compiled_agent.ainvoke(session_state)
        await save_session_to_redis(session_id, final_state)
        examiner_reply = final_state["chat_history"][-1]["content"]

        # 🌟 优雅退出：判断如果进入了 Part 4 (结束状态)，直接销毁当前 Session
        if final_state.get("current_part") == 4:
            print(f"[优雅退出] 🗑️ 考试已结束，正在清理 Redis 会话缓存: session:{session_id}")
            if redis_client:
                redis_client.delete(f"session:{session_id}")

        return examiner_reply
    except Exception as e:
        print(f"[雅思口语模块] ❌ 文本处理失败: {e}")
        return "System error."


# 记得同步修改原本的 process_audio，在它返回之前也加上同样的清理逻辑
# (这里为了简洁省略 process_audio 的其余代码，只展示插入点)
# ...
#         await save_session_to_redis(session_id, final_state)
#         examiner_reply = final_state["chat_history"][-1]["content"]
#         if final_state.get("current_part") == 4:
#             print(f"[优雅退出] 🗑️ 考试已结束，正在清理 Redis 会话缓存: session:{session_id}")
#             if redis_client:
#                 redis_client.delete(f"session:{session_id}")
#         return examiner_reply
# ...

# ⭐ 修改主路由接口
async def handle_request(event_type, session_id, payload):
    if event_type == "upload_image":
        base64_img = payload.get("data")
        result = await process_image(session_id, base64_img)
        return {"status": "success", "data": result}
    elif event_type == "upload_audio":
        base64_audio = payload.get("data")
        result = await process_audio(session_id, base64_audio)
        return {"status": "success", "data": result}

    # 🌟 新增文本处理路由
    elif event_type == "text_chat":
        text = payload.get("text")
        result = await process_text(session_id, text)
        return {"status": "success", "data": result}

    # 🌟 新增一键清空会话路由
    elif event_type == "clear_session":
        if redis_client:
            redis_client.delete(f"session:{session_id}")
            print(f"[调试控制] 💣 开发者已强行重置会话: {session_id}")
        return {"status": "success", "data": "Session has been manually cleared. Ready for a new test."}
    else:
        return {"status": "error", "message": f"雅思模块不支持该动作: {event_type}"}





