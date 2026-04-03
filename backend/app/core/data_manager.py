import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .data_fetcher import Candle
from ..utils.timeframes import estimate_days_for_candle_count, timeframe_to_ms

if TYPE_CHECKING:
    from .data_storage import DataStorage


class DataManager:
    """
    数据管理器
    整合数据获取和存储功能
    """

    def __init__(self, storage: "DataStorage", fetcher=None):
        """
        初始化数据管理器

        Args:
            storage: 数据存储器
            fetcher: 数据获取器（可选）
        """
        self.storage = storage
        self.fetcher = fetcher

    def _emit_progress(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
        **payload: Any,
    ) -> None:
        """向外部任务管理器上报同步进度。"""
        if not progress_callback:
            return
        try:
            progress_callback(payload)
        except Exception:
            pass

    def _build_sync_result(
        self,
        inst_id: str,
        timeframe: str,
        inst_type: str,
        *,
        mode: str,
        fetched_count: int,
        saved_count: int,
        batches: int,
        api_calls: int,
    ) -> Dict[str, Any]:
        sync_record = self.storage.get_sync_record(inst_id, timeframe, inst_type) or {}
        return {
            "mode": mode,
            "fetched_count": int(fetched_count),
            "saved_count": int(saved_count),
            "batches": int(batches),
            "api_calls": int(api_calls),
            "history_complete": bool(sync_record.get("history_complete", False)),
            "candle_count": int(sync_record.get("candle_count", 0) or 0),
            "oldest_timestamp": sync_record.get("oldest_timestamp"),
            "newest_timestamp": sync_record.get("newest_timestamp"),
            "last_sync_mode": sync_record.get("last_sync_mode", mode),
            "last_sync_time": sync_record.get("last_sync_time"),
        }

    def _get_local_sync_state(
        self,
        inst_id: str,
        timeframe: str,
        inst_type: str,
    ) -> Dict[str, Any]:
        """读取本地某个币种/周期的覆盖状态。"""
        sync_record = self.storage.get_sync_record(inst_id, timeframe, inst_type) or {}
        candle_range = self.storage.get_candle_range(inst_id, timeframe, inst_type=inst_type)

        if candle_range:
            oldest_ts, newest_ts, candle_count = candle_range
        else:
            oldest_ts = sync_record.get("oldest_timestamp")
            newest_ts = sync_record.get("newest_timestamp")
            candle_count = int(sync_record.get("candle_count", 0) or 0)

        return {
            "sync_record": sync_record,
            "oldest_timestamp": oldest_ts,
            "newest_timestamp": newest_ts,
            "candle_count": int(candle_count or 0),
            "history_complete": bool(sync_record.get("history_complete", False)),
        }

    def determine_sync_strategy(
        self,
        inst_id: str,
        timeframe: str,
        *,
        count: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        inst_type: str = "SPOT",
    ) -> Optional[Dict[str, Any]]:
        """判断当前请求是否需要先做本地数据同步。"""
        if not self.fetcher:
            return None

        state = self._get_local_sync_state(inst_id, timeframe, inst_type)
        candle_count = state["candle_count"]
        oldest_ts = state["oldest_timestamp"]
        newest_ts = state["newest_timestamp"]
        history_complete = state["history_complete"]

        count_hint = max(int(count or 0), 0)
        bootstrap_count = max(count_hint, 300)
        bootstrap_days = estimate_days_for_candle_count(
            timeframe=timeframe,
            count=bootstrap_count,
            minimum_days=7,
        )

        if candle_count <= 0:
            return {
                "mode": "full",
                "days": max(bootstrap_days, 30),
                "reason": "missing_local_data",
                **state,
            }

        request_start_ms = int(start_time.timestamp() * 1000) if start_time else None
        request_end_ms = int(end_time.timestamp() * 1000) if end_time else None

        need_backfill = False
        if request_start_ms is not None and (oldest_ts is None or request_start_ms < oldest_ts) and not history_complete:
            need_backfill = True
        if count_hint > 0 and candle_count < count_hint and start_time is None and not history_complete:
            need_backfill = True
        if need_backfill:
            return {
                "mode": "full",
                "days": max(bootstrap_days, 30),
                "reason": "insufficient_local_history",
                **state,
            }

        timeframe_ms = timeframe_to_ms(timeframe)
        now_ms = int(datetime.now().timestamp() * 1000)
        need_incremental = False
        if newest_ts:
            if newest_ts + (2 * timeframe_ms) < now_ms:
                need_incremental = True
            if request_end_ms is not None and request_end_ms > newest_ts + timeframe_ms:
                need_incremental = True

        if need_incremental:
            return {
                "mode": "incremental",
                "days": max(bootstrap_days, 7),
                "reason": "latest_gap_detected",
                **state,
            }

        return None

    def ensure_local_candles(
        self,
        inst_id: str,
        timeframe: str,
        *,
        count: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        inst_type: str = "SPOT",
        auto_sync: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """确保本地库已具备本次请求所需的 K 线覆盖。"""
        if not auto_sync:
            return None

        plan = self.determine_sync_strategy(
            inst_id,
            timeframe,
            count=count,
            start_time=start_time,
            end_time=end_time,
            inst_type=inst_type,
        )
        if not plan:
            return None

        if plan["mode"] == "full":
            return self.sync_candles_full(
                inst_id,
                timeframe,
                days=plan["days"],
                inst_type=inst_type,
            )
        return self.sync_candles_incremental(
            inst_id,
            timeframe,
            days=plan["days"],
            inst_type=inst_type,
        )

    def sync_candles_window(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        同步最近 N 天窗口的数据。

        适用于：
        - 首次快速拉起图表
        - 需要补足某个回测窗口最近一段历史
        """
        if not self.fetcher:
            raise ValueError("未配置数据获取器")

        from datetime import timedelta

        normalized_days = max(int(days), 1)
        start_time = datetime.now() - timedelta(days=normalized_days)
        timeframe_ms = timeframe_to_ms(timeframe)
        estimated_count = max(
            300,
            int((normalized_days * 24 * 60 * 60 * 1000) / timeframe_ms) + 5,
        )

        self._emit_progress(
            progress_callback,
            progress=10,
            message=f"正在拉取最近 {normalized_days} 天历史",
            phase="fetch_window",
        )

        print(f"开始同步 {inst_id} {timeframe} 最近{normalized_days}天数据...")

        candles = self.fetcher.get_history_candles(
            inst_id=inst_id,
            timeframe=timeframe,
            start_time=start_time,
            max_candles=estimated_count,
        )

        fetched_count = len(candles)
        saved_count = 0
        if candles:
            self._emit_progress(
                progress_callback,
                progress=70,
                message=f"已获取 {fetched_count} 根，正在写入本地数据库",
                phase="save_window",
                fetched_count=fetched_count,
            )
            saved_count = self.storage.save_candles(inst_id, timeframe, candles, inst_type)

        self.storage.update_sync_record(
            inst_id,
            timeframe,
            inst_type,
            last_sync_mode="window",
        )

        api_calls = 1 if fetched_count == 0 else max(1, (fetched_count + 299) // 300)
        result = self._build_sync_result(
            inst_id,
            timeframe,
            inst_type,
            mode="window",
            fetched_count=fetched_count,
            saved_count=saved_count,
            batches=max(1, (fetched_count + 299) // 300) if fetched_count else 0,
            api_calls=api_calls,
        )
        self._emit_progress(
            progress_callback,
            progress=100,
            message="窗口同步完成",
            phase="done",
            **result,
        )
        return result

    def sync_candles_incremental(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        仅同步本地最新 K 线之后的缺口。

        - 本地已有数据：只补 newest_timestamp 之后的新 bar
        - 本地为空：退化为最近 N 天 bootstrap
        """
        if not self.fetcher:
            raise ValueError("未配置数据获取器")

        sync_record = self.storage.get_sync_record(inst_id, timeframe, inst_type)
        newest_ts = sync_record.get("newest_timestamp") if sync_record else None

        if not newest_ts:
            self._emit_progress(
                progress_callback,
                progress=5,
                message="本地无历史数据，先执行窗口初始化",
                phase="bootstrap_incremental",
            )
            bootstrap_result = self.sync_candles_window(
                inst_id,
                timeframe,
                days=days,
                inst_type=inst_type,
                progress_callback=progress_callback,
            )
            self.storage.update_sync_record(
                inst_id,
                timeframe,
                inst_type,
                history_complete=False,
                last_sync_mode="incremental",
            )
            bootstrap_result["mode"] = "incremental"
            bootstrap_result["history_complete"] = False
            bootstrap_result["last_sync_mode"] = "incremental"
            self._emit_progress(
                progress_callback,
                progress=100,
                message="增量同步完成（初始化）",
                phase="done",
                **bootstrap_result,
            )
            return bootstrap_result

        timeframe_ms = timeframe_to_ms(timeframe)
        start_ts = int(newest_ts) + timeframe_ms
        now_ms = int(datetime.now().timestamp() * 1000)
        if start_ts > now_ms:
            self.storage.update_sync_record(
                inst_id,
                timeframe,
                inst_type,
                last_sync_mode="incremental",
            )
            result = self._build_sync_result(
                inst_id,
                timeframe,
                inst_type,
                mode="incremental",
                fetched_count=0,
                saved_count=0,
                batches=0,
                api_calls=0,
            )
            self._emit_progress(
                progress_callback,
                progress=100,
                message="本地数据已是最新，无需增量同步",
                phase="done",
                **result,
            )
            return result

        # 使用 UTC 感知时间，避免 Windows 对接近 Unix epoch 的本地时间戳抛 OSError。
        start_time = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
        missing_count = max(1, int((now_ms - newest_ts) / timeframe_ms) + 2)
        self._emit_progress(
            progress_callback,
            progress=15,
            message="正在拉取最新缺口数据",
            phase="fetch_incremental",
            newest_timestamp=newest_ts,
        )
        candles = self.fetcher.get_history_candles(
            inst_id=inst_id,
            timeframe=timeframe,
            start_time=start_time,
            max_candles=max(300, missing_count + 5),
        )

        fetched_count = len(candles)
        saved_count = 0
        if candles:
            self._emit_progress(
                progress_callback,
                progress=75,
                message=f"已获取 {fetched_count} 根增量 K 线，正在写入本地数据库",
                phase="save_incremental",
                fetched_count=fetched_count,
            )
            saved_count = self.storage.save_candles(inst_id, timeframe, candles, inst_type)

        self.storage.update_sync_record(
            inst_id,
            timeframe,
            inst_type,
            last_sync_mode="incremental",
        )

        api_calls = 1 if fetched_count == 0 else max(1, (fetched_count + 299) // 300)
        result = self._build_sync_result(
            inst_id,
            timeframe,
            inst_type,
            mode="incremental",
            fetched_count=fetched_count,
            saved_count=saved_count,
            batches=max(1, (fetched_count + 299) // 300) if fetched_count else 0,
            api_calls=api_calls,
        )
        self._emit_progress(
            progress_callback,
            progress=100,
            message="增量同步完成",
            phase="done",
            **result,
        )
        return result

    def sync_candles_full(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        全量回补历史数据，并把最新缺口补齐。

        设计目标：
        - 若本地已有一部分数据，先补最新，再向过去翻页直到最早可取历史
        - 若本地为空，从最新页开始向过去完整回补
        """
        if not self.fetcher:
            raise ValueError("未配置数据获取器")

        print(f"开始全量回补 {inst_id} {timeframe} 历史数据...")
        self._emit_progress(
            progress_callback,
            progress=5,
            message="正在准备全量历史回补",
            phase="prepare_full",
        )

        total_fetched = 0
        total_saved = 0
        total_batches = 0
        total_api_calls = 0

        existing_range = self.storage.get_candle_range(inst_id, timeframe, inst_type=inst_type)
        if existing_range:
            self._emit_progress(
                progress_callback,
                progress=12,
                message="检测到本地已有历史，先补齐最新缺口",
                phase="incremental_before_full",
            )
            incremental_result = self.sync_candles_incremental(
                inst_id,
                timeframe,
                days=days,
                inst_type=inst_type,
                progress_callback=progress_callback,
            )
            total_fetched += incremental_result["fetched_count"]
            total_saved += incremental_result["saved_count"]
            total_batches += incremental_result["batches"]
            total_api_calls += incremental_result["api_calls"]
            existing_range = self.storage.get_candle_range(inst_id, timeframe, inst_type=inst_type)

        cursor = existing_range[0] if existing_range else None
        saw_any_data = bool(existing_range)
        history_complete = False
        # 防止 API 异常导致无限循环（OKX 历史最多约 1440 根/页 × 500 页 = 72 万根）
        MAX_BACKFILL_BATCHES = 500

        while total_batches < MAX_BACKFILL_BATCHES:
            total_api_calls += 1
            self._emit_progress(
                progress_callback,
                progress=min(92, 20 + total_batches * 6),
                message=f"正在向过去回补历史，第 {total_batches + 1} 批",
                phase="backfill_history",
                batches=total_batches,
                fetched_count=total_fetched,
                saved_count=total_saved,
                cursor=cursor,
            )
            batch = self.fetcher.get_candles(
                inst_id=inst_id,
                timeframe=timeframe,
                limit=300,
                after=cursor,
            )

            if not batch:
                history_complete = saw_any_data
                break

            oldest_ts = batch[0].timestamp
            if cursor is not None and oldest_ts == cursor:
                history_complete = True
                break

            saved_count = self.storage.save_candles(inst_id, timeframe, batch, inst_type)
            total_fetched += len(batch)
            total_saved += saved_count
            total_batches += 1
            saw_any_data = True
            cursor = oldest_ts

            # 全量回补会连续分页较多，请求间做轻微让步，避免集中打满限流。
            time.sleep(0.05)

        self.storage.update_sync_record(
            inst_id,
            timeframe,
            inst_type,
            history_complete=history_complete,
            last_sync_mode="full",
        )

        result = self._build_sync_result(
            inst_id,
            timeframe,
            inst_type,
            mode="full",
            fetched_count=total_fetched,
            saved_count=total_saved,
            batches=total_batches,
            api_calls=total_api_calls,
        )
        self._emit_progress(
            progress_callback,
            progress=100,
            message="全量历史回补完成",
            phase="done",
            **result,
        )
        return result

    def sync_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT"
    ) -> int:
        """
        同步K线数据（从交易所获取并保存到本地）

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            days: 同步最近多少天的数据
            inst_type: 交易类型

        Returns:
            同步的K线数量
        """
        result = self.sync_candles_window(
            inst_id,
            timeframe,
            days=days,
            inst_type=inst_type,
        )
        print(f"同步完成: 获取{result['fetched_count']}条，保存{result['saved_count']}条")
        return result["saved_count"]

    def get_candles_with_sync(
        self,
        inst_id: str,
        timeframe: str,
        count: int = 100,
        auto_sync: bool = True,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """
        获取K线数据，本地不足时自动同步

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            count: 需要的数量
            auto_sync: 是否自动同步
            inst_type: 交易类型

        Returns:
            K线数据列表
        """
        self.ensure_local_candles(
            inst_id,
            timeframe,
            count=count,
            inst_type=inst_type,
            auto_sync=auto_sync,
        )
        return self.storage.get_latest_candles(inst_id, timeframe, count, inst_type=inst_type)

    def get_local_candles(
        self,
        inst_id: str,
        timeframe: str,
        *,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        auto_sync: bool = True,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """从本地数据库取 K 线；需要时先自动同步到本地。"""
        self.ensure_local_candles(
            inst_id,
            timeframe,
            count=limit,
            start_time=start_time,
            end_time=end_time,
            inst_type=inst_type,
            auto_sync=auto_sync,
        )
        if start_time or end_time:
            return self.storage.get_candles(
                inst_id=inst_id,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                inst_type=inst_type,
            )
        return self.storage.get_latest_candles(inst_id, timeframe, limit, inst_type=inst_type)
