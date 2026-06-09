# agents/Speaking_agent.py
"""
兼容层：保留旧模块名 Speaking_agent。

你的 Agent_Main.py 当前写法是：
    from agents import Speaking_agent
    await Speaking_agent.handle_request(...)

为了不影响其他团队成员和现有 Tester.html，本文件不再写业务逻辑，
只把请求转发给新的模块化包：agents/ielts_assistant_agent/。
"""

# agents/Speaking_agent.py
"""
兼容层文件：保留旧的 Speaking_agent.handle_request 调用方式。

为什么还要保留这个文件？
1. Agent_Main.py 目前仍然使用：from agents import Speaking_agent
2. 大型眼镜助手项目中，Gateway 层不应该因为 IELTS 模块内部重构而频繁修改
3. 这里作为“适配器 Adapter”，把旧入口转发到新的模块化包

真正的业务代码已经移动到：
agents/ielts_assistant_agent/
"""

from .ielts_assistant_agent.routes import handle_request

__all__ = ["handle_request"]