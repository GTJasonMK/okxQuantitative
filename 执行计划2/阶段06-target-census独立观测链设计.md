# 阶段06：Target Census 独立观测链设计

## 1. 目标

把 `target_census_15m` 从“依赖手动会话秒仓库的派生层”收紧成“独立于手动会话采集的 deployment census 层”，满足 [模型训练构思.txt](/mnt/e/code/okxquantitative/模型训练构思.txt) 对 `P_*` 观测层的要求：

- `target_census_15m` 必须独立于手动会话式秒级采集
- 它必须覆盖声明的 census universe，而不是只覆盖有人点击开始采集的时段
- 它只负责 `P_*` 的边界普查，不负责训练样本产出
- `shift_state` 必须仍然基于 `[t-7200, t)` 的因果窗口构造

本阶段不改动训练协议字段，不改动 `dataset_manifest`、`shift diagnostics`、`weighting`、`rolling-origin` 的上层口径；只替换 `target_census_15m` 的底层观测来源与调度责任。

## 2. 当前冲突

当前实现存在两个根本耦合点：

1. `ResearchCensusService.run_once()` 直接从 `research_second_states` 读取 `[t-7200, t)` 窗口。
2. `TargetCensusScheduler` 的 `inst_id_provider` 通过 `storage.list_research_second_state_inst_ids()` 反推 universe。

这意味着：

- 没有会话采集，就没有 census observation
- census universe 由“谁采过会话数据”隐式决定
- `target_census_15m` 不是 deployment census，而是 session-coupled census

这是与冻结文档冲突的真实根因。

## 3. 采用方案

采用严格版方案：

- 新增独立 `research_census_second_states` 仓库
- 新增独立 `CensusObservationRuntime`
- 新增独立 `census_universe_provider`
- `ResearchCensusService` 只读独立 census observation 仓库
- `session_active_flag` 通过独立 provider 注入，不再由 observation 仓库是否有行来暗推

不采用以下方案：

- 不复用 `research_second_states` 加 `source_kind` 打补丁
- 不做“每个 15m 边界临时拉一次快照”的弱化实现

原因：

- 前者仍然把会话训练层和 `P_*` 观测层耦合在同一秒仓库里
- 后者无法严格恢复 `compact_boundary_state_v1` 所需的 7200 秒滚动统计

## 4. 目标架构

### 4.1 新的分层

系统分成三条彼此解耦的链路：

1. 会话采集链

- 输入：手动启动/停止的 collection session
- 秒仓库：`research_second_states`
- 用途：构造监督样本、样本索引、标签、训练数据集

2. census observation 链

- 输入：独立 census universe
- 秒仓库：`research_census_second_states`
- 用途：为每个 15m 边界提供 `[t-7200, t)` 的因果 observation window

3. target census 链

- 输入：`research_census_second_states` 上的 observation window
- 输出：`research_target_census_15m`
- 用途：定义 `P_*` 的 deployment census、shift diagnostics、weighting target

### 4.2 运行责任

- `CensusObservationRuntime` 持续按 1s 写入 `research_census_second_states`
- `TargetCensusScheduler` 仅在 15m 边界触发 `ResearchCensusService.run_once(inst_id, decision_ts)`
- `ResearchCensusService` 只做“从独立 observation 计算 `shift_state` 并写入 `target_census_15m`”
- `BoundaryMaterializer` 继续只服务会话采集链，不与 census observation 链共享职责

## 5. 数据模型

### 5.1 新表：`research_census_second_states`

新增一张独立表：

- 表名：`research_census_second_states`
- 主用途：保存 census 专用的 1s causal state

字段要求：

- 除 `session_id` 外，与 `research_second_states` 的市场状态字段保持同构
- 不包含 `session_id` 字段
- 主键不再表达任何会话生命周期，只表达 `(inst_id, second_bucket)` 上的独立 census observation

因此本阶段要求：

- 新表字段与 `research_second_states` 的市场状态字段同构
- 主键使用 `(inst_id, second_bucket)`
- 不允许通过 `session_id` 查询该表

存储接口新增：

- `save_research_census_second_state(**row)`
- `list_research_census_second_states_for_inst(inst_id, end_ts, lookback_sec)`
- `list_research_census_inst_ids()`

### 5.2 现有表：`research_target_census_15m`

新增字段：

- `observation_source_kind`

合法值第一阶段固定为：

- `independent_census_runtime_v1`
- `legacy_session_coupled_v0`

作用：

- 保留历史审计
- 阻止旧的 session-coupled census 行被继续误用

数据集读取规则收紧为：

- 只允许读取 `observation_source_kind == 'independent_census_runtime_v1'` 的 census 行

如果没有符合条件的 census 行：

- `target_census_count = 0`
- `dataset_status` 至多为 `research_only`

不允许静默回退去读 `legacy_session_coupled_v0`。

## 6. 关键服务接口

### 6.1 `ResearchCensusService`

改成显式依赖注入：

```python
class ResearchCensusService:
    def __init__(
        self,
        *,
        storage,
        observation_reader,
        session_activity_provider,
    ): ...
```

依赖契约：

- `observation_reader.list_for_inst(inst_id, end_ts, lookback_sec) -> list[dict[str, object]]`
- `session_activity_provider.is_active(inst_id, decision_ts) -> bool`

`run_once()` 的严格要求：

1. 只能读 `observation_reader`
2. 不能读 `research_second_states`
3. 不能根据 observation 有无来判断 `session_active_flag`
4. `shift_state['session_active_flag']` 必须来自 `session_activity_provider`
5. 写 `target_census_15m` 时必须带上：
   - `observation_source_kind = 'independent_census_runtime_v1'`

### 6.2 `TargetCensusScheduler`

改成依赖独立 universe：

```python
TargetCensusScheduler(
    census_service=...,
    inst_id_provider=census_universe_provider.list_inst_ids,
)
```

严格要求：

- 不允许再从任何 second-state 仓库反推 universe
- universe 为空时返回空结果
- `get_census_status()` 必须能暴露：
  - `enabled`
  - `last_decision_ts`
  - `census_policy_version`
  - `shift_state_definition_version`
  - `universe_count`

### 6.3 `CensusObservationRuntime`

新增独立 runtime：

- 作用：持续采集 census universe 对应合约的 1s observation
- 不创建 research session
- 不写 `research_second_states`
- 不触发 `BoundaryMaterializer`

输入源：

- `fetcher`：mark/index/open_interest/funding
- `ws_manager`：book/trade 快照

输出：

- `research_census_second_states`

### 6.4 `census_universe_provider`

单独定义 census universe，不复用 `TREND_RESEARCH_WHITELIST`。

原因：

- `TREND_RESEARCH_WHITELIST` 属于趋势研究服务/模型侧配置
- census universe 属于 deployment target declaration
- 两者职责不同，不能隐式绑定

第一阶段接口：

- `list_inst_ids() -> list[str]`

来源可以是：

- 独立配置项
- 独立用户偏好项

但必须与 trend research whitelist 分开存储。

## 7. `session_active_flag` 的定义

`session_active_flag` 仍然保留在 `compact_boundary_state_v1` 中，但语义改成：

- 该 `inst_id` 在 `decision_ts` 这个 15m 边界时刻是否存在手动采集会话覆盖

它的来源必须是单独的 `session_activity_provider`：

- 输入：`inst_id`, `decision_ts`
- 输出：布尔值

禁止做法：

- 看到 census observation 有最近 60 秒行就认为 session active
- 看到 `research_second_states` 里有数据就默认 `session_active_flag = 1`

因为这会把 `P_*` 观测链和会话链再次耦合。

## 8. 工厂装配

`research_platform.factory` 需要重构装配方式：

### 8.1 当前错误装配

```python
TargetCensusScheduler(
    census_service=ResearchCensusService(storage=storage),
    inst_id_provider=lambda: storage.list_research_second_state_inst_ids(),
)
```

### 8.2 目标装配

```python
TargetCensusScheduler(
    census_service=ResearchCensusService(
        storage=storage,
        observation_reader=...,
        session_activity_provider=...,
    ),
    inst_id_provider=census_universe_provider.list_inst_ids,
)
```

并新增独立的：

- `CensusObservationRuntime`
- `census_universe_provider`

## 9. 测试策略

### 9.1 新失败测试

必须先补下面几类测试：

1. `ResearchCensusService` 只读独立 observation

- `research_second_states` 有完整窗口
- `research_census_second_states` 为空
- `run_once()` 不得产出合格 census

2. `session_active_flag` 来自 injected provider

- 即使 census observation 完整
- 只要 provider 返回 `False`
- 最终 `shift_state['session_active_flag'] == 0`

3. `TargetCensusScheduler` 使用独立 universe

- 不再读取 `list_research_second_state_inst_ids()`
- universe 为空时返回空列表

4. storage 新接口 round-trip

- `save_research_census_second_state`
- `list_research_census_second_states_for_inst`
- `list_research_census_inst_ids`

5. dataset 过滤旧 census 来源

- `target_census_15m` 里同时有 `legacy_session_coupled_v0` 和 `independent_census_runtime_v1`
- 数据集只统计后者

### 9.2 必做回归

- `test_research_platform_dataset_manifest.py`
- `test_research_platform_dataset_filters.py`
- `test_research_platform_propensity.py`
- `test_research_platform_training_run.py`
- `test_research_platform_api_datasets.py`
- `test_research_platform_api_sessions.py`

## 10. 迁移策略

### 10.1 schema 迁移

新增：

- `research_census_second_states`

修改：

- `research_target_census_15m` 增加 `observation_source_kind TEXT NOT NULL DEFAULT 'legacy_session_coupled_v0'`

### 10.2 历史数据处理

已有 `research_target_census_15m` 行一律视为：

- `observation_source_kind = 'legacy_session_coupled_v0'`

不做任何自动升级：

- 不把历史旧行改标成独立 census
- 不做 silent backfill
- 不把旧 observation 仓库复制成新 observation 仓库

原因：

- 旧数据的观测拓扑已经是 session-coupled
- 把旧行伪装成新独立行会破坏审计性

### 10.3 dataset 行为

当系统尚未积累新的独立 census 数据时：

- `target_census_count` 可能为 0
- `support_overlap` / `shift diagnostics` 可能退化
- `dataset_status` 必须显式降级

这不是 bug，而是协议收紧后的正确暴露。

## 11. 实现边界

本阶段只解决以下冲突：

1. census observation 仓库独立
2. census universe 独立
3. census scheduler 不再由会话秒仓库驱动
4. `target_census_15m` 显式区分独立来源和历史耦合来源

本阶段不做：

1. census universe 前端管理页面
2. 更丰富的 deployment target 多 universe 方案
3. 改写 `compact_boundary_state_v1` 字段定义
4. 改写 dataset / weighting / training 的上层协议名

## 12. 完成标准

满足以下条件才算完成：

1. `ResearchCensusService` 不再读取 `research_second_states`
2. `TargetCensusScheduler` 不再通过 second-state 仓库推断 universe
3. `target_census_15m` 新写入行都带 `observation_source_kind = 'independent_census_runtime_v1'`
4. dataset 只消费独立来源 census
5. 没有独立 census 时系统明确降级，不做静默 fallback
6. 相关单元测试与回归测试通过
