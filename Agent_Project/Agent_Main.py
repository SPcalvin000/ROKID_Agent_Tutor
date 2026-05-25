# Agent_Main.py
import asyncio
import websockets
import json
import sys
from datetime import datetime

# 导入我们的子系统模块 (后续开发了新模块，只需在这里 import 即可)
from agents import Speaking_agent
from agents import academic_companion


# from agents import essay_grading
# from agents import note_assistant


def _safe_log(message):
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_message = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(safe_message + "\n")


async def handle_client(websocket):
    client_addr = websocket.remote_address
    _safe_log(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ 客户端 {client_addr} 已连接！")
    try:
        async for message in websocket:
            try:
                # 1. 解析 JSON 信封
                data = json.loads(message)

                agent_type = data.get("agent_type")
                event_type = data.get("event_type")
                session_id = data.get("session_id", "anonymous")
                payload = data.get("payload", {})

                _safe_log(
                    f"\n[{datetime.now().strftime('%H:%M:%S')}] 📥 收到任务路由请求: Agent=[{agent_type}], Event=[{event_type}]")

                # 2. 核心路由枢纽 (Router)
                response_data = None

                if agent_type == "ielts_speaking":
                    # 将任务甩给雅思口语模块处理
                    response_data = await Speaking_agent.handle_request(event_type, session_id, payload)

                elif agent_type == "academic_companion":
                    response_data = await academic_companion.handle_request(event_type, session_id, payload)

                elif agent_type == "essay_grading":
                    # 预留给作文批改模块
                    # response_data = await essay_grading.handle_request(...)
                    response_data = {"status": "pending", "message": "作文批改模块开发中..."}

                elif agent_type == "note_assistant":
                    # 预留给笔记助手模块
                    response_data = {"status": "pending", "message": "笔记助手模块开发中..."}

                else:
                    response_data = {"status": "error", "message": f"未知的智能体模块: {agent_type}"}

                # 3. 封装最终结果，按照统一标准发回前端
                response_json = {
                    "agent_type": agent_type,
                    "event_type": f"{event_type}_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().timestamp(),
                    "response": response_data
                }
                await websocket.send(json.dumps(response_json))
                _safe_log(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 处理完成，结果已回传。")

            except json.JSONDecodeError:
                _safe_log(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 收到非 JSON 格式数据。")
                await websocket.send(json.dumps({"error": "Only JSON format is supported."}))

    except websockets.exceptions.ConnectionClosed:
        _safe_log(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 客户端 {client_addr} 已断开。")


async def main():
    _safe_log("🚀 Agent 综合网关 (Gateway) 已启动！")
    _safe_log("正在监听 ws://0.0.0.0:8765 ...")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
