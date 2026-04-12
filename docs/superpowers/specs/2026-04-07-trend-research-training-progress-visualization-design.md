# 趋势研究训练进度可视化设计

## 目标

为趋势研究增加“单运行、全链路、结构化”的训练过程可视化。用户在前端可以手动触发一次模型重训，并实时看到当前阶段、阶段耗时、阶段统计、`epoch` 训练曲线、最终验证指标以及失败原因，而不是只在结束后看到最终 `model_status`。

本设计只支持同一时刻一个训练任务运行，不做排队、不做静默取消、不做日志字符串解析。

## 当前现状

- 后端训练入口 [`training_runtime.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/training_runtime.py) 采用同步串行执行，只返回最终模型状态。
- 训练过程 [`direct_training.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/direct_training.py) 目前不暴露阶段进度、`epoch` 曲线或阶段统计。
- 实时推送 [`realtime.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/realtime.py) 已经向前端发送 `trend_research` 载荷，但不包含训练运行态。
- 前端趋势研究页 [`TrendResearchPanel.vue`](/mnt/e/code/okxquantitative/frontend/src/renderer/components/analytics/TrendResearchPanel.vue) 目前只展示推断结果、模型状态和因子视图，没有训练控制与训练监控区域。

因此，本次改造的核心不是“加一个进度条”，而是补一套结构化训练运行模型，并将其接入现有 REST 与 WebSocket 链路。

## 范围确认

- 前端支持手动触发重训。
- 训练进度面板常驻在趋势研究页顶部。
- 单运行模式：同一时刻最多一个训练任务。
- 复用现有 `trend_research` WebSocket 推送，不新增第二条实时通道。
- 可视化范围覆盖完整链路：
  - 数据收集
  - 共享因子解析
  - 样本构建
  - 数据集切分
  - `epoch` 训练
  - 验证评估
  - 模型保存
  - 模型激活

## 后端运行模型

新增一套训练运行快照模型，拆分为以下文件：

- `training_run_models.py`
- `training_tracker.py`

核心对象：

- `TrendTrainingRun`
  - `run_id`
  - `status`: `idle / queued / running / completed / failed`
  - `current_stage`
  - `progress_pct`
  - `message`
  - `started_at`
  - `finished_at`
  - `duration_seconds`
- `TrendTrainingStageSnapshot`
  - `stage`
  - `status`: `pending / running / completed / failed`
  - `started_at`
  - `finished_at`
  - `duration_seconds`
  - `message`
  - `stats`
- `TrendTrainingEpochPoint`
  - `epoch`
  - `total_epochs`
  - `train_loss`
  - `validation_loss`
  - `timestamp`

固定阶段定义为：

- `queued`
- `collect_bars`
- `resolve_shared_features`
- `build_samples`
- `split_dataset`
- `train_epochs`
- `evaluate_validation`
- `save_bundle`
- `activate_model`

阶段必须显式失败，不能吞成“模型未就绪”。

## 训练跟踪机制

`training_runtime.py` 负责编排阶段级状态：

- 进入阶段前 `start_stage(...)`
- 阶段完成后 `finish_stage(...)`
- 遇到错误 `fail_run(...)`
- 状态变化后统一触发 `service._emit_update()`

`direct_training.py` 负责 `epoch` 级上报：

- 为 `train_direct_extrema_model(...)` 增加显式回调参数 `progress_callback`
- 每个 `epoch` 完成后回调一次，写入：
  - 当前 `epoch`
  - 总 `epoch`
  - `train_loss`
  - `validation_loss`

回调是显式依赖注入，不使用全局单例，不用日志抓取。

## 单运行约束

趋势研究服务 [`service.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/service.py) 新增单任务句柄：

- `current_training_run`
- `current_training_task`

规则：

- 当前已有运行中任务时，再次触发重训直接返回 `409`
- 不自动排队
- 不自动取消当前训练
- 失败或完成后保留最近一次运行快照，供前端常驻面板继续展示

这样用户始终知道“上一次到底成功了没有”，不会因为任务结束而丢失现场。

## API 与实时推送

保留现有趋势研究 API 前缀，并新增：

- `GET /api/trend-research/training-run`
  - 返回当前或最近一次训练运行快照
- `POST /api/trend-research/model/retrain`
  - 改为“启动训练并立即返回运行快照”
  - 若已有运行中任务，返回 `409`

同时扩展现有 `trend_research` WebSocket 载荷：

- `training_run`
- `training_summary`

其中 `training_summary` 只放前端高频需要的聚合字段：

- `status`
- `current_stage`
- `progress_pct`
- `current_epoch`
- `total_epochs`
- `run_id`

前端进入页面先用 REST 拉一次完整快照，后续依赖现有 `trend_research` 推送增量刷新。

## 前端界面设计

在趋势研究页顶部新增常驻“训练控制与进度”面板，位于当前“结论与状态概览”之前。

面板拆为四个区块：

### 1. 控制区

- `开始重训` 按钮
- 当前运行态徽标：`空闲 / 排队 / 训练中 / 已完成 / 失败`
- 最近一次训练时间
- 最近一次耗时
- 当前运行 `run_id`

训练进行中按钮置灰；后端返回 `409` 时直接显示“已有训练任务运行中”。

### 2. 总进度区

- 总进度条
- 当前阶段名
- 当前阶段说明文字
- 当前阶段关键数字摘要

典型展示值：

- `已收集 3/5 个满足要求的合约`
- `共享因子 27 个`
- `样本 1,284 条`
- `Epoch 8 / 20`

### 3. 阶段时间线

固定按阶段顺序展示，每项显示：

- 状态
- 阶段耗时
- 阶段说明
- 阶段统计

训练失败时，失败阶段直接高亮，并保留错误信息。

### 4. 曲线与结果区

- 左侧：`epoch` 曲线图
  - `train_loss`
  - `validation_loss`
- 右侧：最终验证指标卡
  - 顶部时间 `MAE`
  - 底部时间 `MAE`
  - 顶部价格 `MAE`
  - 底部价格 `MAE`
  - 联合命中

未进入评估阶段时，这部分显示“等待评估结果”。

## 前端组件边界

新增组件：

- `TrendResearchTrainingRunPanel.vue`
- `trendResearchTrainingRunViewModel.mjs`
- `TrendResearchTrainingTimeline.vue`
- `TrendResearchTrainingCurves.vue`

职责划分：

- `TrendResearchTrainingRunPanel.vue`
  - 组织控制区、总进度区、时间线和曲线区
- `trendResearchTrainingRunViewModel.mjs`
  - 把后端结构化快照映射为面板可直接渲染的数据
- `TrendResearchTrainingTimeline.vue`
  - 专注渲染阶段时间线
- `TrendResearchTrainingCurves.vue`
  - 渲染 `epoch` 曲线

不把所有训练展示逻辑塞回 [`TrendResearchPanel.vue`](/mnt/e/code/okxquantitative/frontend/src/renderer/components/analytics/TrendResearchPanel.vue)。

## 错误处理

显式暴露以下失败类型：

- 本地特征条不足
- 无共享因子
- 样本数不足
- `PyTorch` 缺失
- 训练中异常
- 模型保存失败
- 模型激活失败

前端不做“训练失败但假装完成”的降级。失败状态保留在面板顶部，直到下一次训练开始覆盖。

## 测试与验收

后端测试至少覆盖：

- 启动训练运行后返回 `queued/running`
- 单运行冲突返回 `409`
- 阶段流转顺序正确
- `epoch` 上报被记录到运行快照
- 失败时保留失败阶段和错误信息
- `trend_research` 实时载荷包含 `training_run`

前端测试至少覆盖：

- 训练快照 view model 映射
- 训练中、完成、失败三种面板状态
- `epoch` 曲线数据映射
- 手动重训按钮状态切换
- `409` 冲突错误展示
- WebSocket 推送后面板实时刷新

验收标准：

- 用户点击一次“开始重训”，页面 `1` 秒内可见运行态变化
- 用户可以明确知道当前卡在哪个阶段，而不是只看到总百分比
- 训练过程中能实时看到 `epoch` 曲线更新
- 训练完成后模型状态卡自动切换到新模型
- 训练失败后页面保留失败阶段、失败原因和最近一次运行信息

## 非目标

- 不做多任务并发训练
- 不做训练队列
- 不做训练日志流式面板替代结构化事件
- 不新增第二条 WebSocket 通道
- 不做自动定时重训调度
