# Target Census 独立观测链 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 把 `target_census_15m` 的底层观测来源、合约 universe 和调度责任从手动会话秒仓库中彻底拆出，落成独立 census observation 链。

**Architecture:** 先扩 schema / storage，新增独立 `research_census_second_states` 和 `observation_source_kind`；再把 `ResearchCensusService`、`TargetCensusScheduler`、factory 改成依赖注入的独立链路；最后补上独立 runtime、dataset 过滤和回归测试，确保旧 session-coupled census 只保留审计用途，不再进入 dataset。

**Tech Stack:** Python 3.13、FastAPI、SQLite storage mixins、现有 `fetcher` / `ws_manager`、pytest。

---

## File Structure

- Modify: `backend/app/core/storage_research_platform.py`
- Modify: `backend/app/core/storage_research_platform_dataset.py`
- Modify: `backend/app/core/storage_research_platform_dataset_schema.py`
- Modify: `backend/app/core/research_platform/census/service.py`
- Modify: `backend/app/core/research_platform/census/scheduler.py`
- Modify: `backend/app/core/research_platform/factory.py`
- Modify: `backend/app/core/research_platform/service.py`
- Modify: `backend/app/core/research_platform/dataset/qualified_rows.py`
- Create: `backend/app/core/research_platform/census/observation_reader.py`
- Create: `backend/app/core/research_platform/census/session_activity.py`
- Create: `backend/app/core/research_platform/census/universe.py`
- Create: `backend/app/core/research_platform/census/runtime.py`
- Test: `backend/tests/test_research_platform_storage.py`
- Test: `backend/tests/test_research_platform_census.py`
- Test: `backend/tests/test_research_platform_census_scheduler.py`
- Test: `backend/tests/test_research_platform_factory.py`
- Test: `backend/tests/test_research_platform_dataset_filters.py`
- Regression Test: `backend/tests/test_research_platform_dataset_manifest.py`
- Regression Test: `backend/tests/test_research_platform_api_datasets.py`
- Regression Test: `backend/tests/test_research_platform_api_sessions.py`

### Task 1: 扩 schema / storage，落独立 census observation 仓库

**Files:**
- Modify: `backend/app/core/storage_research_platform.py`
- Modify: `backend/app/core/storage_research_platform_dataset.py`
- Modify: `backend/app/core/storage_research_platform_dataset_schema.py`
- Test: `backend/tests/test_research_platform_storage.py`

- [ ] **Step 1: 先写失败测试，固定新仓库和新 census 字段**

```python
def test_storage_round_trips_independent_census_second_state(storage):
    storage.save_research_census_second_state(
        inst_id='BTC-USDT-SWAP',
        second_bucket=1713000899,
        ts_exchange=1713000899.0,
        ts_local=1713000899.2,
        bid_price=65000.0,
        ask_price=65000.5,
        bid_size=12.0,
        ask_size=10.0,
        bid_depth_10bps=40.0,
        ask_depth_10bps=20.0,
        mid_price=65000.25,
        microprice=65000.23,
        open_price=64999.0,
        high_price=65001.0,
        low_price=64998.5,
        close_price=65000.2,
        mark_price=65000.1,
        index_price=65000.0,
        trade_count=18,
        signed_trade_notional=230000.0,
        buy_notional=150000.0,
        sell_notional=80000.0,
        buy_count=10,
        sell_count=8,
        max_trade_notional=45000.0,
        buy_burst_count=2,
        sell_burst_count=1,
        buy_burst_notional=56000.0,
        sell_burst_notional=18000.0,
        open_interest=3200000.0,
        oi_delta=1200.0,
        funding_rate=0.0001,
        funding_delta=0.0,
        premium=1.5,
        basis_bps=2.1,
        spread_bps=0.08,
        book_level_count=5,
        multi_level_book_imbalance=0.11,
        book_slope=0.03,
        has_trade_input=1,
        has_book_input=1,
        has_state_input=1,
        book_age_seconds=0.0,
        state_age_seconds=0.0,
        clock_skew_ms=12.0,
        is_valid_second=1,
        quality_grade='A',
        invalid_reason='',
        integrity_policy_version='strict_v1',
    )

    rows = storage.list_research_census_second_states_for_inst(
        'BTC-USDT-SWAP',
        end_ts=1713000900,
        lookback_sec=60,
    )

    assert len(rows) == 1
    assert rows[0]['inst_id'] == 'BTC-USDT-SWAP'
    assert storage.list_research_census_inst_ids() == ['BTC-USDT-SWAP']


def test_storage_round_trips_target_census_observation_source_kind(storage):
    storage.save_research_target_census(
        census_id='census-1',
        inst_id='BTC-USDT-SWAP',
        decision_ts=1713000900,
        deployment_eligible=1,
        census_policy_version='deployment_eligible_boundary_census_v1',
        shift_state_definition_version='compact_boundary_state_v1',
        shift_state_blob_json='{}',
        hour_of_day=8,
        day_of_week=1,
        realized_vol_proxy_2h=80.0,
        spread_snapshot_bps=0.08,
        liquidity_snapshot_bin=2,
        funding_regime='neutral',
        session_active_flag=0,
        source_health_flag=1,
        invalid_reason='',
        observation_source_kind='independent_census_runtime_v1',
    )

    row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)

    assert row['observation_source_kind'] == 'independent_census_runtime_v1'
```

- [ ] **Step 2: 运行 storage 测试确认失败**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_storage.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 3: 最小实现独立 census second-state 存储接口和 schema**

```python
CENSUS_SECOND_STATE_COLUMNS = tuple(
    column
    for column in SECOND_STATE_COLUMNS
    if column != 'session_id'
)


def save_research_census_second_state(self, **row: object) -> None:
    placeholders = ', '.join('?' for _ in CENSUS_SECOND_STATE_COLUMNS)
    columns = ', '.join(CENSUS_SECOND_STATE_COLUMNS)
    with self._get_cursor() as cursor:
        cursor.execute(
            f'INSERT OR REPLACE INTO research_census_second_states ({columns}) VALUES ({placeholders})',
            build_values(CENSUS_SECOND_STATE_COLUMNS, row),
        )


def list_research_census_second_states_for_inst(
    self,
    inst_id: str,
    *,
    end_ts: int,
    lookback_sec: int,
) -> list[dict[str, object]]:
    start_ts = int(end_ts) - max(int(lookback_sec or 0), 0)
    with self._get_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM research_census_second_states
            WHERE inst_id = ? AND second_bucket >= ? AND second_bucket < ?
            ORDER BY second_bucket ASC
            """,
            (inst_id, start_ts, int(end_ts)),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: 为 `research_target_census_15m` 增加 `observation_source_kind`**

```python
CENSUS_COLUMNS = (
    'census_id',
    'inst_id',
    'decision_ts',
    'deployment_eligible',
    'census_policy_version',
    'shift_state_definition_version',
    'shift_state_blob_json',
    'hour_of_day',
    'day_of_week',
    'realized_vol_proxy_2h',
    'spread_snapshot_bps',
    'liquidity_snapshot_bin',
    'funding_regime',
    'session_active_flag',
    'source_health_flag',
    'invalid_reason',
    'observation_source_kind',
)
```

- [ ] **Step 5: 运行 storage 测试确认通过**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_storage.py -q
```

Expected:

```text
PASS
```

### Task 2: 收紧 Census Service，只读独立 observation

**Files:**
- Modify: `backend/app/core/research_platform/census/service.py`
- Create: `backend/app/core/research_platform/census/observation_reader.py`
- Create: `backend/app/core/research_platform/census/session_activity.py`
- Test: `backend/tests/test_research_platform_census.py`

- [ ] **Step 1: 先写失败测试，证明 census 不再读取会话秒仓库**

```python
class _FakeObservationReader:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_for_inst(self, inst_id: str, end_ts: int, lookback_sec: int):
        self.calls.append((inst_id, end_ts, lookback_sec))
        return list(self.rows)


class _FakeSessionActivityProvider:
    def __init__(self, active: bool):
        self.active = active
        self.calls = []

    def is_active(self, inst_id: str, decision_ts: int) -> bool:
        self.calls.append((inst_id, decision_ts))
        return self.active


def test_census_service_reads_independent_observation_only(storage):
    service = ResearchCensusService(
        storage=storage,
        observation_reader=_FakeObservationReader([]),
        session_activity_provider=_FakeSessionActivityProvider(active=False),
    )
    storage.save_research_second_state(
        session_id='sess-1',
        inst_id='BTC-USDT-SWAP',
        second_bucket=1713000899,
        ts_exchange=1713000899.0,
        ts_local=1713000899.2,
        bid_price=65000.0,
        ask_price=65000.5,
        bid_size=12.0,
        ask_size=10.0,
        bid_depth_10bps=40.0,
        ask_depth_10bps=20.0,
        mid_price=65000.25,
        microprice=65000.23,
        open_price=64999.0,
        high_price=65001.0,
        low_price=64998.5,
        close_price=65000.2,
        mark_price=65000.1,
        index_price=65000.0,
        trade_count=18,
        signed_trade_notional=230000.0,
        buy_notional=150000.0,
        sell_notional=80000.0,
        buy_count=10,
        sell_count=8,
        max_trade_notional=45000.0,
        buy_burst_count=2,
        sell_burst_count=1,
        buy_burst_notional=56000.0,
        sell_burst_notional=18000.0,
        open_interest=3200000.0,
        oi_delta=1200.0,
        funding_rate=0.0001,
        funding_delta=0.0,
        premium=1.5,
        basis_bps=2.1,
        spread_bps=0.08,
        book_level_count=5,
        multi_level_book_imbalance=0.11,
        book_slope=0.03,
        has_trade_input=1,
        has_book_input=1,
        has_state_input=1,
        book_age_seconds=0.0,
        state_age_seconds=0.0,
        clock_skew_ms=12.0,
        is_valid_second=1,
        quality_grade='A',
        invalid_reason='',
        integrity_policy_version='strict_v1',
    )

    asyncio.run(service.run_once(inst_id='BTC-USDT-SWAP', decision_ts=1713000900))

    row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)
    shift_state = json.loads(row['shift_state_blob_json'])
    assert row['observation_source_kind'] == 'independent_census_runtime_v1'
    assert shift_state['session_active_flag'] == 0
    assert row['deployment_eligible'] == 0


def test_census_service_uses_session_activity_provider_for_session_flag(storage):
    reader = _FakeObservationReader([_build_census_second_row(1713000899)])
    activity = _FakeSessionActivityProvider(active=True)
    service = ResearchCensusService(
        storage=storage,
        observation_reader=reader,
        session_activity_provider=activity,
    )

    asyncio.run(service.run_once(inst_id='BTC-USDT-SWAP', decision_ts=1713000900))

    row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)
    shift_state = json.loads(row['shift_state_blob_json'])
    assert shift_state['session_active_flag'] == 1
    assert activity.calls == [('BTC-USDT-SWAP', 1713000900)]
```

- [ ] **Step 2: 运行 census service 测试确认失败**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_census.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 3: 改造 `ResearchCensusService` 为显式依赖注入**

```python
class ResearchCensusService:
    def __init__(
        self,
        *,
        storage,
        observation_reader,
        session_activity_provider,
    ):
        self._storage = storage
        self._observation_reader = observation_reader
        self._session_activity_provider = session_activity_provider
        self.enabled = True
        self.last_decision_ts = None

    async def run_once(self, *, inst_id: str, decision_ts: int) -> dict[str, object]:
        rows = self._observation_reader.list_for_inst(
            inst_id,
            end_ts=decision_ts,
            lookback_sec=LOOKBACK_SECONDS,
        )
        session_active = self._session_activity_provider.is_active(inst_id, decision_ts)
        shift_state = build_compact_boundary_state_v1(
            rows=rows,
            decision_ts=decision_ts,
            session_active_flag=session_active,
        )
        row = build_target_census_row(
            inst_id=inst_id,
            decision_ts=decision_ts,
            shift_state=shift_state,
            observation_source_kind='independent_census_runtime_v1',
        )
        self._storage.save_research_target_census(**row)
        self.last_decision_ts = int(decision_ts)
        return row
```

- [ ] **Step 4: 把 `build_compact_boundary_state_v1` 改成显式接收 `session_active_flag`**

```python
def build_compact_boundary_state_v1(
    *,
    rows: list[dict[str, object]],
    decision_ts: int,
    session_active_flag: bool,
) -> dict[str, object]:
    policy = _resolve_integrity_policy(rows)
    short_rows = [row for row in rows if int(row['second_bucket']) >= decision_ts - SHORT_WINDOW_SECONDS]
    stale_rows = [row for row in rows if int(row['second_bucket']) >= decision_ts - STALE_WINDOW_SECONDS]
    latest = rows[-1] if rows else None
    latest_close = _get_float(latest, 'close_price')
    short_close = _get_float(short_rows[0], 'close_price') if short_rows else latest_close
    long_close = _get_float(rows[0], 'close_price') if rows else latest_close
    bid_depth = _get_float(latest, 'bid_depth_10bps')
    ask_depth = _get_float(latest, 'ask_depth_10bps')
    depth_total = bid_depth + ask_depth
    funding_countdown_min = _funding_countdown_minutes(decision_ts)
    book_stale_ratio = _stale_ratio(
        stale_rows,
        'book_age_seconds',
        threshold=float(policy['book_stale_threshold_sec']),
    )
    state_stale_ratio = _stale_ratio(
        stale_rows,
        'state_age_seconds',
        threshold=float(policy['state_stale_threshold_sec']),
    )
    source_health_flag = 1 if latest and book_stale_ratio == 0.0 and state_stale_ratio == 0.0 else 0
    return {
        'slot_15m': int((decision_ts % 86400) // SHORT_WINDOW_SECONDS),
        'weekend_flag': 1 if datetime.fromtimestamp(decision_ts, tz=timezone.utc).weekday() >= 5 else 0,
        'ret_15m_bps': _log_return_bps(short_close, latest_close),
        'ret_2h_bps': _log_return_bps(long_close, latest_close),
        'rv_15m_bps': _realized_vol_bps(short_rows),
        'rv_2h_bps': _realized_vol_bps(rows),
        'range_15m_bps': _range_bps(short_rows),
        'range_2h_bps': _range_bps(rows),
        'spread_last_bps': _get_float(latest, 'spread_bps'),
        'spread_median_60s_bps': _median([_get_float(row, 'spread_bps') for row in stale_rows]),
        'depth_10bps_log': math.log1p(max(depth_total, 0.0)),
        'imbalance_10bps': _resolve_depth_imbalance(bid_depth=bid_depth, ask_depth=ask_depth),
        'trade_count_60s': int(sum(_get_float(row, 'trade_count') for row in stale_rows)),
        'trade_notional_60s_log': math.log1p(sum(abs(_get_float(row, 'signed_trade_notional')) for row in stale_rows)),
        'funding_countdown_min': funding_countdown_min,
        'near_funding_flag': 1 if funding_countdown_min <= NEAR_FUNDING_MINUTES else 0,
        'book_stale_ratio_60s': book_stale_ratio,
        'state_stale_ratio_60s': state_stale_ratio,
        'source_health_flag': source_health_flag,
        'session_active_flag': 1 if session_active_flag else 0,
    }
```

- [ ] **Step 5: 运行 census service 测试确认通过**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_census.py -q
```

Expected:

```text
PASS
```

### Task 3: 收紧 Scheduler / Factory，使用独立 census universe

**Files:**
- Modify: `backend/app/core/research_platform/census/scheduler.py`
- Modify: `backend/app/core/research_platform/factory.py`
- Modify: `backend/app/core/research_platform/service.py`
- Create: `backend/app/core/research_platform/census/universe.py`
- Test: `backend/tests/test_research_platform_census_scheduler.py`
- Test: `backend/tests/test_research_platform_factory.py`

- [ ] **Step 1: 先写失败测试，证明 scheduler 与 factory 不再读取会话秒仓库**

```python
def test_scheduler_uses_explicit_universe_provider():
    scheduler = TargetCensusScheduler(
        census_service=_FakeCensusService(),
        inst_id_provider=lambda: ['BTC-USDT-SWAP'],
        now_fn=lambda: 1801.2,
    )

    result = asyncio.run(scheduler.run_due_once())

    assert [(row['inst_id'], row['decision_ts']) for row in result] == [
        ('BTC-USDT-SWAP', 1800),
    ]


def test_target_census_instrument_listing_reads_independent_universe_not_second_state_storage(storage):
    provider = factory._build_census_universe_provider(storage, cfg=SimpleNamespace(census_universe=('BTC-USDT-SWAP',)))
    assert provider.list_inst_ids() == ['BTC-USDT-SWAP']
```

- [ ] **Step 2: 运行 scheduler / factory 测试确认失败**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_census_scheduler.py backend/tests/test_research_platform_factory.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 3: 实现独立 universe provider，并接入 factory**

```python
class StaticCensusUniverseProvider:
    def __init__(self, *, inst_ids: list[str]):
        self._inst_ids = list(dict.fromkeys(str(inst_id).strip() for inst_id in inst_ids if str(inst_id).strip()))

    def list_inst_ids(self) -> list[str]:
        return list(self._inst_ids)


def _build_census_universe_provider(storage, *, cfg):
    return StaticCensusUniverseProvider(
        inst_ids=list(getattr(cfg, 'census_universe', ()) or ()),
    )
```

- [ ] **Step 4: 在 service 状态中暴露 universe_count**

```python
def get_census_status(self) -> dict[str, object]:
    return {
        'enabled': self._census.enabled,
        'last_decision_ts': self._census.last_decision_ts,
        'census_policy_version': RESEARCH_PROTOCOL_LOCKS['census_policy_version_v1'],
        'shift_state_definition_version': RESEARCH_PROTOCOL_LOCKS['shift_state_definition_version_v1'],
        'universe_count': len(self._census.inst_ids()),
    }
```

- [ ] **Step 5: 运行 scheduler / factory 测试确认通过**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_census_scheduler.py backend/tests/test_research_platform_factory.py -q
```

Expected:

```text
PASS
```

### Task 4: 新增独立 Census Observation Runtime

**Files:**
- Create: `backend/app/core/research_platform/census/runtime.py`
- Modify: `backend/app/core/research_platform/factory.py`
- Test: `backend/tests/test_research_platform_census.py`

- [ ] **Step 1: 先写失败测试，固定 runtime 只写独立 observation 仓库**

```python
def test_census_observation_runtime_writes_independent_second_states(storage):
    runtime = CensusObservationRuntime(
        storage=storage,
        inst_id='BTC-USDT-SWAP',
        snapshot_reader=lambda: {
            'inst_id': 'BTC-USDT-SWAP',
            'second_bucket': 1713000899,
            'ts_exchange': 1713000899.0,
            'ts_local': 1713000899.2,
            'bid_price': 65000.0,
            'ask_price': 65000.5,
            'bid_size': 12.0,
            'ask_size': 10.0,
            'bid_depth_10bps': 40.0,
            'ask_depth_10bps': 20.0,
            'mid_price': 65000.25,
            'microprice': 65000.23,
            'open_price': 64999.0,
            'high_price': 65001.0,
            'low_price': 64998.5,
            'close_price': 65000.2,
            'mark_price': 65000.1,
            'index_price': 65000.0,
            'trade_count': 18,
            'signed_trade_notional': 230000.0,
            'buy_notional': 150000.0,
            'sell_notional': 80000.0,
            'buy_count': 10,
            'sell_count': 8,
            'max_trade_notional': 45000.0,
            'buy_burst_count': 2,
            'sell_burst_count': 1,
            'buy_burst_notional': 56000.0,
            'sell_burst_notional': 18000.0,
            'open_interest': 3200000.0,
            'oi_delta': 1200.0,
            'funding_rate': 0.0001,
            'funding_delta': 0.0,
            'premium': 1.5,
            'basis_bps': 2.1,
            'spread_bps': 0.08,
            'book_level_count': 5,
            'multi_level_book_imbalance': 0.11,
            'book_slope': 0.03,
            'has_trade_input': 1,
            'has_book_input': 1,
            'has_state_input': 1,
            'book_age_seconds': 0.0,
            'state_age_seconds': 0.0,
            'clock_skew_ms': 12.0,
            'is_valid_second': 1,
            'quality_grade': 'A',
            'invalid_reason': '',
            'integrity_policy_version': 'strict_v1',
        },
    )

    runtime.flush_once()

    rows = storage.list_research_census_second_states_for_inst(
        'BTC-USDT-SWAP',
        end_ts=1713000900,
        lookback_sec=5,
    )
    assert len(rows) == 1
    assert storage.list_research_second_states('sess-1', limit=10) == []
```

- [ ] **Step 2: 运行 runtime 测试确认失败**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_census.py -q -k census_observation_runtime
```

Expected:

```text
FAIL
```

- [ ] **Step 3: 最小实现独立 runtime**

```python
class CensusObservationRuntime:
    def __init__(self, *, storage, inst_id: str, snapshot_reader):
        self._storage = storage
        self._inst_id = inst_id
        self._snapshot_reader = snapshot_reader

    def flush_once(self) -> dict[str, object]:
        row = dict(self._snapshot_reader())
        row['inst_id'] = self._inst_id
        self._storage.save_research_census_second_state(**row)
        return row
```

- [ ] **Step 4: 运行 runtime 测试确认通过**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_census.py -q -k census_observation_runtime
```

Expected:

```text
PASS
```

### Task 5: 收紧 Dataset 读取，只消费独立来源 census

**Files:**
- Modify: `backend/app/core/research_platform/dataset/qualified_rows.py`
- Test: `backend/tests/test_research_platform_dataset_filters.py`

- [ ] **Step 1: 先写失败测试，证明 dataset 会过滤 legacy census**

```python
def test_dataset_manifest_ignores_legacy_session_coupled_census(storage):
    _save_census(storage, DEFAULT_DECISION_TS, 0, shift_gap=False)
    row = storage.get_research_target_census(DEFAULT_INST_ID, DEFAULT_DECISION_TS)
    storage.save_research_target_census(
        **{
            **row,
            'observation_source_kind': 'legacy_session_coupled_v0',
        }
    )

    manifest = service.create_dataset_manifest(build_manifest_payload())

    assert manifest['target_census_count'] == 0
    assert manifest['dataset_status'] == 'research_only'
```

- [ ] **Step 2: 运行 dataset 过滤测试确认失败**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_dataset_filters.py -q
```

Expected:

```text
FAIL
```

- [ ] **Step 3: 最小实现 census 来源过滤**

```python
def _census_row_matches_protocol(
    census_row: dict[str, object],
    *,
    protocol_bundle: dict[str, object],
) -> bool:
    return (
        int(census_row['deployment_eligible']) == 1
        and str(census_row['census_policy_version']) == str(protocol_bundle['target_census_policy_version'])
        and str(census_row['shift_state_definition_version']) == str(protocol_bundle['shift_state_definition_version'])
        and str(census_row.get('observation_source_kind', 'legacy_session_coupled_v0'))
        == 'independent_census_runtime_v1'
    )
```

- [ ] **Step 4: 运行 dataset 过滤测试确认通过**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_dataset_filters.py -q
```

Expected:

```text
PASS
```

### Task 6: 全链路回归，确认协议显式降级而非静默 fallback

**Files:**
- Regression Test: `backend/tests/test_research_platform_dataset_manifest.py`
- Regression Test: `backend/tests/test_research_platform_api_datasets.py`
- Regression Test: `backend/tests/test_research_platform_api_sessions.py`
- Regression Test: `backend/tests/test_research_platform_propensity.py`
- Regression Test: `backend/tests/test_research_platform_training_run.py`

- [ ] **Step 1: 跑 dataset / API 回归**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest \
  backend/tests/test_research_platform_dataset_manifest.py \
  backend/tests/test_research_platform_api_datasets.py \
  backend/tests/test_research_platform_api_sessions.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 2: 跑 weighting / propensity / training 关键回归**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest \
  backend/tests/test_research_platform_dataset_filters.py \
  backend/tests/test_research_platform_propensity.py \
  backend/tests/test_research_platform_training_run.py -q
```

Expected:

```text
PASS or timeout only on unrelated heavy tests
```

- [ ] **Step 3: 如 `training_run.py` 全文件超时，拆关键用例回归**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_training_run.py -q -k 'rejects_dataset_without_complete_inner_validation_folds'
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_training_run.py -q -k 'split_artifact_uses_dataset_qualified_rows_only'
timeout 60s env PYTHONPATH=backend python3 -m pytest backend/tests/test_research_platform_training_run.py -q -k 'materializes_run_local_refs_and_origin_evaluation'
```

Expected:

```text
PASS
```

- [ ] **Step 4: 最终核对完成标准**

检查：

- `ResearchCensusService` 不再读取 `research_second_states`
- `TargetCensusScheduler` 不再通过 second-state 仓库推断 universe
- `target_census_15m` 新行带 `observation_source_kind = 'independent_census_runtime_v1'`
- dataset 不读取 `legacy_session_coupled_v0`
- 没有独立 census 时系统显式降级，不做静默 fallback
