# 趋势研究直接预测未来顶底时间与价格设计

## 目标

将当前“未来是否出现顶部/底部事件”的双头逻辑回归分类器，升级为“直接预测未来 `60` 分钟内最高点与最低点的出现时间和价格”的时序模型。第一版仅覆盖 `USDT` 永续合约，采用全市场共享模型，不做按币种拆分。

模型上线后，系统需要直接输出：

- `predicted_top_eta_seconds`
- `predicted_bottom_eta_seconds`
- `predicted_top_price`
- `predicted_bottom_price`
- `predicted_top_return`
- `predicted_bottom_return`
- `top_time_distribution`
- `bottom_time_distribution`

## 当前现状

- 后端 [`inference.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/inference.py) 当前只支持两种路径：
  - 已训练模型时，输出 `top_probability` 与 `bottom_probability`
  - 无模型时，退回 `signed_trade_notional` 启发式占位逻辑
- 训练入口 [`training_runtime.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/training_runtime.py) 当前使用单点特征矩阵和双头逻辑回归。
- 标签生成 [`extrema_targets.py`](/mnt/e/code/okxquantitative/backend/app/core/trend_research/extrema_targets.py) 已经能计算未来顶部/底部事件与 `time_to_top_seconds` / `time_to_bottom_seconds`，但这些连续目标尚未进入训练链路。

因此，本次改造不是简单替换一个模型文件，而是要把训练目标、样本构建、模型持久化、线上推断和前端展示一起升级为“直接极值预测”。

## 确认后的范围

- 模型框架：`PyTorch`
- 预测窗口：未来 `60` 分钟
- 时间粒度：`1` 分钟，共 `60` 个时间桶
- 任务目标：分别预测未来 `60` 分钟内的最高点和最低点
- 训练范围：全市场共享模型，覆盖白名单内 `USDT` 永续合约
- 第一版编码器：`TCN`
- 第一版非目标：
  - 不上 `Transformer`
  - 不生成完整未来价格路径
  - 不做每币种独立模型
  - 不做静默回退到伪预测

## 标签设计

每个样本都以“当前时刻”为锚点，向前取最近 `120` 分钟的分钟级序列作为输入，向后取未来 `60` 分钟作为监督窗口。

四个主标签如下：

- `top_time_bucket`
  - 未来 `60` 个分钟桶里，最高价第一次出现在哪一分钟
- `bottom_time_bucket`
  - 未来 `60` 个分钟桶里，最低价第一次出现在哪一分钟
- `top_return`
  - `log(future_max_price / current_price)`
- `bottom_return`
  - `log(future_min_price / current_price)`

规则约束：

- 未来 `60` 分钟数据不完整的样本直接丢弃，不补齐
- 同一极值若出现多次，取最早出现的时间桶
- 顶部和底部相互独立，不要求谁先发生
- 价格目标始终使用相对当前价格的对数收益，避免不同币种绝对价格尺度污染共享模型

## 输入特征与序列构建

模型不再吃“当前这一秒的单点特征”，而是吃最近 `120` 个 `1m token` 组成的时序输入。

每个 `1m token` 由现有 `1s feature bars` 聚合而来，保留以下特征族：

- 盘口微观结构：`queue_imbalance`、`microprice_premium_bps`、`ofi_top_book`、`multi_level_book_imbalance`、`book_slope`
- 成交流与订单流：`signed_volume_imbalance`、`trade_intensity`、`large_trade_share`、`buy_burst_strength`、`sell_burst_strength`
- 价格结构：`momentum_30s/60s/300s`、`distance_to_window_extrema`、`breakout_pressure`、`realized_volatility`、`realized_range`、`trend_efficiency`
- 永续特有：`basis_bps`、`basis_momentum`、`funding_rate_level`、`funding_rate_delta`、`open_interest_level`、`open_interest_delta`、`price_oi_quadrant`、`premium_shock`
- 流动性：`amihud_illiquidity`、`impact_per_notional`、`depth_to_vol_ratio`

额外上下文特征：

- 当前价格对数值
- 近期波动率分位
- 合约流动性层级或成交额层级

所有标准化统计量只能在训练集上拟合，并随模型 bundle 一并持久化。

## 模型结构

第一版使用一个共享 `TCN` 编码器加四个输出头：

- `top_time_head -> 60 logits`
- `bottom_time_head -> 60 logits`
- `top_return_head -> 1`
- `bottom_return_head -> 1`

推荐结构：

- 输入张量：`[batch, 120, feature_dim]`
- 主干：多层 `1D dilated causal convolution`
- 连接：残差块
- 正则：`dropout`
- 归一化：`layer norm` 或等价稳定化层
- 聚合：使用最后时刻状态作为全局表征，再送入四个头

选择 `TCN` 的原因：

- 比当前逻辑回归更能利用时序结构
- 比 `Transformer` 更容易在当前数据规模和工程约束下稳定收敛
- 训练和线上推断成本都更适合先接入现有系统

## 损失函数与训练方式

时间头与价格头拆开训练：

- 时间头：`CrossEntropyLoss`
- 价格头：`HuberLoss`

总损失：

- `L = Lt_top + Lt_bottom + λ * Lp_top + λ * Lp_bottom`

其中 `λ` 作为价格回归损失权重，第一版保持显式配置，不写死在代码里。

训练方式：

- 仅按时间顺序切分，不允许随机打散
- 保持 `train / validation / test` 三段式
- 共享模型一次性覆盖全部目标合约
- 不做任何 mock 标签或空数据兜底

## 运行时推断

在线推断时：

1. 从每个合约最近 `120` 分钟分钟序列构造输入张量
2. 输出顶部和底部的 `60` 桶时间分布
3. 取最大概率桶作为 `eta`
4. 结合价格回归头，恢复目标价：
   - `predicted_top_price = current_price * exp(predicted_top_return)`
   - `predicted_bottom_price = current_price * exp(predicted_bottom_return)`

如果模型不存在、序列长度不足或输入特征缺失，应显式返回错误或“模型未就绪”状态，不允许伪造预测成功。

## 后端改造

新增或改造的职责边界：

- `sequence_dataset.py`
  - 从 `1s feature bars` 构造 `1m` 时序样本
- `tcn_model.py`
  - 定义 `PyTorch` 多任务 `TCN`
- `extrema_sequence_training.py`
  - 负责训练循环、验证、早停、指标汇总
- `model_store.py`
  - 扩展为保存 `PyTorch state_dict`、特征 schema、标准化统计量、训练配置和评估指标
- `inference.py`
  - 替换当前双头逻辑回归推断路径，改为直接极值时间/价格推断
- `service.py`
  - 维护每个合约最近 `120` 分钟分钟序列缓存
  - 提供模型状态、训练状态和最近一次预测结果
- `api/trend_research.py`
  - 提供模型状态、训练触发和预测载荷输出

## 前端改造

趋势研究面板需要从“概率卡片”升级为“直接预测结果 + 分布图”：

- 保留模型状态卡
- 结论区新增：
  - 预计顶部时间
  - 预计顶部价格
  - 预计底部时间
  - 预计底部价格
  - 预测窗口与模型版本
- 新增两个时间分布图：
  - `top_time_distribution`
  - `bottom_time_distribution`
- 当前 K 线图上增加预测标记：
  - 顶部预测点
  - 底部预测点

前端若收到“模型未就绪”或训练失败，应明确展示错误，不显示空白成功态。

## 验证标准

模型验收不能只看训练 loss，至少要求以下指标：

- 顶部时间误差中位数
- 底部时间误差中位数
- 顶部价格误差中位数
- 底部价格误差中位数
- 联合命中率：
  - 时间误差 `<= 5` 分钟
  - 且价格误差 `<= 50 bps`
- 分币种切片表现：
  - `BTC`
  - `ETH`
  - 主流中等流动性币组
  - 低流动性币组
- `walk-forward` 时间滚动验证

## 风险与边界

- 共享模型若缺少足够的低流动性样本，可能对小币泛化较差
- 极值价格目标天然重尾，必须优先使用抗异常值损失和显式评估
- 未来最高点和最低点可能都集中在窗口边缘，时间头会出现边界偏置，需要在验证里单独检查
- 新模型上线后，旧的 `top_probability / bottom_probability` 语义将不再是主输出，前后端接口必须同步迁移

## 非目标

- 不做全自动模型选型
- 不做在线增量训练
- 不做强化学习式交易决策
- 不在第一版输出完整顶底置信区间曲线
- 不保留“无模型时用启发式分数伪装预测结果”的旧行为
