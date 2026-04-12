# OKX 官方规则级限流与出站时间线监控设计

## 背景

当前项目已经有基础缓存、共享 WebSocket 和一个全局 API 限流器，但它仍然不是 OKX 官方规则级别的精确限流。

现状问题：

- 限流规则被简化成单一的 `3000/min` 全局窗口，无法表达 OKX 的真实规则。
- OKX 限流维度并不统一，存在 `IP`、`User ID`、`User ID + Instrument ID`、连接级小时配额等不同口径。
- 现有限流主要覆盖公共行情 REST，账户、交易、WebSocket 控制动作没有统一接入。
- 设置页当前只显示分钟计数、剩余配额和总调用，不适合定位具体的出站行为。

本次改造目标是把后端对 OKX 的所有实际出站调用统一纳入官方规则级调度，并在设置页提供近 10 分钟的实际出站时间线监控。

## 目标

- 对后端所有发往 OKX 的真实出站动作实施精确限流。
- 限流规则表达能力覆盖本项目实际使用到的 OKX 官方规则。
- 所有规则在“真正发出请求前”生效，而不是事后统计。
- 设置页用“实际出站时间线图”替代原有 API 调用计数指标。
- 时间线只记录“实际发往 OKX 的调用事件”，不记录等待、排队、预占位。

## 非目标

- 不实现前端到后端的 API 时间线。
- 不实现时间线落库或审计归档，先采用内存环形缓冲。
- 不引入 silent fallback、mock success 或静默降级。
- 不试图覆盖 OKX 文档中本项目完全未使用的所有接口规则。

## 后端架构

新增统一的 OKX 出站控制层，拆成三个组件：

1. `OKXRateRuleRegistry`
   - 维护操作键到官方规则的映射。
   - 规则包含窗口长度、窗口容量、限流维度、显示分类。
   - 典型操作键包括：
     - `market.ticker`
     - `market.tickers`
     - `market.books`
     - `market.books_full`
     - `market.candles`
     - `market.history_candles`
     - `market.trades`
     - `account.balance`
     - `account.positions`
     - `trade.orders_pending`
     - `trade.orders_history`
     - `trade.fills`
     - `trade.place_order`
     - `trade.cancel_order`
     - `ws.connect`
     - `ws.login`
     - `ws.subscribe`
     - `ws.unsubscribe`

2. `OKXOutboundGovernor`
   - 基于滑动窗口做精确调度。
   - 支持不同 scope key：
     - `public_ip`
     - `private_user:<mode>`
     - `trade_user_inst:<mode>:<inst_id>`
     - `ws_connect_ip`
     - `ws_conn_ops:<manager_id>`
   - 对请求的行为是：
     - 能立即发则放行。
     - 不能立即发则等待到最早合法时刻。
     - 超过最大等待时间则显式抛错。
   - 不记录“等待事件”，只在真正放行时触发出站记录。

3. `OKXOutboundTimelineStore`
   - 使用内存环形缓冲保存最近一段时间的实际出站事件。
   - 事件字段：
     - `ts`
     - `op_key`
     - `channel`
     - `target_group`
     - `rule_key`
     - `scope_key`
     - `inst_id`
     - `mode`
     - `result`
     - `latency_ms`
   - 只由 governor 在“请求实际发出”时写入。

## 接入范围

所有真实对 OKX 出站的后端路径都要收口到统一控制层：

- `DataFetcher`
  - `get_ticker`
  - `get_tickers`
  - `get_candles`
  - `get_history_candles`
  - `get_recent_trades`
  - `get_orderbook`
  - `get_instruments`
- `OKXAccount`
  - `get_balance`
  - `get_positions`
  - `get_contract_positions`
  - 其他直接访问私有账户 REST 的方法
- `OKXTrader`
  - `place_order`
  - `cancel_order`
  - `get_pending_orders`
  - `get_order_history`
  - `get_fills`
- `OKXWebSocketManager`
  - `start` 中公共/Business 建连
  - `start_private` 中私有建连与登录
  - `subscribe_tickers`
  - `unsubscribe_tickers`
  - `subscribe_candles`
  - `unsubscribe_candles`
  - 私有频道订阅

业务层不再自行维护限流判断，只声明这次操作对应的 `op_key`、`mode`、`inst_id`、连接标识等上下文。

## 规则精度

规则以本项目实际使用的 OKX 官方限制为准，并按不同维度分桶：

- 公共行情 REST：按 `IP`
- 私有账户/查询 REST：按 `User ID`
- 下单/撤单：按 `User ID + Instrument ID`
- WebSocket 建连：按 `IP`
- WebSocket `login/subscribe/unsubscribe`：按连接级小时窗口

`books` 与 `books-full` 必须分开建规则键，因为官方上限不同。

历史 K 线同步不能继续依赖粗粒度“每分钟总额”估算，而是必须按真实分页发送次数逐次通过 governor 放行。

## 错误处理

- governor 超时拿不到合法发送时机：显式抛错。
- OKX 返回官方限流错误，例如 `50011`、`50061`：原样暴露为上游失败，不伪装为空结果。
- 时间线事件会记录 `result=error`，但只有在请求已经实际发出后才记录。

## 监控 API

新增只读接口：

- `GET /api/system/okx-outbound-timeline`

请求参数：

- `window_seconds`，默认 `600`
- `limit`，限制返回事件数，避免 UI 拉取过大快照

响应包含：

- `window_seconds`
- `generated_at`
- `events`
- `summary`
  - `event_count`
  - `error_count`
  - `top_operations`
  - `slowest_operations`

现有 `/status` 中的旧 `rate_limit` 统计保留兼容一版，但设置页不再使用它作为主监控视图。

## 前端设置页改造

设置页 `monitor` 标签中，原“API 调用”卡片替换为：

- 一张近 10 分钟的 OKX 出站时间线图
- 一组轻量摘要

图表形态采用多泳道时间线：

- 公共 REST
- 私有 REST
- 交易 REST
- WebSocket 控制

每个实际出站事件显示为一个点：

- 颜色区分 `ok/error`
- 纵向按泳道分组
- 横向按时间展开

hover 信息包括：

- 时间
- 操作键
- 接口分类
- `inst_id`
- `mode`
- `scope_key`
- 结果
- 耗时

默认窗口为近 10 分钟，前端每 2 秒轮询一次后端快照。该视图不引入新的监控 WebSocket。

## 测试策略

测试分三层：

1. 规则层
   - 不同操作映射到正确的窗口、容量和 scope 维度。
   - 相同时间窗口内超过官方额度时必须等待或超时报错。

2. 接入层
   - `DataFetcher`、`OKXAccount`、`OKXTrader`、`OKXWebSocketManager` 的真实出站点必须先经过 governor，再执行底层 SDK 调用。
   - `books-full`、历史 K 线分页、下单/撤单、WS 订阅等关键路径都有回归测试。

3. 时间线层
   - 只记录“实际发出”的事件。
   - 等待、排队、预检查不会写入时间线。
   - 错误请求在已实际发出时要记录 `error` 事件。

## 风险与约束

- 本次改造会触及多个核心出站点，必须保持边改边验证，避免出现“部分路径绕过 governor”的旁路。
- 由于用户明确不允许修改环境，验证以现有可执行的静态校验和本地可用测试工具为准；若当前环境缺失 `pytest`，不能通过安装依赖来补齐。
- 当前仓库工作树较脏，实施时只能精确修改本次涉及文件，不能回滚无关改动。
