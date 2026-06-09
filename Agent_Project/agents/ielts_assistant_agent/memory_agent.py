# agents/ielts_assistant_agent/memory_agent.py
"""
雅思口语多智能体系统 - 长期记忆 / 弱点画像 Agent

职责：
1. 调用 embedding 模型，把场景或弱点文本变成向量。
2. 从 Milvus 检索与当前场景相关的用户弱点画像。
3. 在最终报告生成后，可把新的弱点摘要写回 Milvus。

当前阶段重点是“保留原有 Milvus RAG 能力并模块化”。
后续接入 SQL 用户系统后，建议给 Milvus 记录增加 user_id 字段，实现多用户隔离。
"""

# agents/ielts_assistant_agent/memory_agent.py
from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any, Dict, List

from .persistence import native_client, rag_client, RAG_COLLECTION_NAME


# =========================================================
# 1. Embedding 工具
# =========================================================

async def get_query_embedding(text: str) -> List[float]:
    """
    调用 DashScope OpenAI-compatible Embedding API。
    当前 Milvus schema 使用 text-embedding-v3 的 1024 维向量。
    """
    response = await native_client.embeddings.create(
        model="text-embedding-v3",
        input=text,
    )
    return response.data[0].embedding


# =========================================================
# 2. Milvus 弱点画像检索
# =========================================================

async def retrieve_user_profile(current_scene: str) -> str:
    """
    根据当前场景检索用户长期弱点画像。

    例子：
    - 当前场景 cafe
    - 检索 “User weakness related to cafe”
    - 返回历史弱点，如：limited vocabulary about public places
    """
    if not rag_client:
        return ""

    try:
        search_vec = await get_query_embedding(f"User weakness related to {current_scene}")

        # pymilvus 是同步客户端，这里放到线程池，避免阻塞 asyncio 事件循环。
        search_results = await asyncio.to_thread(
            rag_client.search,
            collection_name=RAG_COLLECTION_NAME,
            data=[search_vec],
            limit=1,
            output_fields=["content"],
        )

        if search_results and search_results[0]:
            entity = search_results[0][0].get("entity", {})
            return entity.get("content", "") or ""

    except Exception as e:
        print(f"[RAG 检索模块] ⚠️ Milvus 检索失败: {e}")

    return ""


# =========================================================
# 3. Shadow Summary：从评分结果压缩弱点摘要
# =========================================================

def build_shadow_summary(score_reports: List[Dict[str, Any]]) -> str:
    """
    把多个 ScoreReport 压缩成一句内部提示。

    这个 summary 可以给 Examiner Agent 轻量读取，
    但 Examiner 不能把它直接告诉用户。
    """
    if not score_reports:
        return ""

    tags: List[str] = []
    for report in score_reports:
        tags.extend(report.get("weakness_tags", []) or [])

    top_tags = [tag for tag, _ in Counter(tags).most_common(5)]

    avg_items = []
    for key, label in [
        ("fluency_coherence", "Fluency/Coherence"),
        ("lexical_resource", "Lexical Resource"),
        ("grammatical_range_accuracy", "Grammar"),
    ]:
        values = [
            float(r[key])
            for r in score_reports
            if isinstance(r.get(key), (int, float))
        ]
        if values:
            avg_items.append(f"{label}: {sum(values) / len(values):.1f}")

    tag_text = ", ".join(top_tags) if top_tags else "no stable weakness tags yet"
    avg_text = "; ".join(avg_items) if avg_items else "not enough scored turns"

    return (
        f"Internal scoring trend: {avg_text}. "
        f"Main weakness tags: {tag_text}. "
        "Use this only to adapt question difficulty; never reveal scores during the live test."
    )


async def maybe_store_weakness_summary_to_milvus(
    *,
    session_id: str,
    score_reports: List[Dict[str, Any]],
) -> None:
    """
    预留接口：把本次考试弱点写入 Milvus。

    当前 Phase 2 默认不强制写入，因为你的 Milvus collection schema
    可能还没有为自动写入设计好 primary key / scene_tag 字段。
    Phase 4 做历史归档时建议正式启用。
    """
    if not rag_client or not score_reports:
        return

    summary = build_shadow_summary(score_reports)
    if not summary:
        return

    try:
        vector = await get_query_embedding(summary)
        data = [{
            "id": f"weakness_{session_id}",
            "scene_tag": "ielts_speaking",
            "content": summary,
            "vector": vector,
        }]

        await asyncio.to_thread(
            rag_client.insert,
            collection_name=RAG_COLLECTION_NAME,
            data=data,
        )
        print(f"[长期记忆] 🧠 已写入本次弱点摘要: {session_id}")

    except Exception as e:
        print(f"[长期记忆] ⚠️ 写入 Milvus 失败，已跳过: {e}")