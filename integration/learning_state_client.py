import os
import time


DEFAULT_LSG_BASE_URL = "http://127.0.0.1:5000"
DEFAULT_LSG_TIMEOUT_SECONDS = 0.8
FRAME_ENDPOINT = "/api/v1/rokid/frame"
STATUS_ENDPOINT = "/status"


def is_lsg_enabled():
    raw_value = str(os.getenv("ENABLE_LSG_BRIDGE", "false")).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def normalize_base_url(base_url):
    candidate = str(base_url or os.getenv("LSG_BASE_URL", DEFAULT_LSG_BASE_URL)).strip()
    if not candidate:
        candidate = DEFAULT_LSG_BASE_URL
    return candidate.rstrip("/")


def build_frame_request(image_bytes, mime_type="image/webp", task_mode="reading"):
    if image_bytes is None:
        image_bytes = b""
    file_extension = _extension_for_mime_type(mime_type)
    timestamp_ms = str(int(time.time() * 1000))
    return {
        "data": {
            "task_mode": str(task_mode or "reading"),
            "timestamp_ms": timestamp_ms,
        },
        "files": {
            "frame": (f"lsg-bridge-frame{file_extension}", image_bytes, mime_type),
        },
    }


def send_frame_to_lsg(image_bytes, mime_type="image/webp", task_mode="reading"):
    if not is_lsg_enabled():
        return None

    request_payload = build_frame_request(image_bytes, mime_type=mime_type, task_mode=task_mode)
    url = f"{normalize_base_url(None)}{FRAME_ENDPOINT}"
    timeout_seconds = _get_timeout_seconds()
    try:
        response = _requests_post(
            url,
            data=request_payload["data"],
            files=request_payload["files"],
            timeout=timeout_seconds,
        )
        if response is None or response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


def fetch_lsg_status():
    if not is_lsg_enabled():
        return None

    url = f"{normalize_base_url(None)}{STATUS_ENDPOINT}"
    timeout_seconds = _get_timeout_seconds()
    try:
        response = _requests_get(url, timeout=timeout_seconds)
        if response is None or response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


def build_learning_state_summary(status_json):
    if not isinstance(status_json, dict):
        return None

    interpreted_state = status_json.get("interpreted_state")
    interpreted_confidence = status_json.get("interpreted_confidence")
    state_hint = status_json.get("state_hint")
    interpreted_evidence = status_json.get("interpreted_evidence")

    if (
        interpreted_state is None
        and interpreted_confidence is None
        and state_hint is None
        and interpreted_evidence is None
    ):
        return None

    return {
        "interpreted_state": interpreted_state,
        "interpreted_confidence": interpreted_confidence,
        "state_hint": state_hint,
        "interpreted_evidence": interpreted_evidence if isinstance(interpreted_evidence, list) else [],
    }


def _get_timeout_seconds():
    raw_value = os.getenv("LSG_TIMEOUT_SECONDS", str(DEFAULT_LSG_TIMEOUT_SECONDS))
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_LSG_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_LSG_TIMEOUT_SECONDS


def _extension_for_mime_type(mime_type):
    normalized = str(mime_type or "image/webp").strip().lower()
    if normalized == "image/jpeg":
        return ".jpg"
    if normalized == "image/png":
        return ".png"
    if normalized == "image/webp":
        return ".webp"
    return ".bin"


def _requests_post(url, data, files, timeout):
    requests_module = _load_requests_module()
    if requests_module is None:
        return None
    return requests_module.post(url, data=data, files=files, timeout=timeout)


def _requests_get(url, timeout):
    requests_module = _load_requests_module()
    if requests_module is None:
        return None
    return requests_module.get(url, timeout=timeout)


def _load_requests_module():
    try:
        import requests  # type: ignore
    except Exception:
        return None
    return requests
