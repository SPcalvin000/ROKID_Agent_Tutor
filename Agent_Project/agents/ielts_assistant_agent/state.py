# agents/ielts_assistant_agent/state.py
"""
雅思口语多智能体系统 - 状态定义层

职责：
1. 定义 LangGraph 在各个节点之间传递的 AgentState。
2. 定义 TurnRecord / ScoreReport 等结构化数据。
3. 提供初始化与兼容旧 Redis Session 的工具函数。

注意：这里不要写任何 LLM 调用、Redis 调用、Milvus 调用。
状态层只负责“数据结构”，保持干净，方便其他开发者理解和维护。
"""

# agents/ielts_assistant_agent/state.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict
import uuid


# =========================================================
# 1. 基础工具函数
# =========================================================

def now_iso() -> str:
    """返回 UTC ISO 时间字符串，便于之后写入 SQL / 日志 / 报告。"""
    return datetime.now(timezone.utc).isoformat()


def make_turn_id() -> str:
    """生成一个短 Turn ID，方便日志追踪。"""
    return f"turn_{uuid.uuid4().hex[:10]}"


# =========================================================
# 2. 单轮回答记录：TurnRecord
# =========================================================

class TurnRecord(TypedDict, total=False):
    """
    一次“用户回答”的结构化记录。

    注意：
    - Examiner 的提问和用户回答被绑定成一个 TurnRecord
    - Scoring Agent 后续会基于这个 TurnRecord 生成 ScoreReport
    """
    turn_id: str
    turn_index: int

    # 用户回答的是哪个 IELTS 阶段的问题
    part: int
    depth_level: int

    # 问答内容
    examiner_question: str
    user_answer_text: str

    # 输入模态信息
    audio_path: Optional[str]
    image_path: Optional[str]
    visual_context: Dict[str, Any]

    # 时间戳
    created_at: str


# =========================================================
# 3. 单轮评分报告：ScoreReport
# =========================================================

class ScoreReport(TypedDict, total=False):
    """
    Scoring Agent 对某一个 TurnRecord 的静默评分结果。

    当前 Phase 2：
    - 存储在 Redis 的 AgentState.score_reports 中
    - 不返回给眼镜端
    - 可通过 get_scoring_snapshot / get_final_report 调试查看

    Phase 3/4：
    - 可写入 PostgreSQL
    - 可展示在专门的 Web Report 页面
    """
    turn_id: str
    turn_index: int
    part: int
    depth_level: int

    fluency_coherence: Optional[float]
    lexical_resource: Optional[float]
    grammatical_range_accuracy: Optional[float]
    pronunciation: Optional[float]

    pronunciation_confidence: str
    overall_estimate: Optional[float]

    evidence: Dict[str, List[str]]
    correction_suggestions: List[str]
    weakness_tags: List[str]

    raw_model_output: Optional[str]
    scoring_error: Optional[str]
    created_at: str


# =========================================================
# 4. LangGraph 全局状态：AgentState
# =========================================================

class AgentState(TypedDict, total=False):
    """
    LangGraph 中所有节点共享的状态。

    这是本项目的“状态总线”：
    - Examiner Agent 读取它，写入新的考官问题
    - Scoring Agent 读取最新 TurnRecord，写入 ScoreReport
    - Report Agent 读取 score_reports，生成最终报告
    - Persistence 层把它保存到 Redis
    """
    session_id: str

    # OpenAI-style messages: [{"role": "user", "content": "..."}]
    chat_history: List[Dict[str, str]]

    # 结构化视觉上下文
    visual_context: Dict[str, Any]

    # IELTS 状态机
    current_part: int
    depth_level: int
    turn_count: int
    exam_status: str  # active / completed

    # 长期弱点画像，来自 Milvus
    user_profile: str

    # 当前输入缓存
    current_image_base64: Optional[str]
    current_audio_base64: Optional[str]
    current_user_text: Optional[str]

    # 文件路径缓存
    last_audio_path: Optional[str]
    last_image_path: Optional[str]

    # 当前考官问题，用于把用户下一次回答绑定成 TurnRecord
    current_examiner_question: Optional[str]

    # Phase 2 新增：问答记录与评分记录
    turns: List[TurnRecord]
    score_reports: List[ScoreReport]

    # Scoring Agent 使用：记录“刚刚生成、等待评分”的 turn_id
    pending_score_turn_id: Optional[str]

    # Scoring Agent 压缩出来的弱点摘要，Examiner 可以轻量读取但不能泄露
    shadow_summary: str


# =========================================================
# 5. 状态初始化与迁移
# =========================================================

def build_initial_state(
    session_id: str,
    current_scene: str = "unknown place",
    user_profile: str = "",
) -> AgentState:
    """
    创建一个全新的 IELTS 会话状态。

    注意：
    - 默认从 Part 2 开始，延续你原来的设计
    - Phase 2 新增 turns / score_reports / shadow_summary
    """
    return AgentState(
        session_id=session_id,
        chat_history=[],
        visual_context={"scene": current_scene, "objects": [], "mood": "unknown"},
        current_part=2,
        depth_level=1,
        turn_count=0,
        exam_status="active",
        user_profile=user_profile or "",
        current_image_base64=None,
        current_audio_base64=None,
        current_user_text=None,
        last_audio_path=None,
        last_image_path=None,
        current_examiner_question=None,
        turns=[],
        score_reports=[],
        pending_score_turn_id=None,
        shadow_summary="",
    )


def find_last_assistant_message(chat_history: List[Dict[str, str]]) -> Optional[str]:
    """从历史记录中找最后一条 assistant 消息，用作 current_examiner_question 的兜底。"""
    for msg in reversed(chat_history or []):
        if msg.get("role") == "assistant":
            return msg.get("content")
    return None


def ensure_state_defaults(
    raw_state: Dict[str, Any],
    session_id: str = "anonymous",
    current_scene: str = "unknown place",
) -> AgentState:
    """
    Redis 中可能已经有旧版状态。
    这个函数负责“状态迁移”：给旧状态补齐 Phase 2 新字段。

    这样你不用手动清空所有 Redis 旧 Session。
    """
    state: Dict[str, Any] = dict(raw_state or {})

    state.setdefault("session_id", session_id)
    state.setdefault("chat_history", [])
    state.setdefault("visual_context", {"scene": current_scene, "objects": [], "mood": "unknown"})

    state.setdefault("current_part", 2)
    state.setdefault("depth_level", 1)
    state.setdefault("turn_count", 0)
    state.setdefault("exam_status", "active")
    state.setdefault("user_profile", "")

    state.setdefault("current_image_base64", None)
    state.setdefault("current_audio_base64", None)
    state.setdefault("current_user_text", None)

    state.setdefault("last_audio_path", None)
    state.setdefault("last_image_path", None)

    state.setdefault("turns", [])
    state.setdefault("score_reports", [])
    state.setdefault("pending_score_turn_id", None)
    state.setdefault("shadow_summary", "")

    if not state.get("current_examiner_question"):
        state["current_examiner_question"] = find_last_assistant_message(state.get("chat_history", []))

    # 类型兜底，避免 Redis 旧数据或错误数据导致状态机崩溃
    try:
        state["current_part"] = int(state.get("current_part", 2))
    except Exception:
        state["current_part"] = 2

    try:
        state["depth_level"] = int(state.get("depth_level", 1))
    except Exception:
        state["depth_level"] = 1

    try:
        state["turn_count"] = int(state.get("turn_count", 0))
    except Exception:
        state["turn_count"] = 0

    return AgentState(**state)


def create_turn_record(
    *,
    state: AgentState,
    user_answer_text: str,
) -> TurnRecord:
    """
    把“上一条考官问题 + 当前用户回答”封装成 TurnRecord。

    关键点：
    - 用户回答的是“上一条考官问题”
    - 所以 part/depth_level 使用当前状态中的旧值
    - Examiner Agent 随后才会推进状态机并生成下一题
    """
    turns = state.get("turns", [])
    visual_context = state.get("visual_context", {}) or {}

    examiner_question = (
        state.get("current_examiner_question")
        or find_last_assistant_message(state.get("chat_history", []))
        or "(No previous examiner question recorded.)"
    )

    return TurnRecord(
        turn_id=make_turn_id(),
        turn_index=len(turns) + 1,
        part=int(state.get("current_part", 2)),
        depth_level=int(state.get("depth_level", 1)),
        examiner_question=examiner_question,
        user_answer_text=user_answer_text,
        audio_path=state.get("last_audio_path"),
        image_path=state.get("last_image_path"),
        visual_context=visual_context,
        created_at=now_iso(),
    )