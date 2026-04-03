from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


class MarketAnalysisError(RuntimeError):
    """市场分析执行失败。"""


class MarketAnalysisSecurityError(MarketAnalysisError):
    """市场分析代码触发了安全限制。"""


class MarketAnalysisTimeoutError(MarketAnalysisError):
    """市场分析代码执行超时。"""


def run_market_analysis(*, code: str, dataset: Dict[str, Any], timeout_seconds: int = 12) -> Dict[str, Any]:
    """在独立 worker 中执行受限市场分析代码。"""
    worker_path = Path(__file__).with_name("code_runner_worker.py")
    payload = {
        "code": code,
        "dataset": dataset,
    }

    try:
        completed = subprocess.run(
            [sys.executable, str(worker_path)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            cwd=str(worker_path.parent),
            timeout=max(int(timeout_seconds), 1) + 2,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MarketAnalysisTimeoutError("Python 分析超时，已被终止") from exc

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if not stdout:
        suffix = f"；stderr: {stderr}" if stderr else ""
        raise MarketAnalysisError(f"分析执行器未返回结果{suffix}")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        suffix = f"；stderr: {stderr}" if stderr else ""
        raise MarketAnalysisError(f"分析执行器输出无法解析为 JSON{suffix}") from exc

    if payload.get("status") == "ok":
        return payload.get("result") or {}

    message = str(payload.get("error") or "未知执行错误")
    kind = str(payload.get("kind") or "runtime")
    if stderr:
        message = f"{message} | stderr: {stderr.splitlines()[-1]}"

    if kind == "security":
        raise MarketAnalysisSecurityError(message)
    if kind == "timeout":
        raise MarketAnalysisTimeoutError(message)
    raise MarketAnalysisError(message)
