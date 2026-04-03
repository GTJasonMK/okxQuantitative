from __future__ import annotations

import ast
import builtins
import json
import math
import os
import pathlib
import socket
import statistics
import subprocess
import sys
import traceback
import urllib.request
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Dict, List

import numpy as np
import pandas as pd


FORBIDDEN_NODE_TYPES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
)

FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "help",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "memoryview",
    "breakpoint",
}

FORBIDDEN_ATTRS = {
    "__globals__",
    "__code__",
    "__class__",
    "__dict__",
    "__subclasses__",
    "__mro__",
    "__bases__",
    "__getattribute__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
}

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
}


class SandboxSecurityError(RuntimeError):
    pass


def _deny_io(*args: Any, **kwargs: Any) -> None:
    raise PermissionError("分析沙箱中禁止文件、网络或子进程 IO")


def _install_runtime_guards() -> None:
    builtins.open = _deny_io

    socket.socket = _deny_io  # type: ignore[assignment]
    socket.create_connection = _deny_io  # type: ignore[assignment]

    subprocess.Popen = _deny_io  # type: ignore[assignment]
    subprocess.run = _deny_io  # type: ignore[assignment]
    subprocess.call = _deny_io  # type: ignore[assignment]
    subprocess.check_call = _deny_io  # type: ignore[assignment]
    subprocess.check_output = _deny_io  # type: ignore[assignment]

    os.system = _deny_io  # type: ignore[assignment]
    os.popen = _deny_io  # type: ignore[assignment]
    os.remove = _deny_io  # type: ignore[assignment]
    os.unlink = _deny_io  # type: ignore[assignment]
    os.mkdir = _deny_io  # type: ignore[assignment]
    os.makedirs = _deny_io  # type: ignore[assignment]
    os.rmdir = _deny_io  # type: ignore[assignment]
    os.rename = _deny_io  # type: ignore[assignment]
    os.replace = _deny_io  # type: ignore[assignment]

    pathlib.Path.open = _deny_io  # type: ignore[assignment]
    pathlib.Path.read_text = _deny_io  # type: ignore[assignment]
    pathlib.Path.write_text = _deny_io  # type: ignore[assignment]
    pathlib.Path.read_bytes = _deny_io  # type: ignore[assignment]
    pathlib.Path.write_bytes = _deny_io  # type: ignore[assignment]

    urllib.request.urlopen = _deny_io  # type: ignore[assignment]

    for attr_name in (
        "read_csv",
        "read_json",
        "read_pickle",
        "read_excel",
        "read_html",
        "read_xml",
        "read_sql",
        "read_sql_query",
        "read_sql_table",
        "read_feather",
        "read_parquet",
        "read_hdf",
        "read_clipboard",
        "read_orc",
        "read_spss",
    ):
        if hasattr(pd, attr_name):
            setattr(pd, attr_name, _deny_io)

    for attr_name in (
        "to_csv",
        "to_json",
        "to_pickle",
        "to_excel",
        "to_sql",
        "to_clipboard",
        "to_html",
        "to_xml",
        "to_markdown",
        "to_feather",
        "to_parquet",
        "to_hdf",
        "to_latex",
    ):
        if hasattr(pd.DataFrame, attr_name):
            setattr(pd.DataFrame, attr_name, _deny_io)
        if hasattr(pd.Series, attr_name):
            setattr(pd.Series, attr_name, _deny_io)

    for attr_name in ("load", "save", "savez", "savez_compressed", "fromfile"):
        if hasattr(np, attr_name):
            setattr(np, attr_name, _deny_io)
    if hasattr(np, "memmap"):
        np.memmap = _deny_io  # type: ignore[assignment]


def _validate_user_code(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    has_analyze = False

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODE_TYPES):
            raise SandboxSecurityError(f"禁止使用语句: {type(node).__name__}")
        if isinstance(node, ast.FunctionDef) and node.name == "analyze":
            has_analyze = True
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
                raise SandboxSecurityError(f"禁止访问名称: {node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS or node.attr.startswith("__"):
                raise SandboxSecurityError(f"禁止访问属性: {node.attr}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                raise SandboxSecurityError(f"禁止调用: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_ATTRS:
                raise SandboxSecurityError(f"禁止调用属性: {node.func.attr}")

    if not has_analyze:
        raise SandboxSecurityError("必须定义 analyze(data, helpers) 函数")


def _safe_number(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, np.generic):
        return _safe_number(value.item())
    return value


def _serialize_value(value: Any, *, row_limit: int = 200) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _safe_number(value)
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_serialize_value(item, row_limit=row_limit) for item in value.tolist()]
    if isinstance(value, pd.Series):
        preview = value.head(row_limit)
        return {
            "type": "series",
            "name": str(value.name or ""),
            "length": int(len(value)),
            "values": [_serialize_value(item, row_limit=row_limit) for item in preview.tolist()],
        }
    if isinstance(value, pd.DataFrame):
        preview = value.head(row_limit).copy()
        preview = preview.replace({np.nan: None})
        rows = []
        for record in preview.to_dict(orient="records"):
            rows.append({str(key): _serialize_value(item, row_limit=row_limit) for key, item in record.items()})
        return {
            "type": "dataframe",
            "columns": [str(item) for item in preview.columns.tolist()],
            "row_count": int(len(value)),
            "rows": rows,
        }
    if isinstance(value, dict):
        return {str(key): _serialize_value(item, row_limit=row_limit) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item, row_limit=row_limit) for item in value]
    return _safe_number(value)


def _normalize_result(result: Any, logs: List[str], dataset: Dict[str, Any]) -> Dict[str, Any]:
    summary: Any = None
    metrics: Dict[str, Any] = {}
    tables: Dict[str, Any] = {}
    artifacts: Dict[str, Any] = {}
    warnings: List[str] = []

    if isinstance(result, dict):
        summary = _serialize_value(result.get("summary"))
        metrics_raw = result.get("metrics", {})
        tables_raw = result.get("tables", {})
        artifacts_raw = result.get("artifacts", {})
        warnings_raw = result.get("warnings", [])
        logs.extend([str(item) for item in result.get("logs", [])])

        metrics = _serialize_value(metrics_raw) if isinstance(metrics_raw, dict) else {"value": _serialize_value(metrics_raw)}
        tables = _serialize_value(tables_raw) if isinstance(tables_raw, dict) else {"result": _serialize_value(tables_raw)}
        artifacts = _serialize_value(artifacts_raw) if isinstance(artifacts_raw, dict) else {"result": _serialize_value(artifacts_raw)}

        extra = {
            key: value
            for key, value in result.items()
            if key not in {"summary", "metrics", "tables", "artifacts", "warnings", "logs"}
        }
        if extra:
            artifacts["result"] = _serialize_value(extra)

        if isinstance(warnings_raw, list):
            warnings = [str(item) for item in warnings_raw]
        elif warnings_raw:
            warnings = [str(warnings_raw)]
    else:
        summary = _serialize_value(result)

    context = dataset.get("context") or {}
    candle_map = dataset.get("candles") or {}
    dataset_overview = {
        "inst_id": context.get("inst_id"),
        "inst_type": context.get("inst_type"),
        "timeframes": {
            str(timeframe): int((payload or {}).get("count", len((payload or {}).get("candles", []))))
            for timeframe, payload in candle_map.items()
        },
        "has_market_snapshot": "market_snapshot" in dataset,
        "has_orderbook": "orderbook" in dataset,
        "has_recent_trades": "recent_trades" in dataset,
        "has_position": "position" in dataset,
        "indicator_timeframes": sorted((dataset.get("indicators") or {}).keys()),
    }

    return {
        "summary": summary,
        "metrics": metrics,
        "tables": tables,
        "artifacts": artifacts,
        "logs": [str(item) for item in logs],
        "warnings": warnings,
        "dataset_overview": dataset_overview,
    }


def _build_helpers(dataset: Dict[str, Any]) -> Dict[str, Any]:
    candles_map = dataset.get("candles") or {}
    indicators_map = dataset.get("indicators") or {}

    def candles_to_frame(timeframe: str) -> pd.DataFrame:
        payload = candles_map.get(timeframe) or {}
        return pd.DataFrame(payload.get("candles") or [])

    def orderbook_to_frame(side: str) -> pd.DataFrame:
        payload = dataset.get("orderbook") or {}
        return pd.DataFrame((payload.get(side) or []))

    def recent_trades_to_frame() -> pd.DataFrame:
        payload = dataset.get("recent_trades") or {}
        return pd.DataFrame(payload.get("trades") or [])

    def latest_indicator(timeframe: str, indicator_name: str) -> Any:
        payload = indicators_map.get(timeframe) or {}
        snapshot = (payload.get("indicator_snapshots") or {}).get(indicator_name) or {}
        return snapshot.get("latest")

    def latest_close(timeframe: str) -> Any:
        frame = candles_to_frame(timeframe)
        if frame.empty or "close" not in frame.columns:
            return None
        return frame["close"].iloc[-1]

    return {
        "candles_to_frame": candles_to_frame,
        "orderbook_to_frame": orderbook_to_frame,
        "recent_trades_to_frame": recent_trades_to_frame,
        "latest_indicator": latest_indicator,
        "latest_close": latest_close,
        "available_timeframes": sorted(candles_map.keys()),
    }


def _build_safe_numpy_namespace() -> SimpleNamespace:
    allowed = (
        "array",
        "asarray",
        "abs",
        "mean",
        "median",
        "std",
        "var",
        "max",
        "min",
        "sum",
        "nanmean",
        "nanmedian",
        "nanstd",
        "nanvar",
        "nanmax",
        "nanmin",
        "nansum",
        "percentile",
        "quantile",
        "diff",
        "where",
        "clip",
        "sqrt",
        "log",
        "exp",
        "corrcoef",
        "cumsum",
        "cumprod",
        "sign",
        "isnan",
        "isfinite",
        "round",
    )
    payload = {name: getattr(np, name) for name in allowed if hasattr(np, name)}
    payload["nan"] = np.nan
    return SimpleNamespace(**payload)


def _build_safe_pandas_namespace() -> SimpleNamespace:
    allowed = (
        "DataFrame",
        "Series",
        "concat",
        "to_datetime",
        "Timestamp",
        "date_range",
        "isna",
        "notna",
    )
    return SimpleNamespace(**{name: getattr(pd, name) for name in allowed if hasattr(pd, name)})


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        code = str(payload.get("code") or "")
        dataset = payload.get("dataset") or {}

        _validate_user_code(code)
        _install_runtime_guards()

        logs: List[str] = []

        def _safe_print(*args: Any, **kwargs: Any) -> None:
            message = " ".join(str(item) for item in args)
            logs.append(message[:1000])

        safe_builtins = dict(SAFE_BUILTINS)
        safe_builtins["print"] = _safe_print

        execution_globals: Dict[str, Any] = {
            "__builtins__": safe_builtins,
            "pd": _build_safe_pandas_namespace(),
            "np": _build_safe_numpy_namespace(),
            "math": math,
            "statistics": statistics,
        }
        execution_locals: Dict[str, Any] = {}

        compiled = compile(code, "<market-analysis>", "exec")
        exec(compiled, execution_globals, execution_locals)

        analyze = execution_locals.get("analyze") or execution_globals.get("analyze")
        if not callable(analyze):
            raise SandboxSecurityError("analyze 必须是可调用函数")

        helpers = _build_helpers(dataset)
        result = analyze(dataset, helpers)
        output = _normalize_result(result, logs, dataset)
        print(json.dumps({"status": "ok", "result": output}, ensure_ascii=False))
    except SandboxSecurityError as exc:
        print(json.dumps({"status": "error", "kind": "security", "error": str(exc)}, ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - 作为 worker 最终兜底
        message = f"{exc.__class__.__name__}: {exc}"
        print(
            json.dumps(
                {
                    "status": "error",
                    "kind": "runtime",
                    "error": message,
                    "traceback": traceback.format_exc(limit=6),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
