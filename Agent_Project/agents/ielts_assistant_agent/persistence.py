# agents/ielts_assistant_agent/persistence.py
"""
雅思口语多智能体系统 - 基础设施与状态持久化层

职责：
1. 统一初始化 DashScope/OpenAI-compatible client。
2. 统一初始化 Redis 短期状态缓存。
3. 统一初始化 Milvus 长期记忆库客户端。
4. 提供 save/load/delete Session 的唯一入口。

重要修复：
- 原 Speaking_agent.py 中 session_memory 被重复定义多次；
- save_session_to_redis 也被重复定义，后一个函数覆盖前一个函数，导致 fallback 行为丢失；
- 本文件把这些逻辑收敛为唯一实现，避免“影子覆盖”问题。
"""

# agents/ielts_assistant_agent/persistence.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import dashscope
import redis
from dotenv import load_dotenv
from openai import AsyncOpenAI

try:
    from pymilvus import MilvusClient
except Exception:
    MilvusClient = None  # type: ignore

from .state import AgentState, build_initial_state, ensure_state_defaults


# =========================================================
# 1. 环境变量加载
# =========================================================

load_dotenv()

# 防止本地代理 / VPN 拦截阿里云请求。
os.environ["NO_PROXY"] = os.getenv(
    "NO_PROXY",
    "dashscope.aliyuncs.com,aliyuncs.com,127.0.0.1,localhost"
)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise ValueError("⚠️ 找不到 DASHSCOPE_API_KEY，请检查 Agent_Project/.env 文件。")

dashscope.api_key = DASHSCOPE_API_KEY

DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "86400"))

MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "user_weakness_vector_db")


# =========================================================
# 2. OpenAI-compatible DashScope Client
# =========================================================

native_client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)


# =========================================================
# 3. Redis Session Store
# =========================================================

try:
    print(f"[系统初始化] 🔌 正在连接 Redis 状态缓存: {REDIS_HOST}:{REDIS_PORT}")
    redis_client: Optional[redis.Redis] = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_timeout=5.0,
    )
    redis_client.ping()
    print("[系统初始化] 🟢 Redis 状态缓存器已成功挂载！")
except Exception as e:
    print(f"[系统初始化] ⚠️ Redis 连接失败，将降级为本地内存模式: {e}")
    redis_client = None

# Redis 不可用时的本地兜底。注意：只适合开发环境，不适合生产。
session_memory: Dict[str, Dict[str, Any]] = {}


def session_key(session_id: str) -> str:
    return f"session:{session_id}"


async def load_session(session_id: str) -> Optional[AgentState]:
    """从 Redis / 本地内存读取会话状态。"""
    if redis_client:
        try:
            raw = redis_client.get(session_key(session_id))
            if raw:
                state = json.loads(raw)
                return ensure_state_defaults(state, session_id=session_id)
        except Exception as e:
            print(f"[状态机底座] ⚠️ 从 Redis 读取 Session 失败: {e}")

    if session_id in session_memory:
        return ensure_state_defaults(session_memory[session_id], session_id=session_id)

    return None


async def save_session(session_id: str, state: Dict[str, Any]) -> None:
    """
    统一保存会话状态。

    Phase 2 的评分结果 score_reports 就是通过这个函数保存到 Redis 的。
    """
    safe_state = ensure_state_defaults(dict(state), session_id=session_id)

    if redis_client:
        try:
            redis_client.set(
                session_key(session_id),
                json.dumps(safe_state, ensure_ascii=False),
                ex=SESSION_TTL_SECONDS,
            )
            return
        except Exception as e:
            print(f"[状态机底座] ❌ 写入 Redis 失败，降级到本地内存: {e}")

    session_memory[session_id] = dict(safe_state)


async def clear_session(session_id: str) -> None:
    """清空指定 Session。"""
    if redis_client:
        try:
            redis_client.delete(session_key(session_id))
        except Exception as e:
            print(f"[状态机底座] ⚠️ 删除 Redis Session 失败: {e}")

    session_memory.pop(session_id, None)


# =========================================================
# 4. Milvus Long-term Memory
# =========================================================

try:
    if MilvusClient is None:
        raise RuntimeError("pymilvus 未安装，跳过 Milvus 初始化。")

    print(f"[系统初始化] 🔌 正在连接 Milvus 长期记忆库: {MILVUS_URI}")
    rag_client = MilvusClient(uri=MILVUS_URI)
    print("[系统初始化] 🟢 Milvus 长期记忆库就绪！")
except Exception as e:
    print(f"[系统初始化] ⚠️ Milvus 未启动或连接失败，将降级为无长期记忆模式: {e}")
    rag_client = None


async def get_or_init_session(
    session_id: str,
    current_scene: str = "unknown place",
) -> AgentState:
    """
    读取或初始化会话。

    初始化时会尝试根据当前场景从 Milvus 检索用户弱点画像。
    """
    existing = await load_session(session_id)
    if existing:
        print(f"[状态机底座] 💾 成功恢复 Session [{session_id}]")
        return existing

    print(f"[状态机底座] 🆕 初始化新 Session: {session_id}")

    retrieved_profile = ""
    if current_scene and current_scene != "unknown place":
        try:
            from .memory_agent import retrieve_user_profile
            retrieved_profile = await retrieve_user_profile(current_scene)
        except Exception as e:
            print(f"[RAG 检索模块] ⚠️ 初始化检索用户画像失败: {e}")

    new_state = build_initial_state(
        session_id=session_id,
        current_scene=current_scene,
        user_profile=retrieved_profile,
    )
    await save_session(session_id, new_state)
    return new_state