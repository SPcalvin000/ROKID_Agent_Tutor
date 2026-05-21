from datetime import datetime


MAX_HISTORY = 20
SESSION_STORE = {}


def _now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_payload_dict(payload):
    if isinstance(payload, dict):
        return payload
    return {}


def _get_session(session_id):
    session = SESSION_STORE.get(session_id)
    if session is None:
        created_at = _now_iso()
        session = {
            "session_id": session_id,
            "created_at": created_at,
            "updated_at": created_at,
            "latest_state": {},
            "state_history": [],
            "difficulty_events": [],
            "chat_history": [],
        }
        SESSION_STORE[session_id] = session
    return session


def _append_limited(items, entry):
    items.append(entry)
    if len(items) > MAX_HISTORY:
        del items[:-MAX_HISTORY]


def _build_session_snapshot(session):
    latest_state = session.get("latest_state") or {}
    difficulty_events = session.get("difficulty_events") or []

    if not latest_state and not difficulty_events:
        overall_status = "no_session_data"
        suggested_focus = "Send a state_update or difficulty_event first so the companion can build context."
    elif difficulty_events:
        overall_status = "difficulty_detected"
        last_event = difficulty_events[-1]
        challenge = (
            last_event.get("challenge")
            or last_event.get("difficulty")
            or last_event.get("event")
            or "recent difficulty"
        )
        suggested_focus = f"Review the latest difficulty event and define one next action for {challenge}."
    else:
        overall_status = "tracking"
        task_name = latest_state.get("task") or latest_state.get("activity") or "the current task"
        suggested_focus = f"Keep tracking progress on {task_name} and send a session_review when you want a summary."

    return {
        "session_id": session["session_id"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "overall_status": overall_status,
        "state_count": len(session.get("state_history", [])),
        "difficulty_count": len(difficulty_events),
        "latest_state": latest_state,
        "recent_difficulty_events": difficulty_events[-3:],
        "suggested_focus": suggested_focus,
    }


def _build_chat_reply(message, session_snapshot):
    latest_state = session_snapshot.get("latest_state") or {}
    difficulty_count = session_snapshot.get("difficulty_count", 0)
    focus_level = latest_state.get("focus_level") or latest_state.get("focus") or "unknown"
    task_name = latest_state.get("task") or latest_state.get("activity") or "your current work"

    if not message:
        return (
            "Academic companion is online. Share your question, current task, or blocker, "
            "and I will keep the conversation tied to this session."
        )

    if difficulty_count:
        return (
            f"I received your message about \"{message}\". I can see {difficulty_count} recorded difficulty event(s) "
            f"and your latest focus level is {focus_level}. I suggest clarifying the next concrete step for {task_name} first."
        )

    return (
        f"I received your message about \"{message}\". Your latest tracked task is {task_name} "
        f"with focus level {focus_level}. If you want, send a state_update or session_review next for a more grounded summary."
    )


async def _handle_text_chat(session_id, payload):
    session = _get_session(session_id)
    message = str(payload.get("message") or payload.get("text") or "").strip()
    recorded_at = _now_iso()

    session_snapshot = _build_session_snapshot(session)
    reply = _build_chat_reply(message, session_snapshot)

    if message:
        _append_limited(session["chat_history"], {
            "role": "user",
            "message": message,
            "recorded_at": recorded_at,
        })
    _append_limited(session["chat_history"], {
        "role": "assistant",
        "message": reply,
        "recorded_at": recorded_at,
    })
    session["updated_at"] = recorded_at

    return {
        "status": "success",
        "data": {
            "session_id": session_id,
            "event_type": "text_chat",
            "reply": reply,
            "received_message": message,
            "session_snapshot": _build_session_snapshot(session),
        },
    }


async def _handle_state_update(session_id, payload):
    session = _get_session(session_id)
    recorded_at = _now_iso()
    state_entry = {
        "recorded_at": recorded_at,
        **payload,
    }

    session["latest_state"] = state_entry
    _append_limited(session["state_history"], state_entry)
    session["updated_at"] = recorded_at

    return {
        "status": "success",
        "data": {
            "session_id": session_id,
            "event_type": "state_update",
            "state": state_entry,
            "state_count": len(session["state_history"]),
            "session_snapshot": _build_session_snapshot(session),
        },
    }


async def _handle_difficulty_event(session_id, payload):
    session = _get_session(session_id)
    recorded_at = _now_iso()
    event_index = len(session["difficulty_events"]) + 1
    event_entry = {
        "event_id": payload.get("event_id") or f"difficulty_{event_index}",
        "recorded_at": recorded_at,
        **payload,
    }

    _append_limited(session["difficulty_events"], event_entry)
    session["updated_at"] = recorded_at

    return {
        "status": "success",
        "data": {
            "session_id": session_id,
            "event_type": "difficulty_event",
            "difficulty_event": event_entry,
            "difficulty_count": len(session["difficulty_events"]),
            "session_snapshot": _build_session_snapshot(session),
        },
    }


async def _handle_session_review(session_id, payload):
    session = _get_session(session_id)
    session_snapshot = _build_session_snapshot(session)
    review_request = {
        "requested_at": _now_iso(),
        **payload,
    }

    return {
        "status": "success",
        "data": {
            "session_id": session_id,
            "event_type": "session_review",
            "review_request": review_request,
            "review": session_snapshot,
        },
    }


async def handle_request(event_type, session_id, payload):
    safe_payload = _ensure_payload_dict(payload)
    safe_session_id = str(session_id or "anonymous")

    if event_type == "text_chat":
        return await _handle_text_chat(safe_session_id, safe_payload)
    if event_type == "state_update":
        return await _handle_state_update(safe_session_id, safe_payload)
    if event_type == "difficulty_event":
        return await _handle_difficulty_event(safe_session_id, safe_payload)
    if event_type == "session_review":
        return await _handle_session_review(safe_session_id, safe_payload)

    return {
        "status": "error",
        "message": f"academic_companion does not support event_type: {event_type}",
    }
