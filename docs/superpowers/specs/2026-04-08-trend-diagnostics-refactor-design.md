# 趋势研究过程诊断重构设计

## 目标

把“分析中心 > 趋势研究 > 过程诊断”从当前的共享大 payload 子视图，重构为一个独立的诊断子系统。重构后的过程诊断采用“单合约优先、链路健康优先、诊断时间线优先”的结构，后端提供独立读模型与独立实时通道，前端使用独立状态层与独立组件树，不再与训练状态、因子分析、推断结果表共用同一份视图状态。

本次重构的目标不是补几个字段或继续修刷新 bug，而是清理当前架构中的职责缠绕、协议混杂、页面冗余和调试体验失真。

## 当前架构问题

### 1. 后端职责混杂

- 趋势研究服务 [`service.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/service.py) 同时承担运行编排、周期任务、输入订阅、运行错误、训练状态和前端推送职责，已经明显超出单一职责边界。
- 诊断快照构建 [`process_view.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/process_view.py) 混入了展示层格式化，导致“运行事实”和“页面渲染模型”没有分层。
- 实时载荷拼装 [`realtime.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/realtime.py) 把推断结果、训练状态、过程诊断一次性塞进同一个 `trend_research` 大对象，协议耦合过重。
- WebSocket API 层 [`websocket.py`](/mnt/e/code/okxquantitative/backend/app/api/websocket.py) 直接理解趋势研究业务推送，导致市场 WS 网关和趋势研究业务边界不清。

### 2. 前端状态边界混杂

- 共享状态入口 [`useTrendResearchWorkspace.mjs`](/mnt/e/code/okxquantitative/frontend/src/renderer/components/analytics/useTrendResearchWorkspace.mjs) 同时管理共享加载、WS 订阅、合约选择、训练态、过程诊断态和错误挡板，已经变成趋势研究万能状态总线。
- 过程诊断组件 [`TrendResearchProcessDiagnostics.vue`](/mnt/e/code/okxquantitative/frontend/src/renderer/components/analytics/TrendResearchProcessDiagnostics.vue) 直接消费整坨 `recentProcess`，没有自己的 transport、读模型和组件边界。
- 过程诊断与训练页、因子页共享刷新节奏，导致一个子页的数据变化会触发其他子页的整块重算。

### 3. 页面结构不适合排障

- 当前过程诊断把“概览卡片、所有合约卡片、最新推断、特征窗口”平铺在一起，既不是单合约优先，也没有明确的主次层级。
- 用户排查“为什么不刷新”时，需要在大量数字中自行推断链路卡点，而不是直接看到 trade/book/state/feature/inference 的断点时间线。
- 过程诊断中存在大量与其他子页重复的信息，例如趋势结果摘要、特征统计和次级运行数字，冗余高且干扰主任务。

### 4. 协议不利于演进

- 当前采用一个共享 `trend_research` 大 payload，全量快照反复覆盖，无法按功能模块做独立演进。
- 过程诊断缺乏独立订阅通道，无法按选中合约缩小推送范围，也无法独立定义首帧与增量事件。

## 范围确认

本次重构只覆盖“过程诊断”子页面，不重构趋势研究的训练、因子、结论总览页面本身，但会调整趋势研究壳层以容纳独立诊断工作流。

明确纳入范围：

- 新增独立 `trend_diagnostics` REST 首帧接口
- 新增独立 `trend_diagnostics` WebSocket 通道
- 过程诊断使用独立读模型与独立事件类型
- 过程诊断页面改为单合约工作台
- 主视图以链路健康概览为主
- 第二主视图为诊断时间线
- 删除与诊断目的无关的冗余信息块

明确不纳入范围：

- 不重写趋势研究推断算法
- 不修改因子分析页面的图表逻辑
- 不把所有趋势研究实时通道都拆成事件流
- 不引入新的前端全局 store 框架

## 设计原则

- 过程诊断必须有独立读模型，不能再复用趋势研究全量 payload 的子集。
- 运行事实、读模型投影、实时协议、页面渲染必须分层。
- 前端只消费诊断需要的最小数据，不再接收训练、因子、推断表等无关字段。
- 单合约优先，默认视角服务于“当前这个合约为什么卡住或停更”的排查任务。
- 错误必须显式暴露，不做静默回退，不用大面积挡板覆盖已有诊断内容。

## 后端架构

### 1. 运行层：`TrendResearchRuntime`

新增运行层模块，承接当前趋势研究服务中的实时采集与推断职责：

- 订阅 `trades` / `books`
- 同步 contract state
- 生成 1 秒特征条
- 生成 inference 快照
- 推送内部运行事件

运行层只负责产生事实，不负责拼装过程诊断页面模型。

建议拆分后由原 [`service.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/service.py) 保留外部协调入口，核心运行逻辑迁移到：

- `backend/app/core/trend_research/runtime_service.py`

### 2. 诊断投影层：`TrendDiagnosticsProjector`

新增诊断投影器，专门把运行事实投影为“过程诊断读模型”。

建议文件：

- `backend/app/core/trend_research/diagnostics_models.py`
- `backend/app/core/trend_research/diagnostics_projector.py`
- `backend/app/core/trend_research/diagnostics_realtime.py`

职责：

- 维护全局摘要
- 维护单合约诊断快照
- 维护单合约时间线窗口
- 根据内部运行事件产出诊断增量事件
- 提供 REST 首帧所需完整快照

### 3. 诊断读模型

单合约诊断快照采用固定三段结构：

- `global_health`
  - 白名单数量
  - 活跃合约数量
  - 停滞合约数量
  - 异常合约数量
  - 最近系统事件时间
- `instrument_health`
  - `inst_id`
  - `pipeline_stage`
  - `trade_age_seconds`
  - `book_age_seconds`
  - `state_age_seconds`
  - `last_feature_at`
  - `last_inference_at`
  - `is_stale`
  - `is_error`
  - `current_error`
  - `last_event_at`
- `timeline`
  - 最近 N 个时间片段
  - 每个片段标记 `trade/book/state/feature/inference/error/recovery`
- `details`
  - 最近特征条桶时间
  - 最近推断桶时间
  - 少量运行计数器
  - 订阅状态

这里有意不包含训练运行态、因子摘要、结果表格行，避免诊断模型再次膨胀为共享大对象。

### 4. 诊断事件模型

新增独立实时事件类型，挂在 `trend_diagnostics` 通道下：

- `snapshot`
  - 首帧或重连恢复时发送完整诊断快照
- `health_changed`
  - 单合约健康状态变化
- `timeline_appended`
  - 追加时间线片段
- `feature_emitted`
  - 生成新特征条
- `inference_emitted`
  - 生成新推断
- `runtime_error_changed`
  - 当前异常变化

所有事件都必须带：

- `inst_id`
- `event_type`
- `emitted_at`
- `sequence`

其中 `sequence` 用于前端确保事件顺序可观察，`emitted_at` 用于可视化“最近一次诊断推送时间”。

### 5. API 与 WebSocket 边界

新增独立 REST：

- `GET /api/trend-research/diagnostics`

参数：

- `inst_id`
- `timeline_limit`

返回：

- `selected_inst_id`
- `instruments`
- `global_health`
- `instrument_health`
- `timeline`
- `details`

新增独立 WS 通道：

- `trend_diagnostics`

订阅语义：

- 前端订阅时传入 `inst_id`
- 后端先回一条 `snapshot`
- 后续只推该合约详细诊断事件
- 同时携带轻量 `instruments` 状态摘要，供顶部合约切换条更新

WebSocket API 层 [`websocket.py`](/mnt/e/code/okxquantitative/backend/app/api/websocket.py) 只负责：

- 接受 `trend_diagnostics` 订阅/取消订阅
- 调用诊断广播器
- 转发诊断事件

它不再自行构造诊断业务 payload。

## 前端架构

### 1. 独立诊断状态层

新增：

- `frontend/src/renderer/components/analytics/useTrendDiagnosticsWorkspace.mjs`

职责：

- 初始 `diagnostics snapshot` 加载
- `trend_diagnostics` 独立订阅
- 当前合约切换
- 诊断事件局部更新
- 页面错误与连接态管理

原 [`useTrendResearchWorkspace.mjs`](/mnt/e/code/okxquantitative/frontend/src/renderer/components/analytics/useTrendResearchWorkspace.mjs) 保留趋势研究壳层职责：

- 子页切换
- 共享白名单上下文
- 其他非诊断子页的共享载荷

过程诊断从共享 workspace 中拆出，不再直接消费 `recentProcess`。

### 2. 页面结构

过程诊断页改为单合约工作台，结构如下：

#### 顶部：合约切换条

仅展示：

- 合约名
- 极简健康状态
- 是否停滞 / 异常

不再在切换条中堆叠置信度、趋势状态、额外数值。

#### 第一主视图：健康概览

作为默认焦点区域，展示：

- 当前链路阶段
- Trade 新鲜度
- Book 新鲜度
- State 新鲜度
- 最近特征时间
- 最近推断时间
- 当前异常
- 停滞状态

目标是用户进入页面后 1 秒内就能判断“当前卡在哪一步”。

#### 第二主视图：诊断时间线

展示最近诊断事件片段：

- trade 到达
- book 到达
- state 同步
- feature 生成
- inference 生成
- error / recovery

时间线用于直接解释“为什么不刷新”，替代当前的多卡片平铺数字面板。

#### 底部折叠区：必要细节

保留：

- 最近错误消息
- 最近事件时间
- 少量计数器
- 订阅状态

删除：

- 所有合约卡片墙
- 与训练/因子页重复的统计块
- 与诊断主任务无关的次级数字

### 3. 组件边界

建议新增组件：

- `TrendDiagnosticsShell.vue`
- `TrendDiagnosticsInstrumentPicker.vue`
- `TrendDiagnosticsHealthSummary.vue`
- `TrendDiagnosticsTimeline.vue`
- `TrendDiagnosticsDetails.vue`

保留或改造：

- `TrendResearchDiagnosticsPage.vue`

职责调整：

- `TrendResearchDiagnosticsPage.vue`
  - 只做壳层集成，不再直接渲染业务细节
- `TrendDiagnosticsShell.vue`
  - 组织健康概览、时间线、细节区
- `TrendDiagnosticsHealthSummary.vue`
  - 专注渲染健康概览读模型
- `TrendDiagnosticsTimeline.vue`
  - 专注渲染单合约时间线
- `TrendDiagnosticsDetails.vue`
  - 专注渲染折叠细节

现有 [`TrendResearchProcessDiagnostics.vue`](/mnt/e/code/okxquantitative/frontend/src/renderer/components/analytics/TrendResearchProcessDiagnostics.vue) 不再继续膨胀，应当被替换或降级为兼容壳。

## 前端数据流

### 初始加载

页面进入过程诊断子页时：

1. 用 REST 拉取 `GET /api/trend-research/diagnostics`
2. 渲染当前选中合约的初始快照
3. 建立 `trend_diagnostics` WebSocket 订阅

### 实时更新

WS 事件处理规则：

- `snapshot`
  - 整体替换当前诊断快照
- `health_changed`
  - 只更新 `instrument_health` 与局部 `details`
- `timeline_appended`
  - 只向时间线末尾追加并裁剪窗口
- `feature_emitted`
  - 更新最近特征时间与相关健康状态
- `inference_emitted`
  - 更新最近推断时间与最终阶段状态
- `runtime_error_changed`
  - 更新 `current_error`，同步时间线错误段

前端不再每次收到事件后重建整个趋势研究壳层状态。

### 合约切换

合约切换时：

1. 立即发起新的 REST 首帧请求
2. 取消旧 `trend_diagnostics` 订阅
3. 建立新合约订阅
4. 页面只更新过程诊断自身状态，不影响训练页和因子页

## 错误处理

### REST 首帧失败

- 显示“初始诊断快照加载失败”
- 不覆盖已有 WS 诊断内容
- 支持用户手动刷新

### WS 断开

- 保留最后快照
- 显示“实时连接中断”
- 不用通用错误挡板覆盖整个工作区

### 运行时异常

- 写入 `current_error`
- 时间线追加 `error` 或 `recovery` 片段
- 健康概览显式标记异常态

不允许把运行时异常吞成“暂无数据”。

## 测试要求

后端新增或更新测试覆盖：

- 诊断投影器能从 runtime 事实生成单合约快照
- `trend_diagnostics` 首帧订阅能返回 `snapshot`
- `health_changed` / `timeline_appended` / `runtime_error_changed` 事件序列正确
- 合约切换后只推当前合约详细事件
- 断线重连后能重新发送首帧快照

前端新增或更新测试覆盖：

- 诊断页首屏默认聚焦健康概览
- WS 增量事件只更新局部状态，不重建整页
- 合约切换会取消旧订阅并建立新订阅
- REST 失败不遮挡已有诊断状态
- 时间线能够追加事件并裁剪窗口

## 迁移策略

采用分阶段迁移：

1. 先新增后端诊断读模型与独立接口，不移除旧 `recentProcess`
2. 前端新增独立诊断 workspace 和新组件树
3. 趋势研究壳层切换到新诊断页
4. 删除旧过程诊断冗余视图和共享依赖
5. 最后清理旧 `recentProcess` 相关兼容路径

这样可以避免一次性大爆炸替换。

## 风险与约束

- 过程诊断拆出独立通道后，必须保证与现有 `trend_research` 通道共存期间不会双重广播或状态漂移。
- 当前仓库里趋势研究模块仍在快速演进，重构时必须优先控制边界，而不是顺手继续加字段。
- [`service.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/service.py) 和 [`websocket.py`](/mnt/e/code/okxquantitative/backend/app/api/websocket.py) 已明显过大，本次重构应当同时完成职责下沉，而不是继续把新逻辑堆入原文件。

## 成功标准

当重构完成后，过程诊断应满足以下标准：

- 页面首次进入默认展示“当前选中合约”的健康概览
- 用户无需阅读大量数字，就能直接判断卡住阶段和最近断点
- 诊断时间线能直观看到 `trade/book/state/feature/inference/error/recovery`
- 过程诊断拥有独立 REST 与独立 WS 通道
- 前后端都不再依赖共享大 payload 才能渲染过程诊断
- 训练、因子、结论总览的状态变化不会触发诊断页整块重算
