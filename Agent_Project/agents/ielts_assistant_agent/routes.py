# agents/ielts_assistant_agent/routes.py
"""
雅思口语多智能体系统 - 外部事件路由层

职责：
1. 对接 Agent_Main.py 的 handle_request(event_type, session_id, payload)。
2. 处理 upload_image / upload_audio / text_chat / clear_session。
3. 额外提供 get_final_report，供 Web 报告页拉取完整 JSON 报告。

保持兼容：
Agent_Main.py 仍然可以写：
    from agents import Speaking_agent
    await Speaking_agent.handle_request(...)
"""

# agents/ielts_assistant_agent/routes.py
from __future__ import annotations

import asyncio
import base64
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from dashscope import MultiModalConversation

from .graph import compiled_agent, perceive_image_base64
from .persistence import clear_session, get_or_init_session, load_session, save_session
from .report_agent import build_final_report, build_scoring_snapshot
from .state import AgentState, ensure_state_defaults


# =========================================================
# 1. 通用工具函数
# =========================================================

def _safe_extract_last_assistant(state: Dict[str, Any]) -> str:
    """从 chat_history 中提取最后一条 assistant 消息，作为返回给眼镜端的实时内容。"""
    for msg in reversed(state.get("chat_history", []) or []):
        if msg.get("role") == "assistant":
            return msg.get("content", "")

    return "I'm ready. Please begin."


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _decode_base64_to_file(base64_data: str, file_path: str) -> None:
    """把前端传来的纯 base64 保存到本地文件。"""
    raw = base64.b64decode(base64_data)
    with open(file_path, "wb") as f:
        f.write(raw)


# =========================================================
# 2. 图片入口：upload_image
# =========================================================

async def process_image(session_id: str, base64_data: Optional[str]) -> str:
    """
    处理图片输入。

    流程：
    1. 保存图片
    2. 先跑 VLM 获取 scene
    3. 用 scene 初始化 Session，触发 Milvus 弱点画像检索
    4. 进入 LangGraph：Examiner Agent 生成 Part 2 Cue Card
    5. Scoring Agent 发现没有用户回答，所以不会评分
    """
    if not base64_data:
        return "I didn't receive an image. Please upload an image again."

    try:
        save_dir = os.path.join("received_images", "ielts")
        _ensure_dir(save_dir)

        filename = f"img_{session_id}_{datetime.now().strftime('%H%M%S')}.webp"
        image_path = os.path.abspath(os.path.join(save_dir, filename)).replace("\\", "/")
        _decode_base64_to_file(base64_data, image_path)

        # 先 VLM 获取 scene，用于初始化 RAG Session。
        vlm_result = await perceive_image_base64(base64_data)
        visual_context = vlm_result.get("visual_context", {}) or {}
        current_scene = visual_context.get("scene", "unknown place")

        session_state = await get_or_init_session(
            session_id=session_id,
            current_scene=current_scene,
        )

        session_state["visual_context"] = visual_context
        session_state["last_image_path"] = image_path
        session_state["current_image_base64"] = None
        session_state["current_user_text"] = None

        final_state = await compiled_agent.ainvoke(session_state)
        final_state = ensure_state_defaults(final_state, session_id=session_id)

        await save_session(session_id, final_state)

        return _safe_extract_last_assistant(final_state)

    except Exception as e:
        print(f"[IELTS Routes] ❌ 图片处理失败: {e}")
        return "I'm having trouble understanding the environment right now. Could you tell me where you are?"


# =========================================================
# 3. 音频入口：upload_audio
# =========================================================

async def transcribe_audio_with_qwen(audio_path: str) -> str:
    """
    使用 Qwen-Audio-Turbo 转写音频。

    DashScope MultiModalConversation 是同步调用，
    所以外层 process_audio 会用 asyncio.to_thread 包起来。
    """
    response = MultiModalConversation.call(
        model="qwen-audio-turbo",
        messages=[
            {
                "role": "user",
                "content": [
                    {"audio": f"file://{audio_path}"},
                    {
                        "text": (
                            "Please transcribe this English audio. "
                            "Output strictly the transcribed text without translation or explanation."
                        )
                    },
                ],
            }
        ],
    )

    if getattr(response, "status_code", None) != 200:
        code = getattr(response, "code", "unknown_code")
        message = getattr(response, "message", "unknown_message")
        raise RuntimeError(f"Qwen-Audio 接口报错: {code} - {message}")

    content = response.output.choices[0].message.content

    if isinstance(content, list):
        return "".join(item.get("text", "") for item in content if isinstance(item, dict)).strip()

    return str(content).strip()


async def process_audio(session_id: str, base64_data: Optional[str]) -> str:
    """
    处理语音输入。

    流程：
    1. 保存 WebM 音频
    2. Qwen-Audio 转写成英文文本
    3. 把文本送入 LangGraph
    4. Examiner Agent 生成下一题
    5. Scoring Agent 静默评分当前用户回答
    6. Redis 保存完整 state
    7. 返回给眼镜端的仍然只有下一题
    """
    if not base64_data:
        return "I didn't receive your audio. Could you please say that again?"

    print(f"[IELTS Routes] 🎙️ Session {session_id}: 正在处理语音输入...")

    try:
        save_dir = "received_audio"
        _ensure_dir(save_dir)

        audio_path = os.path.abspath(
            os.path.join(save_dir, f"user_{session_id}_{uuid.uuid4().hex[:6]}.webm")
        ).replace("\\", "/")

        _decode_base64_to_file(base64_data, audio_path)

        print("[Audio] 👂 正在调用 Qwen-Audio 转写...")
        user_text = await asyncio.to_thread(transcribe_audio_with_qwen, audio_path)
        print(f"[Audio] ✅ 转写结果: {user_text}")

        session_state = await get_or_init_session(session_id=session_id)
        session_state["current_user_text"] = user_text
        session_state["current_image_base64"] = None
        session_state["current_audio_base64"] = None
        session_state["last_audio_path"] = audio_path

        final_state = await compiled_agent.ainvoke(session_state)
        final_state = ensure_state_defaults(final_state, session_id=session_id)

        await save_session(session_id, final_state)

        # 注意：这里不会返回分数，只返回 Examiner 下一题。
        return _safe_extract_last_assistant(final_state)

    except Exception as e:
        print(f"[IELTS Routes] ❌ 语音处理失败: {e}")
        return "Sorry, I encountered an error recognizing your voice. Could you please say that again?"


# =========================================================
# 4. 文本入口：text_chat
# =========================================================

async def process_text(session_id: str, text: Optional[str]) -> str:
    """
    开发者文本直达入口。

    用途：
    - 跳过 ASR
    - 快速测试 Examiner Agent 和 Scoring Agent
    - 推荐你在 Phase 2 主要用这个接口回归测试
    """
    if not text:
        return "Please provide some text."

    print(f"[IELTS Routes] ⌨️ Session {session_id}: 文本测试输入: {text}")

    try:
        session_state = await get_or_init_session(session_id=session_id)
        session_state["current_user_text"] = text
        session_state["current_image_base64"] = None
        session_state["current_audio_base64"] = None
        session_state["last_audio_path"] = None

        final_state = await compiled_agent.ainvoke(session_state)
        final_state = ensure_state_defaults(final_state, session_id=session_id)

        await save_session(session_id, final_state)

        # 注意：Scoring Agent 的结果已经在 final_state["score_reports"] 中保存。
        # 但这里仍然只返回 Examiner 下一题，符合眼镜端轻量交互设计。
        return _safe_extract_last_assistant(final_state)

    except Exception as e:
        print(f"[IELTS Routes] ❌ 文本处理失败: {e}")
        return "System error."


# =========================================================
# 5. 调试 / 报告入口
# =========================================================

async def get_scoring_snapshot(session_id: str) -> Dict[str, Any]:
    """
    Phase 2 调试接口。

    前端可以发送：
    {
      "agent_type": "ielts_speaking",
      "event_type": "get_scoring_snapshot",
      "session_id": "test_user_001",
      "payload": {}
    }

    返回当前 Redis state 中的 turns 和 score_reports。
    """
    state = await load_session(session_id)
    if not state:
        return {
            "status": "error",
            "message": "Session not found.",
        }

    return {
        "status": "success",
        "data": build_scoring_snapshot(state),
    }


async def get_final_report(session_id: str) -> Dict[str, Any]:
    """
    临时 JSON 报告接口。

    Phase 3 会把这个 JSON 变成独立 Web 页面。
    Phase 4 会把它写入 SQL 历史归档。
    """
    state = await load_session(session_id)
    if not state:
        return {
            "status": "error",
            "message": "Session not found.",
        }

    return {
        "status": "success",
        "data": build_final_report(state),
    }


# =========================================================
# 6. 主路由：给 Agent_Main.py 调用
# =========================================================

async def handle_request(
    event_type: str,
    session_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    保持旧接口不变：
    Agent_Main.py 仍然调用 Speaking_agent.handle_request(...)
    """
    if event_type == "upload_image":
        result = await process_image(session_id, payload.get("data"))
        return {
            "status": "success",
            "data": result,
            "note": "Live response only. Scoring is stored silently in session state.",
        }

    if event_type == "upload_audio":
        result = await process_audio(session_id, payload.get("data"))
        return {
            "status": "success",
            "data": result,
            "note": "Live response only. Scoring is stored silently in session state.",
        }

    if event_type == "text_chat":
        result = await process_text(session_id, payload.get("text"))
        return {
            "status": "success",
            "data": result,
            "note": "Live response only. Scoring is stored silently in session state.",
        }

    if event_type == "get_scoring_snapshot":
        return await get_scoring_snapshot(session_id)

    if event_type == "get_final_report":
        return await get_final_report(session_id)

    if event_type == "clear_session":
        await clear_session(session_id)
        print(f"[调试控制] 💣 已清空 Session: {session_id}")
        return {
            "status": "success",
            "data": "Session has been manually cleared. Ready for a new test.",
        }

    return {
        "status": "error",
        "message": f"IELTS speaking module does not support event_type: {event_type}",
    }