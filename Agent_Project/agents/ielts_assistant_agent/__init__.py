# agents/ielts_assistant_agent/__init__.py
"""
IELTS Assistant Agent 模块包。

当前模块职责：
- Examiner Agent：实时生成 IELTS 考官问题
- Scoring Agent：静默评分，不直接展示给眼镜端
- Report Agent：生成临时 JSON 报告快照
- Memory Agent：对接 Milvus 弱点记忆
- Graph：使用 LangGraph 编排多节点工作流
"""

from .routes import handle_request

__all__ = ["handle_request"]