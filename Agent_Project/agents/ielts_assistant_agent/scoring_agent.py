# agents/ielts_assistant_agent/scoring_agent.py
"""
雅思口语多智能体系统 - Shadow Scoring Agent

职责：
1. 静默读取用户回答，不向眼镜端/前端输出评分。
2. 按 IELTS Speaking 四项维度生成结构化 JSON。
3. 把 ScoreReport 写入 AgentState，供最终报告页面使用。

工程原则：
- 评分 Agent 不应影响 Examiner Agent 的实时考官人格；
- 评分失败不能中断考试；
- 只有文本转写时，pronunciation 不做强行高置信评分。
"""

# agents/ielts_assistant_agent/scoring_agent.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .memory_agent import build_shadow_summary
from .persistence import native_client
from .state import AgentState, ScoreReport, now_iso


# =========================================================
# 1. JSON 解析工具
# =========================================================

def extract_json_object(text: str) -> Dict[str, Any]:
    """
    从模型输出中提取 JSON 对象。

    有些模型即使被要求输出 JSON，也可能包一层 ```json。
    这里做容错清洗。
    """
    if not text:
        return {}

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


def safe_float(value: Any) -> Optional[float]:
    """把模型输出安全转换成 0~9 的 IELTS band 分数。"""
    if value is None:
        return None

    try:
        number = float(value)
        return max(0.0, min(9.0, round(number, 1)))
    except Exception:
        return None


def average_score(values: List[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if isinstance(v, (int, float))]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)


# =========================================================
# 2. Prompt 构建
# =========================================================

def build_scoring_prompt() -> str:
    """
    Scoring Agent 的系统提示词。

    重要：
    - Scoring Agent 是 Shadow Agent，不直接面对用户
    - 只输出 JSON
    - 当前阶段只基于 transcript 评分，所以 pronunciation 不能强行打分
    """
    return """
You are a silent IELTS Speaking scoring assistant.

You do NOT speak to the candidate.
You do NOT generate examiner questions.
You ONLY evaluate the user's previous answer and output a valid JSON object.

Evaluate the answer according to IELTS Speaking dimensions:
1. fluency_coherence
2. lexical_resource
3. grammatical_range_accuracy
4. pronunciation

Important pronunciation rule:
- If you only receive a text transcript and no reliable acoustic features, set pronunciation to null.
- Set pronunciation_confidence to "not_scored_from_transcript".

Scoring calibration:
- Use IELTS-style band estimates from 0.0 to 9.0.
- You may use .5 increments.
- Do not be overly generous.
- Do not be overly punitive.
- Base evidence on the actual answer.
- If the answer is too short, reflect that in fluency/coherence and lexical resource.

Return ONLY JSON. No markdown. No explanation outside JSON.

Required JSON keys:
{
  "fluency_coherence": number,
  "lexical_resource": number,
  "grammatical_range_accuracy": number,
  "pronunciation": null,
  "pronunciation_confidence": "not_scored_from_transcript",
  "overall_estimate": number,
  "evidence": {
    "fluency_coherence": ["..."],
    "lexical_resource": ["..."],
    "grammatical_range_accuracy": ["..."],
    "pronunciation": ["..."]
  },
  "correction_suggestions": ["..."],
  "weakness_tags": ["..."]
}
"""


# =========================================================
# 3. 报告规整
# =========================================================

def normalize_score_report(
    *,
    raw: Dict[str, Any],
    raw_model_output: str,
    turn: Dict[str, Any],
) -> ScoreReport:
    """
    把模型 JSON 规整成项目内部的 ScoreReport 结构。
    """
    fc = safe_float(raw.get("fluency_coherence"))
    lr = safe_float(raw.get("lexical_resource"))
    gra = safe_float(raw.get("grammatical_range_accuracy"))

    # Phase 2 不从音频声学特征评分，所以 pronunciation 默认 None。
    pronunciation = safe_float(raw.get("pronunciation"))
    pronunciation_confidence = raw.get("pronunciation_confidence") or "not_scored_from_transcript"

    overall = safe_float(raw.get("overall_estimate"))
    if overall is None:
        # 不把 pronunciation 纳入均分，因为当前没有可靠声学特征。
        overall = average_score([fc, lr, gra])

    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    for key in [
        "fluency_coherence",
        "lexical_resource",
        "grammatical_range_accuracy",
        "pronunciation",
    ]:
        value = evidence.get(key)
        if not isinstance(value, list):
            evidence[key] = []

    correction_suggestions = raw.get("correction_suggestions")
    if not isinstance(correction_suggestions, list):
        correction_suggestions = []

    weakness_tags = raw.get("weakness_tags")
    if not isinstance(weakness_tags, list):
        weakness_tags = []

    return ScoreReport(
        turn_id=turn.get("turn_id", ""),
        turn_index=int(turn.get("turn_index", 0)),
        part=int(turn.get("part", 0)),
        depth_level=int(turn.get("depth_level", 0)),
        fluency_coherence=fc,
        lexical_resource=lr,
        grammatical_range_accuracy=gra,
        pronunciation=pronunciation,
        pronunciation_confidence=pronunciation_confidence,
        overall_estimate=overall,
        evidence=evidence,
        correction_suggestions=[str(x) for x in correction_suggestions],
        weakness_tags=[str(x) for x in weakness_tags],
        raw_model_output=raw_model_output,
        scoring_error=None,
        created_at=now_iso(),
    )


def fallback_score_report(
    *,
    turn: Dict[str, Any],
    error: str,
    raw_model_output: Optional[str] = None,
) -> ScoreReport:
    """
    当 Scoring Agent 失败时，也要写入一个错误报告，便于排查。
    """
    return ScoreReport(
        turn_id=turn.get("turn_id", ""),
        turn_index=int(turn.get("turn_index", 0)),
        part=int(turn.get("part", 0)),
        depth_level=int(turn.get("depth_level", 0)),
        fluency_coherence=None,
        lexical_resource=None,
        grammatical_range_accuracy=None,
        pronunciation=None,
        pronunciation_confidence="not_scored",
        overall_estimate=None,
        evidence={
            "fluency_coherence": [],
            "lexical_resource": [],
            "grammatical_range_accuracy": [],
            "pronunciation": [],
        },
        correction_suggestions=[],
        weakness_tags=["scoring_failed"],
        raw_model_output=raw_model_output,
        scoring_error=error,
        created_at=now_iso(),
    )


def find_pending_turn(state: AgentState) -> Optional[Dict[str, Any]]:
    """根据 pending_score_turn_id 找到刚刚需要评分的 TurnRecord。"""
    pending_id = state.get("pending_score_turn_id")
    if not pending_id:
        return None

    for turn in state.get("turns", []) or []:
        if turn.get("turn_id") == pending_id:
            return dict(turn)

    return None


def already_scored(state: AgentState, turn_id: str) -> bool:
    """避免重复评分同一个 turn。"""
    for report in state.get("score_reports", []) or []:
        if report.get("turn_id") == turn_id:
            return True
    return False


# =========================================================
# 4. Scoring Agent Node
# =========================================================

async def scoring_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 节点：Shadow Scoring Agent。

    关键设计：
    - 它在 Examiner 生成下一题之后执行
    - 它只把评分写入 state.score_reports
    - 它的输出不会直接返回给眼镜端
    """
    enable_scoring = os.getenv("ENABLE_SHADOW_SCORING", "true").lower() in {
        "1",
        "true",
        "yes",
        "y",
    }

    if not enable_scoring:
        print("[Scoring Agent] ⏭️ ENABLE_SHADOW_SCORING=false，跳过静默评分。")
        return {"pending_score_turn_id": None}

    turn = find_pending_turn(state)
    if not turn:
        return {}

    turn_id = turn.get("turn_id", "")
    if not turn_id:
        return {"pending_score_turn_id": None}

    if already_scored(state, turn_id):
        print(f"[Scoring Agent] ℹ️ Turn 已评分，跳过: {turn_id}")
        return {"pending_score_turn_id": None}

    answer = (turn.get("user_answer_text") or "").strip()
    if not answer:
        print("[Scoring Agent] ℹ️ 用户回答为空，跳过评分。")
        return {"pending_score_turn_id": None}

    print(f"[Scoring Agent] 🧪 正在静默评分: {turn_id}")

    system_prompt = build_scoring_prompt()

    user_payload = {
        "turn_id": turn_id,
        "part": turn.get("part"),
        "depth_level": turn.get("depth_level"),
        "examiner_question": turn.get("examiner_question"),
        "user_answer_text": answer,
        "note": (
            "Score based on transcript only. "
            "Do not assign a confident pronunciation score."
        ),
    }

    raw_output = ""

    try:
        response = await native_client.chat.completions.create(
            model="qwen-max",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            temperature=0.1,
        )

        raw_output = response.choices[0].message.content or ""
        parsed = extract_json_object(raw_output)

        report = normalize_score_report(
            raw=parsed,
            raw_model_output=raw_output,
            turn=turn,
        )

        print(
            f"[Scoring Agent] ✅ 评分完成: {turn_id}, "
            f"overall={report.get('overall_estimate')}"
        )

    except Exception as e:
        print(f"[Scoring Agent] ❌ 评分失败: {e}")
        report = fallback_score_report(
            turn=turn,
            error=str(e),
            raw_model_output=raw_output,
        )

    updated_reports = list(state.get("score_reports", []))
    updated_reports.append(report)

    shadow_summary = build_shadow_summary(updated_reports)

    return {
        "score_reports": updated_reports,
        "pending_score_turn_id": None,
        "shadow_summary": shadow_summary,
    }