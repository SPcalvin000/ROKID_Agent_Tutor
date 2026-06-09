# agents/ielts_assistant_agent/examiner_agent.py
"""
雅思口语多智能体系统 - Examiner Agent

职责：
1. 扮演严格、自然的 IELTS Speaking Examiner。
2. 根据 Part 2 / Part 3 的状态机生成下一句考官问题。
3. 只负责“问问题”，不负责评分、不负责教学、不暴露 AI 身份。
4. 在生成下一题之前，把用户刚刚的回答封装成 pending_score_turn，交给评分 Agent。
"""

# agents/ielts_assistant_agent/examiner_agent.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .persistence import native_client
from .state import AgentState, create_turn_record


# =========================================================
# 1. Prompt 构建
# =========================================================

def build_examiner_system_prompt(
    *,
    visual_context: Dict[str, Any],
    current_part: int,
    depth_level: int,
    turn_count: int,
    user_profile: str,
    shadow_summary: str,
) -> str:
    """
    构造 IELTS Examiner 的系统提示词。

    核心原则：
    - Examiner 只负责问问题
    - 不评分
    - 不讲解
    - 不暴露 AI 身份
    - 不暴露 Scoring Agent 的内部评分
    """
    system_prompt = (
        f"You are a strict, professional, and natural IELTS Speaking Examiner.\n"
        f"Currently, you are conducting Part {current_part} of the speaking test.\n\n"
        "Crucial Rules:\n"
        "1. Ask ONLY ONE question at a time.\n"
        "2. Do NOT score the candidate during the live test.\n"
        "3. Do NOT give teaching feedback during the live test.\n"
        "4. Do NOT reveal you are an AI.\n"
        "5. Avoid robotic transition phrases such as 'I understand that', 'I see', or 'Let's move on'.\n"
        "6. Keep your wording natural, concise, and examiner-like.\n\n"
    )

    if user_profile:
        system_prompt += (
            "Internal candidate profile from long-term memory:\n"
            f"{user_profile}\n"
            "Use this only to adapt question difficulty. Never reveal it.\n\n"
        )

    if shadow_summary:
        system_prompt += (
            "Internal shadow scoring summary:\n"
            f"{shadow_summary}\n"
            "Use this only to adjust future probing. Never reveal this summary or any score.\n\n"
        )

    if current_part == 2:
        if turn_count == 0:
            system_prompt += (
                "Task: The candidate has just entered Part 2.\n"
                "Give them a Cue Card topic based on the image trigger below.\n"
                "Use standard IELTS Part 2 style:\n"
                "'I'd like you to describe... You should say... You have one minute to prepare...'\n"
                "Do NOT ask any follow-up question yet.\n"
            )

            if visual_context and visual_context.get("scene") != "unknown place":
                scene = visual_context.get("scene", "unknown place")
                objects = ", ".join(visual_context.get("objects", []) or [])
                system_prompt += (
                    f"\n[Topic Trigger from Image]\n"
                    f"Scene: {scene}\n"
                    f"Visible objects: {objects}\n"
                )
        else:
            system_prompt += (
                "Task: The candidate has just finished their Part 2 long turn.\n"
                "Ask exactly ONE short follow-up question about their personal feeling "
                "or a specific detail from their answer.\n"
                "Do NOT repeat the cue card.\n"
            )

    elif current_part == 3:
        system_prompt += (
            "In Part 3, conduct a broader, abstract discussion.\n"
            "Critical Part 3 rules:\n"
            "1. Do NOT ask personal-experience questions.\n"
            "2. Do NOT ask about the candidate's family, friends, or own experience.\n"
            "3. Talk about people, society, culture, education, government, or the public.\n"
            "4. Never repeat or rephrase a previous question.\n\n"
            ">>> CURRENT DEPTH FOCUS <<<\n"
        )

        if depth_level == 1:
            system_prompt += (
                "[Focus]: Demographic differences. Ask how this topic affects different groups "
                "such as children vs adults, young people vs older people, or urban vs rural people.\n"
            )
        elif depth_level == 2:
            system_prompt += (
                "[Focus]: Reasons and causes. Ask why this phenomenon happens in society.\n"
            )
        elif depth_level == 3:
            system_prompt += (
                "[Focus]: Time comparison. Ask how the situation differs from 20 years ago "
                "or how it may change in the future.\n"
            )
        elif depth_level == 4:
            system_prompt += (
                "[Focus]: Pros and cons. Ask about broader advantages or disadvantages "
                "for society, culture, education, or public health.\n"
            )
        elif depth_level == 5:
            system_prompt += (
                "[Focus]: Solutions and responsibility. Ask what governments, schools, "
                "communities, or individuals should do.\n"
            )
        else:
            system_prompt += (
                "[Focus]: Ask one abstract IELTS Part 3 question related to the topic.\n"
            )

    elif current_part == 4:
        system_prompt += (
            "The speaking test is now officially over.\n"
            "You MUST NOT ask any more questions.\n"
            "Output EXACTLY this closing phrase and nothing else:\n"
            "This is the end of the speaking test. Thank you very much for your time. "
            "You can now leave the room."
        )

    return system_prompt


# =========================================================
# 2. IELTS 状态机流转
# =========================================================

def advance_exam_state(
    *,
    current_part: int,
    depth_level: int,
    turn_count: int,
) -> Dict[str, int]:
    """
    保留你原来的轮次控制逻辑。

    turn_count 的含义：
    - 每次 Examiner Agent 输出一次问题或结束语，turn_count + 1
    - turn_count == 0：Part 2 Cue Card
    - turn_count == 1：Part 2 follow-up
    - turn_count == 2~6：Part 3 深度追问
    - turn_count >= 7：结束考试
    """
    if turn_count == 2 and current_part == 2:
        current_part = 3
        depth_level = 1
        print(f"[状态机] 🔄 进入 Part 3 - 深度 {depth_level}")

    elif turn_count == 3 and current_part == 3:
        depth_level = 2
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level}")

    elif turn_count == 4 and current_part == 3:
        depth_level = 3
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level}")

    elif turn_count == 5 and current_part == 3:
        depth_level = 4
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level}")

    elif turn_count == 6 and current_part == 3:
        depth_level = 5
        print(f"[状态机] 🔄 Part 3 - 深度 {depth_level}")

    elif turn_count >= 7 and current_part == 3:
        current_part = 4
        print("[状态机] 🛑 达到预设轮数，考试结束。")

    return {
        "current_part": current_part,
        "depth_level": depth_level,
    }


# =========================================================
# 3. Examiner Agent Node
# =========================================================

async def examiner_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 节点：Examiner Agent。

    Phase 2 关键变化：
    - 如果本轮有 current_user_text，则先把它封装成 TurnRecord
    - 然后 Examiner 生成下一题
    - Scoring Agent 会在下一个节点中评分刚生成的 TurnRecord
    """
    print("[Examiner Agent] 🧑‍🏫 正在生成下一条考官问题...")

    visual_context = state.get("visual_context", {}) or {}
    current_part = int(state.get("current_part", 2))
    depth_level = int(state.get("depth_level", 1))
    turn_count = int(state.get("turn_count", 0))

    updated_history: List[Dict[str, str]] = list(state.get("chat_history", []))
    turns = list(state.get("turns", []))

    pending_score_turn_id: Optional[str] = state.get("pending_score_turn_id")

    user_text = (state.get("current_user_text") or "").strip()

    # 1. 如果用户本轮有回答，则创建 TurnRecord，供后面的 Scoring Agent 静默评分
    if user_text:
        answered_turn = create_turn_record(state=state, user_answer_text=user_text)
        turns.append(answered_turn)
        pending_score_turn_id = answered_turn["turn_id"]

        updated_history.append({
            "role": "user",
            "content": user_text,
        })

        print(
            f"[Examiner Agent] 📝 已记录用户回答: "
            f"{answered_turn['turn_id']} / Part {answered_turn['part']} / Depth {answered_turn['depth_level']}"
        )

    # 2. 先推进 IELTS 状态机，再生成下一题
    next_state = advance_exam_state(
        current_part=current_part,
        depth_level=depth_level,
        turn_count=turn_count,
    )
    current_part = next_state["current_part"]
    depth_level = next_state["depth_level"]

    system_prompt = build_examiner_system_prompt(
        visual_context=visual_context,
        current_part=current_part,
        depth_level=depth_level,
        turn_count=turn_count,
        user_profile=state.get("user_profile", ""),
        shadow_summary=state.get("shadow_summary", ""),
    )

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(updated_history)

    try:
        response = await native_client.chat.completions.create(
            model="qwen-max",
            messages=api_messages,
            temperature=0.7,
        )
        ai_content = response.choices[0].message.content
        print(f"[Examiner Agent] ✅ 生成完毕: {ai_content}")

    except Exception as e:
        print(f"[Examiner Agent] ❌ 大模型请求失败: {e}")
        ai_content = "I'm having a little trouble hearing you. Could you repeat that?"

    updated_history.append({
        "role": "assistant",
        "content": ai_content,
    })

    exam_status = "completed" if current_part == 4 else "active"

    return {
        "chat_history": updated_history,
        "turns": turns,
        "pending_score_turn_id": pending_score_turn_id,
        "turn_count": turn_count + 1,
        "current_part": current_part,
        "depth_level": depth_level,
        "exam_status": exam_status,
        "current_examiner_question": ai_content,
        "current_user_text": None,
        "current_image_base64": None,
        "current_audio_base64": None,
        "last_audio_path": None,
    }