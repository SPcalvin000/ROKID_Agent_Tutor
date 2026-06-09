# agents/ielts_assistant_agent/report_agent.py
"""
雅思口语多智能体系统 - Report Agent

职责：
1. 汇总所有 TurnRecord 与 ScoreReport。
2. 生成前端专用 JSON 报告。
3. 后续可扩展为 HTML 报告、PDF 报告、PostgreSQL 归档记录。
"""

# agents/ielts_assistant_agent/report_agent.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .state import AgentState, now_iso


# =========================================================
# 1. 工具函数
# =========================================================

def avg_score(reports: List[Dict[str, Any]], key: str) -> Optional[float]:
    values = [
        float(r[key])
        for r in reports
        if isinstance(r.get(key), (int, float))
    ]

    if not values:
        return None

    return round(sum(values) / len(values), 1)


def find_report_for_turn(
    reports: List[Dict[str, Any]],
    turn_id: str,
) -> Optional[Dict[str, Any]]:
    for report in reports:
        if report.get("turn_id") == turn_id:
            return report
    return None


# =========================================================
# 2. Phase 2 调试快照
# =========================================================

def build_scoring_snapshot(state: AgentState) -> Dict[str, Any]:
    """
    Phase 2 用于调试的评分快照。

    它不是最终漂亮报告页面，只是让开发者确认：
    - Scoring Agent 有没有跑
    - score_reports 有没有写入 Redis state
    - 每一轮分数与证据是否存在
    """
    return {
        "session_id": state.get("session_id"),
        "exam_status": state.get("exam_status"),
        "current_part": state.get("current_part"),
        "depth_level": state.get("depth_level"),
        "turn_count": state.get("turn_count"),
        "total_turns": len(state.get("turns", []) or []),
        "total_score_reports": len(state.get("score_reports", []) or []),
        "shadow_summary": state.get("shadow_summary", ""),
        "turns": state.get("turns", []) or [],
        "score_reports": state.get("score_reports", []) or [],
        "generated_at": now_iso(),
    }


# =========================================================
# 3. 临时最终报告 JSON
# =========================================================

def build_final_report(state: AgentState) -> Dict[str, Any]:
    """
    临时最终报告。

    Phase 3 会把这个结果美化成独立 Web 页面。
    Phase 4 会把它归档到 SQL。
    """
    reports = list(state.get("score_reports", []) or [])
    turns = list(state.get("turns", []) or [])

    fc = avg_score(reports, "fluency_coherence")
    lr = avg_score(reports, "lexical_resource")
    gra = avg_score(reports, "grammatical_range_accuracy")

    # 当前 Phase 2 不可靠评分 pronunciation，所以不纳入总分。
    overall_values = [
        x for x in [fc, lr, gra]
        if isinstance(x, (int, float))
    ]
    overall = round(sum(overall_values) / len(overall_values), 1) if overall_values else None

    turn_items = []
    for turn in turns:
        report = find_report_for_turn(reports, turn.get("turn_id", ""))
        turn_items.append({
            "turn_id": turn.get("turn_id"),
            "turn_index": turn.get("turn_index"),
            "part": turn.get("part"),
            "depth_level": turn.get("depth_level"),
            "examiner_question": turn.get("examiner_question"),
            "user_answer_text": turn.get("user_answer_text"),
            "score_report": report,
        })

    return {
        "report_type": "ielts_speaking_phase2_json_report",
        "session_id": state.get("session_id"),
        "exam_status": state.get("exam_status"),
        "generated_at": now_iso(),
        "overall_band_estimate": overall,
        "criteria_summary": {
            "fluency_coherence": fc,
            "lexical_resource": lr,
            "grammatical_range_accuracy": gra,
            "pronunciation": None,
            "pronunciation_note": (
                "Pronunciation is not reliably scored in Phase 2 because the scoring agent "
                "only receives ASR transcript text, not acoustic pronunciation features."
            ),
        },
        "shadow_summary": state.get("shadow_summary", ""),
        "turns": turn_items,
        "raw_score_reports": reports,
    }