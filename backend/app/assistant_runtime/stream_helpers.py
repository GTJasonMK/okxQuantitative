from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    chunks: List[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("text"), str) and item["text"]:
            chunks.append(item["text"])
        elif isinstance(item.get("value"), str) and item["value"]:
            chunks.append(item["value"])
    return "".join(chunks)


def _sanitize_completion_history(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    index = 0

    while index < len(items):
        item = items[index]
        role = item.get("role")
        metadata = item.get("metadata") or {}
        tool_calls = metadata.get("tool_calls")

        if role == "assistant" and isinstance(tool_calls, list) and tool_calls:
            next_index = index + 1
            tool_rows: List[Dict[str, Any]] = []
            while next_index < len(items) and items[next_index].get("role") == "tool":
                tool_rows.append(items[next_index])
                next_index += 1

            matched_tool_ids = {
                str(tool_row.get("tool_call_id") or "").strip()
                for tool_row in tool_rows
                if str(tool_row.get("tool_call_id") or "").strip()
            }
            valid_tool_calls = [
                tool_call
                for tool_call in tool_calls
                if str((tool_call or {}).get("id") or "").strip() in matched_tool_ids
            ]
            if valid_tool_calls:
                sanitized.append({
                    "role": "assistant",
                    "content": item.get("content") or "",
                    "tool_calls": valid_tool_calls,
                })
                emitted_tool_ids: set[str] = set()
                for tool_row in tool_rows:
                    tool_call_id = str(tool_row.get("tool_call_id") or "").strip()
                    if not tool_call_id or tool_call_id in emitted_tool_ids:
                        continue
                    if tool_call_id not in matched_tool_ids:
                        continue
                    emitted_tool_ids.add(tool_call_id)
                    sanitized.append({
                        "role": "tool",
                        "content": tool_row.get("content") or "",
                        "tool_call_id": tool_call_id,
                    })
            index = next_index
            continue

        if role != "tool":
            sanitized.append({
                "role": role,
                "content": item.get("content") or "",
            })
        index += 1

    return sanitized


def _append_stream_tool_call_buffer(
    tool_call_buffers: List[Dict[str, Any]],
    delta_tool_calls: Any,
) -> None:
    if not isinstance(delta_tool_calls, list):
        return

    for item in delta_tool_calls:
        if not isinstance(item, dict):
            continue
        raw_index = item.get("index", len(tool_call_buffers))
        try:
            index = max(int(raw_index), 0)
        except Exception:
            index = len(tool_call_buffers)

        while len(tool_call_buffers) <= index:
            tool_call_buffers.append({
                "id": "",
                "type": "function",
                "function": {
                    "name": "",
                    "arguments": "",
                },
            })

        target = tool_call_buffers[index]
        if isinstance(item.get("id"), str) and item["id"]:
            target["id"] = item["id"]
        if isinstance(item.get("type"), str) and item["type"]:
            target["type"] = item["type"]

        function_payload = item.get("function") or {}
        if not isinstance(function_payload, dict):
            continue

        target_function = target.setdefault("function", {"name": "", "arguments": ""})
        if isinstance(function_payload.get("name"), str) and function_payload["name"]:
            target_function["name"] = f"{target_function.get('name', '')}{function_payload['name']}"
        if isinstance(function_payload.get("arguments"), str) and function_payload["arguments"]:
            target_function["arguments"] = (
                f"{target_function.get('arguments', '')}{function_payload['arguments']}"
            )


def _finalize_stream_tool_calls(tool_call_buffers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    finalized: List[Dict[str, Any]] = []
    for item in tool_call_buffers:
        function_payload = item.get("function") or {}
        tool_name = str(function_payload.get("name") or "").strip()
        tool_arguments = str(function_payload.get("arguments") or "")
        if not (tool_name or tool_arguments or item.get("id")):
            continue
        finalized.append({
            "id": str(item.get("id") or "").strip(),
            "type": str(item.get("type") or "function").strip() or "function",
            "function": {
                "name": tool_name,
                "arguments": tool_arguments,
            },
        })
    return finalized


def _should_fallback_streaming(status_code: int, detail: str) -> bool:
    normalized = (detail or "").strip().lower()
    if status_code in {404, 405, 415, 422, 501}:
        return True
    if status_code == 400 and any(token in normalized for token in (
        "stream",
        "sse",
        "not support",
        "unsupported",
        "does not support",
        "invalid stream",
        "streaming is not available",
    )):
        return True
    return False


async def _maybe_emit_stream_delta(
    callback: Optional[Callable[[str], Awaitable[None] | None]],
    delta: str,
) -> None:
    if not callback or not delta:
        return
    result = callback(delta)
    if inspect.isawaitable(result):
        await result

