# agents/ielts_assistant_agent/graph.py
"""
雅思口语多智能体系统 - LangGraph 编排层

职责：
1. 视觉感知节点：从图片中提取 scene / objects / mood。
2. Examiner Agent 节点：生成下一句考官问题。
3. Shadow Scoring Agent 节点：静默评分用户回答。

当前阶段仍保持你的原始主流程：
- 图像触发 VLM；
- 文本/音频触发 Examiner；
- 评分 Agent 静默运行，不改变前端返回格式。
"""

# agents/ielts_assistant_agent/graph.py
from __future__ import annotations

import json
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from .examiner_agent import examiner_agent_node
from .persistence import native_client
from .scoring_agent import scoring_agent_node
from .state import AgentState


# =========================================================
# 1. VLM 感知节点
# =========================================================

def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """从 VLM 输出中提取 JSON。"""
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


async def vlm_perception_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 节点：视觉感知层。

    职责：
    - 只做客观图像结构化提取
    - 不生成考试问题
    - 不评分
    """
    base64_image = state.get("current_image_base64")
    if not base64_image:
        print("[VLM Agent] ℹ️ 当前轮没有图片，跳过视觉感知。")
        return {}

    print("[VLM Agent] 👀 正在调用 Qwen-VL-Plus 解析图片环境...")

    try:
        response = await native_client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/webp;base64,{base64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "你是一个图像实体提取器。请分析这张第一人称视角的图片，"
                                "提取出场景的客观信息。\n"
                                "请严格以 JSON 格式输出，必须包含以下三个字段：\n"
                                "1. scene：主场景，如 cafe, bedroom\n"
                                "2. objects：显著物体列表，使用英文，不超过5个\n"
                                "3. mood：场景氛围描述\n"
                                "不要输出任何多余解释，只输出合法 JSON。"
                            ),
                        },
                    ],
                }
            ],
            temperature=0.1,
        )

        vlm_text = response.choices[0].message.content or ""
        vlm_data = _extract_json_from_text(vlm_text)

        if not isinstance(vlm_data, dict):
            raise ValueError("VLM 输出不是 JSON object。")

        vlm_data.setdefault("scene", "unknown place")
        vlm_data.setdefault("objects", [])
        vlm_data.setdefault("mood", "unknown")

        print(f"[VLM Agent] ✅ 图片解析结果: {json.dumps(vlm_data, ensure_ascii=False)}")

        return {
            "visual_context": vlm_data,
            "current_image_base64": None,
        }

    except Exception as e:
        print(f"[VLM Agent] ❌ 图片解析失败: {e}")
        return {
            "visual_context": state.get(
                "visual_context",
                {"scene": "unknown place", "objects": [], "mood": "unknown"},
            ),
            "current_image_base64": None,
        }


async def perceive_image_base64(base64_image: str) -> Dict[str, Any]:
    """
    给 routes.py 使用的辅助函数。

    为什么需要这个？
    - 你原来的逻辑希望先通过 VLM 得到 scene
    - 然后用 scene 初始化 Session 并触发 Milvus RAG 检索
    """
    fake_state = AgentState(
        current_image_base64=base64_image,
        visual_context={"scene": "unknown place", "objects": [], "mood": "unknown"},
    )
    return await vlm_perception_node(fake_state)


# =========================================================
# 2. LangGraph 路由
# =========================================================

def route_by_input(state: AgentState) -> str:
    """
    条件入口：
    - 有图片：先进入 VLM Agent
    - 没图片：直接进入 Examiner Agent
    """
    if state.get("current_image_base64"):
        return "vlm_perception"

    return "examiner_agent"


# =========================================================
# 3. 构建 LangGraph 工作流
# =========================================================

workflow = StateGraph(AgentState)

workflow.add_node("vlm_perception", vlm_perception_node)
workflow.add_node("examiner_agent", examiner_agent_node)
workflow.add_node("scoring_agent", scoring_agent_node)

workflow.set_conditional_entry_point(
    route_by_input,
    {
        "vlm_perception": "vlm_perception",
        "examiner_agent": "examiner_agent",
    },
)

# 图片理解后进入考官节点
workflow.add_edge("vlm_perception", "examiner_agent")

# 考官生成下一题后，评分助手静默评分上一轮用户回答
workflow.add_edge("examiner_agent", "scoring_agent")

# Scoring Agent 写入 score_reports 后结束本轮
workflow.add_edge("scoring_agent", END)

compiled_agent = workflow.compile()