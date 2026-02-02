<template>
  <div class="trading-view">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 页面标题 -->
        <div class="page-title">
          <span class="title-text">{{ pageModeText }}交易</span>
        </div>

        <!-- 交易对选择 -->
        <div class="dropdown-select" ref="symbolDropdown">
          <div class="dropdown-trigger" @click="toggleSymbolDropdown">
            <span class="dropdown-label">交易对</span>
            <span class="dropdown-value">{{ selectedSymbol }}</span>
            <span class="dropdown-arrow">{{ symbolDropdownOpen ? '▲' : '▼' }}</span>
          </div>
          <div class="dropdown-menu" v-if="symbolDropdownOpen">
            <div class="dropdown-search">
              <input
                type="text"
                v-model="symbolSearch"
                placeholder="搜索交易对..."
                @click.stop
              />
            </div>
            <div class="dropdown-add">
              <input
                type="text"
                v-model="newSymbolInput"
                placeholder="添加币种 (如 BTC)"
                @click.stop
                @keyup.enter="addCustomSymbol"
              />
              <button class="btn-add" @click.stop="addCustomSymbol">添加</button>
            </div>
            <div class="dropdown-list">
              <div
                v-for="symbol in filteredSymbols"
                :key="symbol"
                class="dropdown-item"
                :class="{ active: symbol === selectedSymbol, locked: isHoldingSymbol(symbol) }"
                @click="selectSymbol(symbol)"
              >
                <span class="symbol-text">{{ symbol }}</span>
                <span v-if="isHoldingSymbol(symbol)" class="lock-icon" title="持仓币种">L</span>
                <button
                  v-if="!isHoldingSymbol(symbol)"
                  class="btn-remove"
                  @click.stop="removeSymbol(symbol)"
                  title="删除"
                >X</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 交易模式显示 -->
        <div class="mode-indicator">
          <span class="mode-tag" :class="[props.mode, { locked: isModeLocked }]">
            {{ pageModeText }}
            <span v-if="isModeLocked" class="mode-lock-flag">LOCK</span>
          </span>
          <span class="default-mode-hint">默认：{{ defaultModeText }}</span>
        </div>

        <!-- 交易类型切换: 现货 / 永续 / 交割 -->
        <div class="trade-type-switch">
          <button
            class="type-btn"
            :class="{ active: tradeType === 'spot' }"
            @click="switchTradeType('spot')"
          >现货</button>
          <button
            class="type-btn"
            :class="{ active: tradeType === 'swap' }"
            @click="switchTradeType('swap')"
          >永续合约</button>
          <button
            class="type-btn"
            :class="{ active: tradeType === 'futures', disabled: true }"
            @click="showFuturesNotSupported"
            title="交割合约功能开发中"
          >交割合约 <span class="coming-soon">(开发中)</span></button>
        </div>
      </div>

      <div class="toolbar-right">
        <button class="btn btn-secondary" @click="refreshAll" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- API 未配置提示 -->
    <div v-if="!tradingStatus.api_configured" class="api-warning card">
      <h3>API 未配置</h3>
      <p>交易功能需要配置 OKX API 密钥。请前往设置页面配置您的 API 密钥。</p>
      <router-link to="/settings" class="btn btn-primary">前往设置</router-link>
    </div>

    <!-- 主内容区域 -->
    <div v-else class="trading-wrapper">
      <!-- 模式锁提示：允许查看，但禁止跨默认模式的交易动作 -->
      <div v-if="isModeLocked" class="mode-lock-warning card">
        <h3>交易已锁定</h3>
        <p>
          当前系统默认模式为 <strong>{{ defaultModeText }}</strong>，已禁止在 <strong>{{ pageModeText }}</strong>
          执行下单/撤单/合约设置等交易动作。你仍可查看该页面的账户、持仓、委托与成交信息。
        </p>
        <router-link to="/settings" class="btn btn-primary btn-small">去系统设置切换默认模式</router-link>
      </div>

      <div class="trading-layout">
      <!-- 左侧：账户信息 + 下单表单 -->
      <div class="left-panel">
        <!-- 账户信息卡片 -->
        <div class="card account-card">
          <h3>账户信息</h3>
          <div class="account-info">
            <div class="info-row">
              <span class="label">总权益 (USDT)</span>
              <span class="value">{{ formatNumber(accountBalance.total_equity) }}</span>
            </div>
            <div class="balance-details" v-if="accountBalance.details.length > 0">
              <div
                v-for="detail in accountBalance.details"
                :key="detail.ccy"
                class="detail-item"
              >
                <span class="ccy">{{ detail.ccy }}</span>
                <div class="amounts">
                  <span>可用: {{ formatNumber(detail.avail_bal) }}</span>
                  <span>冻结: {{ formatNumber(detail.frozen_bal) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="no-data">暂无余额数据</div>
          </div>
        </div>

        <!-- 下单表单卡片 -->
        <div class="card order-card">
          <h3>{{ tradeType === 'spot' ? '现货下单' : '合约下单' }}</h3>

          <!-- 当前价格显示 -->
          <div class="current-price-info" v-if="currentPrice">
            <span class="price-label">当前价格</span>
            <span class="price-value">${{ formatPrice(currentPrice.last) }}</span>
            <span class="price-change" :class="parseFloat(priceChange24h) >= 0 ? 'profit' : 'loss'">
              {{ parseFloat(priceChange24h) >= 0 ? '+' : '' }}{{ priceChange24h }}%
            </span>
          </div>
          <div class="current-price-info loading" v-else-if="priceLoading">
            <span class="price-label">加载价格中...</span>
          </div>

          <!-- 合约特有设置 -->
          <div v-if="tradeType !== 'spot'" class="contract-settings">
            <!-- 杠杆设置 -->
            <div class="form-group leverage-group">
              <label>杠杆倍数</label>
              <div class="leverage-selector">
                <button
                  v-for="lev in [1, 2, 3, 5, 10, 20, 50, 100]"
                  :key="lev"
                  type="button"
                  class="leverage-btn"
                  :class="{ active: contractSettings.leverage === lev }"
                  @click="setLeverage(lev)"
                  :disabled="isModeLocked"
                >{{ lev }}x</button>
              </div>
            </div>

            <!-- 保证金模式 -->
            <div class="form-group">
              <label>保证金模式</label>
              <div class="margin-mode-tabs">
                <button
                  type="button"
                  class="margin-btn"
                  :class="{ active: contractSettings.marginMode === 'cross' }"
                  @click="contractSettings.marginMode = 'cross'"
                >全仓</button>
                <button
                  type="button"
                  class="margin-btn"
                  :class="{ active: contractSettings.marginMode === 'isolated' }"
                  @click="contractSettings.marginMode = 'isolated'"
                >逐仓</button>
              </div>
            </div>

            <!-- 开仓方向选择 (合约) -->
            <div class="contract-side-tabs">
              <button
                type="button"
                class="contract-side-tab open-long"
                :class="{ active: contractSide === 'open_long' }"
                @click="contractSide = 'open_long'"
              >开多</button>
              <button
                type="button"
                class="contract-side-tab open-short"
                :class="{ active: contractSide === 'open_short' }"
                @click="contractSide = 'open_short'"
              >开空</button>
              <button
                type="button"
                class="contract-side-tab close-long"
                :class="{ active: contractSide === 'close_long' }"
                @click="contractSide = 'close_long'"
              >平多</button>
              <button
                type="button"
                class="contract-side-tab close-short"
                :class="{ active: contractSide === 'close_short' }"
                @click="contractSide = 'close_short'"
              >平空</button>
            </div>
          </div>

          <!-- 现货买卖方向选择 -->
          <div v-else class="side-tabs">
            <button
              type="button"
              class="side-tab"
              :class="{ active: currentSide === 'buy', buy: currentSide === 'buy' }"
              @click="currentSide = 'buy'"
            >
              买入
            </button>
            <button
              type="button"
              class="side-tab"
              :class="{ active: currentSide === 'sell', sell: currentSide === 'sell' }"
              @click="currentSide = 'sell'"
            >
              卖出
            </button>
          </div>

          <form @submit.prevent="tradeType === 'spot' ? confirmOrder(currentSide) : confirmContractOrder()">
            <!-- 订单类型 -->
            <div class="form-group">
              <label>订单类型</label>
              <select v-model="orderForm.order_type" class="select" :disabled="isModeLocked">
                <option value="market">市价单</option>
                <option value="limit">限价单</option>
              </select>
            </div>

            <!-- 价格（限价单） -->
            <div class="form-group" v-if="orderForm.order_type === 'limit'">
              <label>价格 (USDT)</label>
              <input
                type="number"
                v-model="orderForm.price"
                class="input"
                step="0.01"
                placeholder="输入委托价格"
                :disabled="isModeLocked"
              />
            </div>

            <!-- 数量 -->
            <div class="form-group">
              <label>{{ tradeType === 'spot' ? '数量' : '数量 (张)' }}</label>
              <div class="input-with-info">
                <input
                  type="number"
                  v-model="orderForm.size"
                  class="input"
                  :step="tradeType === 'spot' ? '0.0001' : '1'"
                  placeholder="输入数量"
                  :disabled="isModeLocked"
                />
                <span class="input-suffix">{{ tradeType === 'spot' ? baseCurrency : '张' }}</span>
              </div>
              <!-- 可买可卖数量显示 -->
              <div class="max-size-info">
                <span class="max-item">
                  <span class="max-label">{{ tradeType === 'spot' ? '可买:' : '可开多:' }}</span>
                  <span class="max-value">{{ formatNumber(maxTradeSize.maxBuy) }} {{ tradeType === 'spot' ? baseCurrency : '张' }}</span>
                </span>
                <span class="max-divider">|</span>
                <span class="max-item">
                  <span class="max-label">{{ tradeType === 'spot' ? '可卖:' : '可开空:' }}</span>
                  <span class="max-value">{{ formatNumber(maxTradeSize.maxSell) }} {{ tradeType === 'spot' ? baseCurrency : '张' }}</span>
                </span>
              </div>
            <div class="quick-amounts">
              <button type="button" class="quick-btn" @click="setQuickAmount(0.25)" :disabled="isModeLocked">25%</button>
              <button type="button" class="quick-btn" @click="setQuickAmount(0.5)" :disabled="isModeLocked">50%</button>
              <button type="button" class="quick-btn" @click="setQuickAmount(0.75)" :disabled="isModeLocked">75%</button>
              <button type="button" class="quick-btn" @click="setQuickAmount(1)" :disabled="isModeLocked">100%</button>
            </div>
          </div>

            <!-- 预估金额 -->
            <div class="estimated-amount" v-if="orderForm.size">
              <span class="estimated-label">预估金额</span>
              <span class="estimated-value">{{ estimatedAmount }} USDT</span>
            </div>

            <!-- 下单按钮 -->
            <div class="order-buttons">
              <!-- 现货按钮 -->
              <button
                v-if="tradeType === 'spot'"
                type="button"
                class="btn"
                :class="currentSide === 'buy' ? 'btn-buy' : 'btn-sell'"
                @click="confirmOrder(currentSide)"
                :disabled="orderLoading || isModeLocked"
              >
                {{ orderLoading ? '处理中...' : (currentSide === 'buy' ? '买入' : '卖出') + ' ' + baseCurrency }}
              </button>
              <!-- 合约按钮 -->
              <button
                v-else
                type="button"
                class="btn"
                :class="contractSideClass"
                @click="confirmContractOrder()"
                :disabled="orderLoading || isModeLocked"
              >
                {{ orderLoading ? '处理中...' : contractSideText }}
              </button>
            </div>
          </form>

          <!-- 订单结果提示 -->
          <div v-if="orderResult" class="order-result" :class="orderResult.success ? 'success' : 'error'">
            {{ orderResult.message }}
          </div>
        </div>
      </div>

      <!-- 右侧：持仓 + 委托 + 成交 -->
      <div class="right-panel">
        <!-- 现货持仓表格 -->
        <div v-if="tradeType === 'spot'" class="card positions-card">
          <div class="card-header-with-info">
            <h3>现货持仓</h3>
            <button class="btn btn-small btn-ghost" @click="syncFills" :disabled="syncingFills">
              {{ syncingFills ? '同步中...' : '同步记录' }}
            </button>
          </div>
          <!-- 成本统计信息 -->
          <div class="cost-summary" v-if="totalCostUsdt !== '0'">
            <div class="summary-item">
              <span class="summary-label">当前市值</span>
              <span class="summary-value">${{ formatNumber(totalValueWithCost) }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">总成本</span>
              <span class="summary-value">${{ formatNumber(totalCostUsdt) }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">总手续费</span>
              <span class="summary-value">${{ formatNumber(totalFeeUsdt) }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">盈亏</span>
              <span class="summary-value" :class="getPnlClass(totalPnlPercent)">
                ${{ formatNumber(totalPnlUsdt) }} ({{ formatPnl(totalPnlPercent) }})
              </span>
            </div>
          </div>
          <div class="table-container">
            <table v-if="spotHoldings.length > 0">
              <thead>
                <tr>
                  <th>币种</th>
                  <th>持仓数量</th>
                  <th>可用</th>
                  <th>成本价</th>
                  <th>当前价</th>
                  <th>市值(USDT)</th>
                  <th>盈亏</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="holding in spotHoldings" :key="holding.ccy" :class="{ stablecoin: holding.is_stablecoin }">
                  <td class="ccy-cell">
                    <span class="ccy-name">{{ holding.ccy }}</span>
                    <span v-if="holding.is_stablecoin" class="stable-tag">稳定币</span>
                  </td>
                  <td>{{ formatNumber(holding.total) }}</td>
                  <td>{{ formatNumber(holding.available) }}</td>
                  <td>{{ holding.avg_cost === '-' ? '-' : '$' + formatPrice(holding.avg_cost) }}</td>
                  <td>{{ holding.price_usdt === '-' ? '-' : '$' + formatPrice(holding.price_usdt) }}</td>
                  <td>{{ holding.value_usdt === '-' ? '-' : '$' + formatNumber(holding.value_usdt) }}</td>
                  <td :class="getPnlClass(holding.pnl_percent)">
                    {{ formatPnl(holding.pnl_percent) }}
                  </td>
                  <td class="actions-cell">
                    <button
                      v-if="!holding.is_stablecoin"
                      class="btn btn-small btn-ghost"
                      @click="openEditCostDialog(holding)"
                      title="编辑成本"
                    >
                      编辑
                    </button>
                    <button
                      v-if="!holding.is_stablecoin && parseFloat(holding.available) > 0"
                      class="btn btn-small btn-sell"
                      @click="quickSell(holding)"
                    >
                      卖出
                    </button>
                    <span v-if="holding.is_stablecoin" class="no-action">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-else class="no-data">暂无持仓</div>
          </div>
        </div>

        <!-- 合约持仓表格 -->
        <div v-else class="card positions-card contract-positions">
          <div class="card-header-with-info">
            <h3>合约持仓</h3>
            <button class="btn btn-small btn-ghost" @click="fetchContractPositions">刷新</button>
          </div>
          <div class="table-container">
            <table v-if="contractPositions.length > 0">
              <thead>
                <tr>
                  <th>合约</th>
                  <th>方向</th>
                  <th>数量(张)</th>
                  <th>开仓均价</th>
                  <th>标记价格</th>
                  <th>未实现盈亏</th>
                  <th>杠杆</th>
                  <th>强平价</th>
                  <th>保证金</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pos in contractPositions" :key="pos.inst_id + pos.pos_side">
                  <td>{{ pos.inst_id }}</td>
                  <td :class="pos.pos_side === 'long' ? 'long-side' : (pos.pos_side === 'short' ? 'short-side' : 'net-side')">
                    {{ pos.pos_side === 'long' ? '多' : (pos.pos_side === 'short' ? '空' : '净') }}
                  </td>
                  <td>{{ pos.pos }}</td>
                  <td>${{ formatPrice(pos.avg_px) }}</td>
                  <td>${{ formatPrice(pos.mark_px) }}</td>
                  <td :class="parseFloat(pos.upl) >= 0 ? 'profit' : 'loss'">
                    ${{ formatNumber(pos.upl) }}
                    <span class="upl-ratio">({{ (parseFloat(pos.upl_ratio) * 100).toFixed(2) }}%)</span>
                  </td>
                  <td>{{ pos.lever }}x</td>
                  <td>${{ formatPrice(pos.liq_px) }}</td>
                  <td>${{ formatNumber(pos.margin) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="no-data">暂无合约持仓</div>
          </div>
        </div>

        <!-- 当前委托表格 -->
        <div class="card orders-card">
          <h3>当前委托</h3>
          <div class="table-container">
            <table v-if="pendingOrders.length > 0">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>交易对</th>
                  <th>方向</th>
                  <th>类型</th>
                  <th>价格</th>
                  <th>数量</th>
                  <th>已成交</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="order in pendingOrders" :key="order.ord_id">
                  <td>{{ formatTime(order.c_time) }}</td>
                  <td>{{ order.inst_id }}</td>
                  <td :class="order.side">{{ order.side === 'buy' ? '买入' : '卖出' }}</td>
                  <td>{{ order.ord_type === 'market' ? '市价' : '限价' }}</td>
                  <td>{{ formatPrice(order.px) }}</td>
                  <td>{{ formatNumber(order.sz) }}</td>
                  <td>{{ formatNumber(order.fill_sz) }}</td>
                  <td>{{ getOrderStateText(order.state) }}</td>
                  <td>
                    <button
                      class="btn btn-small btn-danger"
                      @click="cancelOrder(order)"
                      :disabled="cancelingOrderId === order.ord_id || isModeLocked"
                    >
                      {{ cancelingOrderId === order.ord_id ? '撤销中' : '撤单' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-else class="no-data">暂无委托</div>
          </div>
        </div>

        <!-- 成交记录表格 -->
        <div class="card fills-card">
          <h3>成交记录</h3>
          <div class="table-container">
            <table v-if="fills.length > 0">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>交易对</th>
                  <th>方向</th>
                  <th>成交价</th>
                  <th>成交量</th>
                  <th>手续费</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="fill in fills" :key="fill.trade_id">
                  <td>{{ formatTime(fill.ts) }}</td>
                  <td>{{ fill.inst_id }}</td>
                  <td :class="fill.side">{{ fill.side === 'buy' ? '买入' : '卖出' }}</td>
                  <td>{{ formatPrice(fill.fill_px) }}</td>
                  <td>{{ formatNumber(fill.fill_sz) }}</td>
                  <td>{{ formatNumber(fill.fee) }} {{ fill.fee_ccy }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="no-data">暂无成交记录</div>
          </div>
        </div>
      </div>
      </div>
    </div>

    <!-- 下单确认弹窗 -->
    <div class="confirm-dialog-overlay" v-if="showConfirmDialog" @click.self="cancelConfirm">
      <div class="confirm-dialog">
        <h3>确认下单</h3>
        <div class="confirm-content" v-if="pendingOrder">
          <div class="confirm-row">
            <span class="confirm-label">交易对</span>
            <span class="confirm-value">{{ pendingOrder.inst_id }}</span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">方向</span>
            <span class="confirm-value" :class="pendingOrder.side">
              {{ pendingOrder.side === 'buy' ? '买入' : '卖出' }}
            </span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">类型</span>
            <span class="confirm-value">{{ pendingOrder.order_type === 'market' ? '市价单' : '限价单' }}</span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">数量</span>
            <span class="confirm-value">{{ pendingOrder.size }} {{ baseCurrency }}</span>
          </div>
          <div class="confirm-row" v-if="pendingOrder.order_type === 'limit'">
            <span class="confirm-label">价格</span>
            <span class="confirm-value">{{ pendingOrder.price }} USDT</span>
          </div>
          <div class="confirm-row highlight">
            <span class="confirm-label">预估金额</span>
            <span class="confirm-value">{{ pendingOrder.estimated }} USDT</span>
          </div>
        </div>
        <div class="confirm-buttons">
          <button class="btn btn-secondary" @click="cancelConfirm">取消</button>
          <button
            class="btn"
            :class="pendingOrder?.side === 'buy' ? 'btn-buy' : 'btn-sell'"
            @click="executeOrder"
            :disabled="orderLoading || isModeLocked"
          >
            {{ orderLoading ? '处理中...' : '确认下单' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 合约下单确认弹窗 -->
    <div class="confirm-dialog-overlay" v-if="showContractConfirmDialog" @click.self="cancelContractConfirm">
      <div class="confirm-dialog contract-confirm">
        <h3>确认合约下单</h3>
        <div class="contract-warning">
          <span class="warning-icon">!</span>
          <span>合约交易风险较高，请确认订单信息</span>
        </div>
        <div class="confirm-content" v-if="pendingContractOrder">
          <div class="confirm-row">
            <span class="confirm-label">合约</span>
            <span class="confirm-value">{{ pendingContractOrder.inst_id }}</span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">操作</span>
            <span class="confirm-value" :class="pendingContractOrder.side">
              {{ pendingContractOrder.sideText }}
            </span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">杠杆</span>
            <span class="confirm-value highlight-lever">{{ pendingContractOrder.leverage }}x</span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">保证金模式</span>
            <span class="confirm-value">{{ pendingContractOrder.marginMode }}</span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">订单类型</span>
            <span class="confirm-value">{{ pendingContractOrder.order_type === 'market' ? '市价单' : '限价单' }}</span>
          </div>
          <div class="confirm-row">
            <span class="confirm-label">数量(张)</span>
            <span class="confirm-value">{{ pendingContractOrder.size }}</span>
          </div>
          <div class="confirm-row" v-if="pendingContractOrder.order_type === 'limit'">
            <span class="confirm-label">价格</span>
            <span class="confirm-value">{{ pendingContractOrder.price }} USDT</span>
          </div>
        </div>
        <div class="confirm-buttons">
          <button class="btn btn-secondary" @click="cancelContractConfirm">取消</button>
          <button
            class="btn"
            :class="{
              'btn-open-long': pendingContractOrder?.side === 'open_long',
              'btn-open-short': pendingContractOrder?.side === 'open_short',
              'btn-close-long': pendingContractOrder?.side === 'close_long',
              'btn-close-short': pendingContractOrder?.side === 'close_short'
            }"
            @click="executeContractOrder"
            :disabled="orderLoading || isModeLocked"
          >
            {{ orderLoading ? '处理中...' : '确认下单' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑成本弹窗 -->
    <div class="modal-overlay" v-if="showEditCostDialog" @click.self="closeEditCostDialog">
      <div class="modal-dialog edit-cost-dialog">
        <h3>编辑成本价 - {{ editingCcy }}</h3>
        <div class="edit-cost-form">
          <div class="form-row">
            <label>平均成本价 (USDT)</label>
            <input
              type="number"
              v-model="editCostValue"
              step="0.0001"
              min="0"
              placeholder="输入成本价"
            />
          </div>
          <p class="edit-cost-hint">
            提示：此价格将用于计算该币种的盈亏百分比
          </p>
        </div>
        <div class="confirm-buttons">
          <button class="btn btn-secondary" @click="closeEditCostDialog">取消</button>
          <button class="btn btn-primary" @click="saveCostBasis" :disabled="savingCost">
            {{ savingCost ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, onActivated, onDeactivated, watch } from 'vue'
import { api } from '../services/api'
import marketWS from '../services/websocket'
import { useAppStore } from '../stores/app'

// 定义组件名称，用于 keep-alive 缓存
defineOptions({
  name: 'TradingView'
})

// ========== 持久化存储 ==========
const TRADING_PREFS_KEY = 'trading_settings';

// 保存设置到后端
const saveSettings = async () => {
  try {
    const settings = {
      selectedSymbol: selectedSymbol.value,
      availableSymbols: availableSymbols.value,
    };
    await api.updatePreferences({ [TRADING_PREFS_KEY]: settings });
  } catch (e) {
    console.warn('保存交易设置失败:', e);
  }
};

// 防抖保存
let saveTimer = null;
const debouncedSave = () => {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveSettings();
  }, 500);
};

// 设置是否已加载
const settingsLoaded = ref(false);

// 从后端加载设置
const loadSettings = async () => {
  try {
    const res = await api.getPreferences();
    if (res.success && res.data && res.data[TRADING_PREFS_KEY]) {
      const saved = res.data[TRADING_PREFS_KEY];
      if (saved.availableSymbols && saved.availableSymbols.length > 0) {
        availableSymbols.value = saved.availableSymbols;
      }
      if (saved.selectedSymbol) {
        selectedSymbol.value = saved.selectedSymbol;
      }
      console.log('[TradingView] 已从后端加载设置');
    }
  } catch (e) {
    console.warn('加载交易设置失败:', e);
  } finally {
    settingsLoaded.value = true;
  }
};

// ========== Props ==========
const props = defineProps({
  // 页面模式: 'simulated' 或 'live'
  // 用于区分模拟盘页面和实盘页面
  mode: {
    type: String,
    default: 'simulated',
    validator: (value) => ['simulated', 'live'].includes(value)
  }
})

// 全局状态：用于读取“系统默认模式”（OKX_USE_SIMULATED）
const appStore = useAppStore()
const defaultModeText = computed(() => (appStore.isSimulated ? '模拟盘' : '实盘'))

// 模式锁：允许查看两套盘的数据，但交易动作必须跟随默认模式
const isModeLocked = computed(() => props.mode !== appStore.tradingMode)

// 统一提取后端错误信息（优先使用 FastAPI 的 detail）
const getErrorDetail = (e) => {
  return e?.response?.data?.detail || e?.response?.data?.message || e?.message || '网络错误'
}

// ========== 状态 ==========
const loading = ref(false)
const orderLoading = ref(false)
const cancelingOrderId = ref(null)

// 当前价格信息
const currentPrice = ref(null)
const priceLoading = ref(false)
const wsConnected = ref(false)  // WebSocket 连接状态

// 最大可交易数量
const maxTradeSize = reactive({
  maxBuy: '0',
  maxSell: '0'
})

// 确认弹窗
const showConfirmDialog = ref(false)
const pendingOrder = ref(null)

// 合约下单确认弹窗
const showContractConfirmDialog = ref(false)
const pendingContractOrder = ref(null)

// 当前操作方向（用于快捷按钮）
const currentSide = ref('buy')

// ========== 合约交易状态 ==========
// 交易类型: spot（现货）、swap（永续）、futures（交割）
const tradeType = ref('spot')

// 合约方向: open_long, open_short, close_long, close_short
const contractSide = ref('open_long')

// 合约设置
const contractSettings = reactive({
  leverage: 10,
  marginMode: 'cross'  // cross(全仓) 或 isolated(逐仓)
})

// 合约账户持仓模式：long_short_mode(双向) / net_mode(单向)
const contractPosMode = ref('')

// 合约持仓
const contractPositions = ref([])

// 交易状态
const tradingStatus = reactive({
  trader_available: false,
  account_available: false,
  mode: 'simulated',
  api_configured: false
})

// 页面显示模式文本
const pageModeText = computed(() => {
  return props.mode === 'simulated' ? '模拟盘' : '实盘'
})

const buildModeLockMessage = () => {
  return `当前系统默认模式为${defaultModeText.value}，已禁止在${pageModeText.value}执行交易操作。请在“系统设置”切换默认模式后重试。`
}

// 账户余额
const accountBalance = reactive({
  total_equity: '0',
  details: []
})

// 现货持仓
const spotHoldings = ref([])
const totalValueUsdt = ref('0')
const totalValueWithCost = ref('0')
const totalCostUsdt = ref('0')
const totalFeeUsdt = ref('0')
const totalPnlUsdt = ref('0')
const totalPnlPercent = ref('0')

// 持仓优化：基础数据（余额+成本）与实时价格分离
const holdingsBase = ref([])  // 从 /holdings-base 获取的基础数据
const holdingPrices = reactive({})  // 各币种实时价格缓存 { 'BTC': 50000, 'ETH': 3000 }

// 计算持仓市值和盈亏（使用缓存的实时价格）
const recalcHoldings = () => {
  if (!holdingsBase.value.length) return

  const holdings = []
  let totalValue = 0
  let totalCost = 0
  let totalValueWithCostCalc = 0
  let totalFee = 0

  for (const h of holdingsBase.value) {
    const ccy = h.ccy
    const totalBal = parseFloat(h.total) || 0

    if (h.is_stablecoin) {
      // 稳定币直接用 1:1
      holdings.push({
        ...h,
        price_usdt: '1.0',
        value_usdt: String(totalBal.toFixed(2)),
        pnl_usdt: '-',
        pnl_percent: '-',
      })
      totalValue += totalBal
    } else {
      // 非稳定币使用缓存价格
      const price = holdingPrices[ccy] || 0
      const value = totalBal * price

      let pnlUsdt = null
      let pnlPercent = null
      const avgCost = h.avg_cost ? parseFloat(h.avg_cost) : null
      const costTotal = h.total_cost ? parseFloat(h.total_cost) : null
      const feeTotal = h.total_fee ? parseFloat(h.total_fee) : null

      if (avgCost && avgCost > 0 && costTotal !== null) {
        pnlUsdt = value - costTotal
        pnlPercent = ((price - avgCost) / avgCost * 100)
        totalCost += costTotal
        totalValueWithCostCalc += value
        if (feeTotal) totalFee += feeTotal
      }

      holdings.push({
        ...h,
        price_usdt: price > 0 ? String(price.toFixed(4)) : '-',
        value_usdt: price > 0 ? String(value.toFixed(2)) : '-',
        pnl_usdt: pnlUsdt !== null ? String(pnlUsdt.toFixed(2)) : '-',
        pnl_percent: pnlPercent !== null ? String(pnlPercent.toFixed(2)) : '-',
      })
      totalValue += value
    }
  }

  // 按市值排序（稳定币在前）
  holdings.sort((a, b) => {
    if (a.is_stablecoin !== b.is_stablecoin) return a.is_stablecoin ? -1 : 1
    const va = parseFloat(a.value_usdt) || 0
    const vb = parseFloat(b.value_usdt) || 0
    return vb - va
  })

  spotHoldings.value = holdings
  totalValueUsdt.value = totalValue.toFixed(2)
  totalCostUsdt.value = totalCost.toFixed(2)
  totalValueWithCost.value = totalValueWithCostCalc.toFixed(2)
  totalFeeUsdt.value = totalFee.toFixed(2)

  if (totalCost > 0) {
    const pnl = totalValueWithCostCalc - totalCost
    totalPnlUsdt.value = pnl.toFixed(2)
    totalPnlPercent.value = (pnl / totalCost * 100).toFixed(2)
  } else {
    totalPnlUsdt.value = '0'
    totalPnlPercent.value = '0'
  }
}

// 成本编辑相关
const syncingFills = ref(false)
const showEditCostDialog = ref(false)
const editingCcy = ref('')
const editCostValue = ref('')
const savingCost = ref(false)

// 当前委托
const pendingOrders = ref([])

// 成交记录
const fills = ref([])

// 订单结果
const orderResult = ref(null)

// 交易对选择
const selectedSymbol = ref('BTC-USDT')
const symbolDropdownOpen = ref(false)
const symbolSearch = ref('')
const availableSymbols = ref([])  // 从持久化设置加载，首次使用时从持仓初始化
const holdingSymbols = ref([])  // 持仓币种列表（不可删除）
const newSymbolInput = ref('')  // 添加币种输入框

// 判断是否为持仓币种（不可删除）
const isHoldingSymbol = (symbol) => {
  return holdingSymbols.value.includes(symbol)
}

// 下单表单
const orderForm = reactive({
  order_type: 'market',
  price: '',
  size: ''
})

// ========== 计算属性 ==========
const filteredSymbols = computed(() => {
  const search = symbolSearch.value.toUpperCase()
  return availableSymbols.value.filter(s => s.includes(search))
})

const baseCurrency = computed(() => {
  return selectedSymbol.value.split('-')[0]
})

// 计算预估交易金额
const estimatedAmount = computed(() => {
  const size = parseFloat(orderForm.size) || 0
  if (size <= 0) return '0.00'

  let price = 0
  if (orderForm.order_type === 'limit' && orderForm.price) {
    price = parseFloat(orderForm.price) || 0
  } else if (currentPrice.value && currentPrice.value.last) {
    price = parseFloat(currentPrice.value.last) || 0
  }

  return (size * price).toFixed(2)
})

// 价格涨跌幅
const priceChange24h = computed(() => {
  if (!currentPrice.value) return null
  const last = parseFloat(currentPrice.value.last) || 0
  const open = parseFloat(currentPrice.value.open24h) || 0
  if (open === 0) return 0
  return ((last - open) / open * 100).toFixed(2)
})

// 合约交易对ID（根据交易类型转换）
const contractInstId = computed(() => {
  if (tradeType.value === 'spot') return selectedSymbol.value
  // 永续合约: BTC-USDT -> BTC-USDT-SWAP
  if (tradeType.value === 'swap') return selectedSymbol.value + '-SWAP'
  // 交割合约暂不支持（需要季度合约后缀如 BTC-USDT-250331）
  return ''
})

// 交割合约暂不支持提示
const showFuturesNotSupported = () => {
  orderResult.value = {
    success: false,
    message: '交割合约功能开发中，请使用永续合约进行交易'
  }
}

// 合约按钮样式
const contractSideClass = computed(() => {
  const side = contractSide.value
  if (side === 'open_long') return 'btn-open-long'
  if (side === 'open_short') return 'btn-open-short'
  if (side === 'close_long') return 'btn-close-long'
  if (side === 'close_short') return 'btn-close-short'
  return ''
})

// 合约按钮文字
const contractSideText = computed(() => {
  const side = contractSide.value
  if (side === 'open_long') return '开多'
  if (side === 'open_short') return '开空'
  if (side === 'close_long') return '平多'
  if (side === 'close_short') return '平空'
  return ''
})

// ========== 方法 ==========

// 格式化数字（至少6位小数）
const formatNumber = (val) => {
  const num = parseFloat(val)
  if (isNaN(num)) return '0.000000'
  if (Math.abs(num) >= 1000) return num.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 })
  return num.toFixed(6)
}

// 格式化价格（至少6位小数）
const formatPrice = (val) => {
  const num = parseFloat(val)
  if (isNaN(num) || num === 0) return '-'
  return num.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 })
}

// 格式化百分比
const formatPercent = (val) => {
  const num = parseFloat(val) * 100
  if (isNaN(num)) return '0.00%'
  return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
}

// 格式化时间
const formatTime = (ts) => {
  if (!ts) return '-'
  const date = new Date(parseInt(ts))
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 获取盈亏样式类
const getPlClass = (val) => {
  const num = parseFloat(val)
  if (num > 0) return 'profit'
  if (num < 0) return 'loss'
  return ''
}

// 获取涨跌样式类
const getChangeClass = (val) => {
  if (val === '-' || val === '0') return ''
  const num = parseFloat(val)
  if (num > 0) return 'profit'
  if (num < 0) return 'loss'
  return ''
}

// 格式化涨跌幅
const formatChange = (val) => {
  if (val === '-' || val === '0') return '-'
  const num = parseFloat(val)
  if (isNaN(num)) return '-'
  return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
}

// 获取订单状态文本
const getOrderStateText = (state) => {
  const stateMap = {
    'live': '等待成交',
    'partially_filled': '部分成交',
    'filled': '完全成交',
    'canceled': '已撤销',
    'mmp_canceled': '做市商撤销'
  }
  return stateMap[state] || state
}

// 切换交易对下拉框
const toggleSymbolDropdown = () => {
  symbolDropdownOpen.value = !symbolDropdownOpen.value
}

// 选择交易对
const selectSymbol = (symbol) => {
  selectedSymbol.value = symbol
  symbolDropdownOpen.value = false
  symbolSearch.value = ''
}

// 添加自定义交易对
const addCustomSymbol = () => {
  let symbol = newSymbolInput.value.trim().toUpperCase()
  if (!symbol) return

  // 自动补全 -USDT 后缀
  if (!symbol.includes('-')) {
    symbol = `${symbol}-USDT`
  }

  // 检查是否已存在
  if (availableSymbols.value.includes(symbol)) {
    newSymbolInput.value = ''
    return
  }

  availableSymbols.value.push(symbol)
  newSymbolInput.value = ''
}

// 删除交易对（持仓币种不可删除）
const removeSymbol = (symbol) => {
  if (isHoldingSymbol(symbol)) return

  const idx = availableSymbols.value.indexOf(symbol)
  if (idx > -1) {
    availableSymbols.value.splice(idx, 1)
  }

  // 如果删除的是当前选中的，切换到第一个
  if (selectedSymbol.value === symbol && availableSymbols.value.length > 0) {
    selectedSymbol.value = availableSymbols.value[0]
  }
}

// 获取当前交易对价格
const fetchCurrentPrice = async () => {
  priceLoading.value = true
  try {
    const res = await api.getTicker(selectedSymbol.value)
    if (res && res.data) {
      // 后端返回 snake_case 字段，转换为与 WebSocket 一致的 camelCase 格式
      const d = res.data
      currentPrice.value = {
        last: d.last,
        askPx: d.ask_px,
        bidPx: d.bid_px,
        open24h: d.open_24h,
        high24h: d.high_24h,
        low24h: d.low_24h,
        vol24h: d.vol_24h,
        change24h: d.change_24h,
        timestamp: d.timestamp,
      }
    }
  } catch (e) {
    console.error('获取价格失败:', e)
    currentPrice.value = null
  } finally {
    priceLoading.value = false
  }
}

// 获取最大可交易数量
const fetchMaxSize = async () => {
  try {
    if (tradeType.value === 'spot') {
      // 现货
      const res = await api.getMaxSize(selectedSymbol.value, 'cash', props.mode)
      maxTradeSize.maxBuy = res.max_buy || '0'
      maxTradeSize.maxSell = res.max_sell || '0'
    } else {
      // 合约（axios拦截器已返回response.data，res即后端JSON）
      const res = await api.getContractMaxSize(contractInstId.value, contractSettings.marginMode, props.mode)
      maxTradeSize.maxBuy = res.max_buy || '0'
      maxTradeSize.maxSell = res.max_sell || '0'
    }
  } catch (e) {
    console.error('获取最大数量失败:', e)
    maxTradeSize.maxBuy = '0'
    maxTradeSize.maxSell = '0'
  }
}

// 快速设置数量百分比
const setQuickAmount = (percent) => {
  if (tradeType.value !== 'spot') {
    // 合约模式下根据方向设置
    const isLong = contractSide.value === 'open_long' || contractSide.value === 'close_short'
    const max = parseFloat(isLong ? maxTradeSize.maxBuy : maxTradeSize.maxSell) || 0
    orderForm.size = max > 0 ? Math.floor(max * percent).toString() : ''
    return
  }
  // 现货模式：根据当前方向计算数量
  if (currentSide.value === 'buy') {
    const maxBuy = parseFloat(maxTradeSize.maxBuy) || 0
    orderForm.size = maxBuy > 0 ? (maxBuy * percent).toFixed(6) : ''
  } else {
    const maxSell = parseFloat(maxTradeSize.maxSell) || 0
    orderForm.size = maxSell > 0 ? (maxSell * percent).toFixed(6) : ''
  }
}

// 刷新所有数据
const refreshAll = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchTradingStatus(),
      fetchAccountBalance(),
      fetchSpotHoldings(),
      fetchPendingOrders(),
      fetchFills()
    ])
  } finally {
    loading.value = false
  }
}

// 获取交易状态
const fetchTradingStatus = async () => {
  try {
    const res = await api.getTradingStatus(props.mode)
    Object.assign(tradingStatus, res)
  } catch (e) {
    console.error('获取交易状态失败:', e)
  }
}

// 获取账户余额
const fetchAccountBalance = async () => {
  try {
    const res = await api.getAccount(props.mode)
    accountBalance.total_equity = res.total_equity || '0'
    accountBalance.details = res.details || []
  } catch (e) {
    console.error('获取账户余额失败:', e)
  }
}

// 持仓币种的 WebSocket 价格回调
const onHoldingPriceUpdate = (data) => {
  // data.instId 格式为 'BTC-USDT'，提取币种
  const ccy = data.instId.split('-')[0]
  const price = parseFloat(data.last) || 0
  if (price > 0) {
    holdingPrices[ccy] = price
    // 价格更新后重新计算持仓
    recalcHoldings()
  }
}

// 订阅所有持仓币种的价格
const subscribeHoldingPrices = () => {
  if (!marketWS.isConnected) return

  for (const h of holdingsBase.value) {
    if (!h.is_stablecoin) {
      const instId = `${h.ccy}-USDT`
      // 避免重复订阅当前选中的交易对
      if (instId !== selectedSymbol.value) {
        marketWS.subscribe(instId, onHoldingPriceUpdate)
      }
    }
  }
}

// 取消订阅持仓币种价格
const unsubscribeHoldingPrices = () => {
  if (!marketWS.isConnected) return

  for (const h of holdingsBase.value) {
    if (!h.is_stablecoin) {
      const instId = `${h.ccy}-USDT`
      if (instId !== selectedSymbol.value) {
        marketWS.unsubscribe(instId, onHoldingPriceUpdate)
      }
    }
  }
}

// 获取现货持仓（优化版：使用轻量API + WebSocket实时价格）
const fetchSpotHoldings = async () => {
  try {
    // 使用轻量版 API（不查行情）
    const res = await api.getHoldingsBase(props.mode)
    const oldHoldings = holdingsBase.value

    holdingsBase.value = res.holdings || []

    // 如果持仓币种变化，重新订阅 WebSocket
    const oldCcys = new Set(oldHoldings.filter(h => !h.is_stablecoin).map(h => h.ccy))
    const newCcys = new Set(holdingsBase.value.filter(h => !h.is_stablecoin).map(h => h.ccy))
    const hasChange = oldCcys.size !== newCcys.size || [...newCcys].some(c => !oldCcys.has(c))

    if (hasChange && marketWS.isConnected) {
      // 取消旧订阅
      for (const ccy of oldCcys) {
        const instId = `${ccy}-USDT`
        if (instId !== selectedSymbol.value) {
          marketWS.unsubscribe(instId, onHoldingPriceUpdate)
        }
      }
      // 添加新订阅
      subscribeHoldingPrices()
    }

    // 立即计算一次（使用已缓存的价格）
    recalcHoldings()
  } catch (e) {
    console.error('获取现货持仓失败:', e)
    holdingsBase.value = []
    spotHoldings.value = []
    totalValueUsdt.value = '0'
    totalValueWithCost.value = '0'
    totalCostUsdt.value = '0'
    totalFeeUsdt.value = '0'
    totalPnlUsdt.value = '0'
    totalPnlPercent.value = '0'
  }
}

// 获取当前委托（根据交易类型请求对应的inst_type）
const fetchPendingOrders = async () => {
  try {
    // 根据当前交易类型确定 inst_type
    let instType = 'SPOT'
    if (tradeType.value === 'swap') {
      instType = 'SWAP'
    } else if (tradeType.value === 'futures') {
      instType = 'FUTURES'
    }
    const res = await api.getOrders(instType, '', props.mode)
    pendingOrders.value = res.orders || []
  } catch (e) {
    console.error('获取委托失败:', e)
    pendingOrders.value = []
  }
}

// 获取成交记录（根据交易类型请求对应的inst_type）
const fetchFills = async () => {
  try {
    // 根据当前交易类型确定 inst_type
    let instType = 'SPOT'
    if (tradeType.value === 'swap') {
      instType = 'SWAP'
    } else if (tradeType.value === 'futures') {
      instType = 'FUTURES'
    }
    const res = await api.getFills(instType, '', 50, props.mode)
    fills.value = res.fills || []
  } catch (e) {
    console.error('获取成交记录失败:', e)
    fills.value = []
  }
}

// 下单
const placeOrder = async (side) => {
  if (isModeLocked.value) {
    orderResult.value = { success: false, message: buildModeLockMessage() }
    return
  }
  if (!orderForm.size) {
    orderResult.value = { success: false, message: '请输入数量' }
    return
  }

  if (orderForm.order_type === 'limit' && !orderForm.price) {
    orderResult.value = { success: false, message: '限价单请输入价格' }
    return
  }

  orderLoading.value = true
  orderResult.value = null

  try {
    const res = await api.placeOrder({
      inst_id: selectedSymbol.value,
      side: side,
      order_type: orderForm.order_type,
      size: orderForm.size,
      price: orderForm.price || '',
      mode: props.mode
    })

    if (res.success) {
      orderResult.value = {
        success: true,
        message: `${side === 'buy' ? '买入' : '卖出'}订单已提交，订单号: ${res.order_id}`
      }
      // 清空表单
      orderForm.size = ''
      orderForm.price = ''
      // WebSocket 会自动推送订单和账户更新
      // 备用：如果 WebSocket 未连接，手动刷新
      if (!wsConnected.value) {
        setTimeout(() => {
          fetchPendingOrders()
          fetchAccountBalance()
        }, 1000)
      }
    } else {
      orderResult.value = {
        success: false,
        message: `下单失败: ${res.error_message || '未知错误'}`
      }
    }
  } catch (e) {
    orderResult.value = {
      success: false,
      message: `下单失败: ${getErrorDetail(e)}`
    }
  } finally {
    orderLoading.value = false
  }
}

// 撤单
const cancelOrder = async (order) => {
  if (isModeLocked.value) {
    alert(buildModeLockMessage())
    return
  }
  cancelingOrderId.value = order.ord_id

  try {
    const res = await api.cancelOrder(order.ord_id, order.inst_id, props.mode)
    if (res.success) {
      // WebSocket 会自动推送订单状态更新
      // 备用：如果 WebSocket 未连接，手动刷新
      if (!wsConnected.value) {
        await fetchPendingOrders()
      }
    } else {
      alert(`撤单失败: ${res.error_message || '未知错误'}`)
    }
  } catch (e) {
    alert(`撤单失败: ${getErrorDetail(e)}`)
  } finally {
    cancelingOrderId.value = null
  }
}

// 下单前确认
const confirmOrder = (side) => {
  if (isModeLocked.value) {
    orderResult.value = { success: false, message: buildModeLockMessage() }
    return
  }
  if (!orderForm.size) {
    orderResult.value = { success: false, message: '请输入数量' }
    return
  }

  if (orderForm.order_type === 'limit' && !orderForm.price) {
    orderResult.value = { success: false, message: '限价单请输入价格' }
    return
  }

  // 设置待确认订单信息
  pendingOrder.value = {
    inst_id: selectedSymbol.value,
    side,
    order_type: orderForm.order_type,
    size: orderForm.size,
    price: orderForm.price || (currentPrice.value?.last || ''),
    estimated: estimatedAmount.value
  }
  showConfirmDialog.value = true
}

// 确认后执行下单
const executeOrder = async () => {
  showConfirmDialog.value = false
  if (pendingOrder.value) {
    if (isModeLocked.value) {
      orderResult.value = { success: false, message: buildModeLockMessage() }
      pendingOrder.value = null
      return
    }
    await placeOrder(pendingOrder.value.side)
    pendingOrder.value = null
    // 刷新最大可交易数量
    fetchMaxSize()
  }
}

// 取消确认
const cancelConfirm = () => {
  showConfirmDialog.value = false
  pendingOrder.value = null
}

// ========== 合约交易方法 ==========

// 切换交易类型
const switchTradeType = (type) => {
  if (tradeType.value === type) return
  tradeType.value = type
  // 切换交易类型时刷新最大可交易量
  fetchMaxSize()
  // 切换交易类型时刷新委托和成交记录（不同交易类型有不同的订单）
  fetchPendingOrders()
  fetchFills()
  // 如果切换到合约，获取杠杆设置
  if (type !== 'spot') {
    fetchContractAccountConfig()
    fetchContractLeverage()
    fetchContractPositions()
  }
}

// 获取合约账户配置（持仓模式等）
const fetchContractAccountConfig = async () => {
  try {
    const res = await api.getContractAccountConfig(props.mode)
    if (res && res.pos_mode) {
      contractPosMode.value = res.pos_mode
    }
  } catch (e) {
    console.error('获取账户配置失败:', e)
  }
}

// 根据当前页面的合约方向/持仓模式，推导下单/杠杆接口所需的 posSide
const getDesiredContractPosSide = () => {
  if (contractPosMode.value === 'net_mode') return 'net'
  // open_long/close_long -> long；open_short/close_short -> short
  return contractSide.value.endsWith('long') ? 'long' : 'short'
}

// 设置杠杆
const setLeverage = async (lever) => {
  if (isModeLocked.value) {
    orderResult.value = { success: false, message: buildModeLockMessage() }
    return
  }
  try {
    const posSide = contractSettings.marginMode === 'isolated' ? getDesiredContractPosSide() : ''
    const res = await api.setContractLeverage(
      contractInstId.value,
      String(lever),
      contractSettings.marginMode,
      posSide,
      props.mode
    )
    if (res.success) {
      contractSettings.leverage = lever
      orderResult.value = { success: true, message: `杠杆已设置为 ${lever}x` }
      // 刷新最大可开仓量
      fetchMaxSize()
    } else {
      orderResult.value = { success: false, message: res.message || '设置杠杆失败' }
    }
  } catch (e) {
    console.error('设置杠杆失败:', e)
    orderResult.value = { success: false, message: '设置杠杆失败: ' + getErrorDetail(e) }
  }
}

// 获取合约杠杆设置
const fetchContractLeverage = async () => {
  try {
    const res = await api.getContractLeverage(contractInstId.value, contractSettings.marginMode, props.mode)
    if (res.success && res.data?.length > 0) {
      const desiredPosSide = getDesiredContractPosSide()
      const leverData = res.data.find(d => (d.posSide || '').toLowerCase() === desiredPosSide) || res.data[0]
      contractSettings.leverage = parseInt(leverData.lever) || 10
    }
  } catch (e) {
    console.error('获取杠杆设置失败:', e)
  }
}

// 获取合约持仓
const fetchContractPositions = async () => {
  try {
    const instType = tradeType.value === 'swap' ? 'SWAP' : 'FUTURES'
    const res = await api.getContractPositions(instType, '', props.mode)
    if (res.positions) {
      contractPositions.value = res.positions
    }
  } catch (e) {
    console.error('获取合约持仓失败:', e)
  }
}

// 合约下单确认
const confirmContractOrder = () => {
  if (isModeLocked.value) {
    orderResult.value = { success: false, message: buildModeLockMessage() }
    return
  }
  if (!orderForm.size) {
    orderResult.value = { success: false, message: '请输入数量' }
    return
  }

  if (orderForm.order_type === 'limit' && !orderForm.price) {
    orderResult.value = { success: false, message: '限价单请输入价格' }
    return
  }

  // 显示确认弹窗
  pendingContractOrder.value = {
    inst_id: contractInstId.value,
    side: contractSide.value,
    sideText: contractSideText.value,
    order_type: orderForm.order_type,
    size: orderForm.size,
    price: orderForm.price || (currentPrice.value?.last || ''),
    leverage: contractSettings.leverage,
    marginMode: contractSettings.marginMode === 'cross' ? '全仓' : '逐仓'
  }
  showContractConfirmDialog.value = true
}

// 取消合约下单确认
const cancelContractConfirm = () => {
  showContractConfirmDialog.value = false
  pendingContractOrder.value = null
}

// 执行合约下单
const executeContractOrder = async () => {
  showContractConfirmDialog.value = false
  if (isModeLocked.value) {
    orderResult.value = { success: false, message: buildModeLockMessage() }
    return
  }
  orderLoading.value = true
  orderResult.value = null

  // 解析合约方向
  let side
  const posSide = getDesiredContractPosSide()
  switch (contractSide.value) {
    case 'open_long':
      side = 'buy'
      break
    case 'open_short':
      side = 'sell'
      break
    case 'close_long':
      side = 'sell'
      break
    case 'close_short':
      side = 'buy'
      break
    default:
      orderResult.value = { success: false, message: '无效的操作方向' }
      orderLoading.value = false
      return
  }

  const isClose = contractSide.value.startsWith('close')

  try {
    const res = await api.placeContractOrder({
      instId: contractInstId.value,
      side,
      posSide,
      orderType: orderForm.order_type,
      size: orderForm.size,
      price: orderForm.price,
      tdMode: contractSettings.marginMode,
      reduceOnly: isClose,
      mode: props.mode
    })

    if (res.success) {
      orderResult.value = {
        success: true,
        message: `${contractSideText.value}成功，订单号: ${res.order_id}`
      }
      // 清空表单
      orderForm.size = ''
      orderForm.price = ''
      // 刷新数据
      fetchMaxSize()
      fetchContractPositions()
      fetchPendingOrders()
    } else {
      orderResult.value = {
        success: false,
        message: res.error_message || '下单失败'
      }
    }
  } catch (e) {
    console.error('合约下单失败:', e)
    orderResult.value = {
      success: false,
      message: '下单失败: ' + getErrorDetail(e)
    }
  } finally {
    orderLoading.value = false
  }
}

// 持仓快捷卖出
const quickSell = (holding) => {
  // 切换到对应交易对
  selectedSymbol.value = `${holding.ccy}-USDT`
  // 设置为卖出方向
  currentSide.value = 'sell'
  // 填入可用数量
  orderForm.size = holding.available
  orderForm.order_type = 'market'
  orderForm.price = ''
  // 滚动到下单区域
  document.querySelector('.order-card')?.scrollIntoView({ behavior: 'smooth' })
}

// 同步成交记录到本地
const syncFills = async () => {
  syncingFills.value = true
  try {
    const res = await api.syncFillsToLocal(props.mode)
    if (res.synced_count !== undefined) {
      alert(`同步成功: ${res.message || `共${res.synced_count}条记录，新增${res.new_count}条`}`)
      // 刷新持仓数据以更新成本
      await fetchSpotHoldings()
    }
  } catch (e) {
    console.error('同步成交记录失败:', e)
    alert('同步失败: ' + getErrorDetail(e))
  } finally {
    syncingFills.value = false
  }
}

// 打开编辑成本弹窗
const openEditCostDialog = (holding) => {
  editingCcy.value = holding.ccy
  // 如果已有成本价，预填到输入框
  editCostValue.value = holding.avg_cost !== '-' ? holding.avg_cost : ''
  showEditCostDialog.value = true
}

// 关闭编辑成本弹窗
const closeEditCostDialog = () => {
  showEditCostDialog.value = false
  editingCcy.value = ''
  editCostValue.value = ''
}

// 保存成本基础
const saveCostBasis = async () => {
  if (!editCostValue.value || parseFloat(editCostValue.value) <= 0) {
    alert('请输入有效的成本价')
    return
  }

  savingCost.value = true
  try {
    await api.updateCostBasis({
      ccy: editingCcy.value,
      avgCost: parseFloat(editCostValue.value),
      mode: props.mode
    })
    closeEditCostDialog()
    // 刷新持仓数据以更新盈亏
    await fetchSpotHoldings()
  } catch (e) {
    console.error('保存成本失败:', e)
    alert('保存失败: ' + (e.message || '网络错误'))
  } finally {
    savingCost.value = false
  }
}

// 获取盈亏样式类
const getPnlClass = (val) => {
  if (val === '-' || val === '0' || val === null || val === undefined) return ''
  const num = parseFloat(val)
  if (isNaN(num)) return ''
  if (num > 0) return 'profit'
  if (num < 0) return 'loss'
  return ''
}

// 格式化盈亏百分比
const formatPnl = (val) => {
  if (val === '-' || val === '0' || val === null || val === undefined) return '-'
  const num = parseFloat(val)
  if (isNaN(num)) return '-'
  return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
}

// 点击外部关闭下拉框
const handleClickOutside = (e) => {
  const dropdown = document.querySelector('.dropdown-select')
  if (dropdown && !dropdown.contains(e.target)) {
    symbolDropdownOpen.value = false
  }
}

// 自动刷新定时器
let refreshTimer = null
let priceRefreshTimer = null

// WebSocket 价格更新回调
const onPriceUpdate = (data) => {
  if (data.instId === selectedSymbol.value) {
    currentPrice.value = {
      last: data.last,
      askPx: data.askPx,
      bidPx: data.bidPx,
      open24h: data.open24h,
      high24h: data.high24h,
      low24h: data.low24h,
      vol24h: data.vol24h,
      change24h: data.change24h,
      timestamp: data.timestamp,
    }
    // 同时更新 holdingPrices 缓存（如果是持仓币种）
    const ccy = data.instId.split('-')[0]
    const price = parseFloat(data.last) || 0
    if (price > 0 && holdingsBase.value.some(h => h.ccy === ccy)) {
      holdingPrices[ccy] = price
      recalcHoldings()
    }
  }
}

// WebSocket 账户更新回调
const onAccountUpdate = (accountData, wsMode) => {
  // 过滤：只处理与当前页面模式匹配的推送
  if (wsMode && wsMode !== props.mode) {
    console.log(`[WS] 忽略账户更新 (模式不匹配: ws=${wsMode}, page=${props.mode})`)
    return
  }
  console.log('[WS] 收到账户更新:', accountData)
  // accountData 是 { ccy: { ccy, cashBal, availBal, frozenBal, eqUsd, uTime } } 格式
  // 转换为 accountBalance 所需格式
  const details = []
  let totalEquity = 0

  for (const ccy in accountData) {
    const item = accountData[ccy]
    const eqUsd = parseFloat(item.eqUsd) || 0
    totalEquity += eqUsd
    details.push({
      ccy: item.ccy,
      avail_bal: item.availBal || '0',
      frozen_bal: item.frozenBal || '0',
      cash_bal: item.cashBal || '0',
      eq_usd: item.eqUsd || '0',
    })
  }

  accountBalance.total_equity = totalEquity.toFixed(2)
  accountBalance.details = details

  // 优化：本地更新 holdingsBase 的余额部分，而非重新调用 API
  let holdingsChanged = false
  for (const ccy in accountData) {
    const item = accountData[ccy]
    const existingHolding = holdingsBase.value.find(h => h.ccy === ccy)
    if (existingHolding) {
      // 更新已有持仓的余额
      existingHolding.available = item.availBal || '0'
      existingHolding.frozen = item.frozenBal || '0'
      existingHolding.total = String(
        (parseFloat(item.availBal) || 0) + (parseFloat(item.frozenBal) || 0)
      )
      holdingsChanged = true
    } else {
      // 新增币种，需要调用 API 获取完整数据（包含成本）
      holdingsChanged = true
      fetchSpotHoldings()
      return
    }
  }

  if (holdingsChanged) {
    recalcHoldings()
  }

  // 刷新最大可交易量
  fetchMaxSize()
}

// 根据 OKX 推送的 instType 映射到页面 tradeType
const mapInstTypeToTradeType = (instType) => {
  const t = (instType || '').toUpperCase()
  if (t === 'SPOT') return 'spot'
  if (t === 'SWAP') return 'swap'
  if (t === 'FUTURES') return 'futures'
  return null
}

// WebSocket 订单更新回调
const onOrderUpdate = (orderData, wsMode) => {
  // 过滤：只处理与当前页面模式匹配的推送
  if (wsMode && wsMode !== props.mode) {
    console.log(`[WS] 忽略订单更新 (模式不匹配: ws=${wsMode}, page=${props.mode})`)
    return
  }

  const instType = orderData.instType
  const orderTradeType = mapInstTypeToTradeType(instType)
  // 过滤：只处理当前页面交易类型对应的订单推送，避免现货/合约互相污染列表
  if (orderTradeType && orderTradeType !== tradeType.value) {
    console.log(`[WS] 忽略订单更新 (instType=${instType}, tradeType=${tradeType.value})`)
    return
  }

  console.log('[WS] 收到订单更新:', orderData)
  // orderData 是单个订单对象
  const existingIndex = pendingOrders.value.findIndex(o => o.ord_id === orderData.ordId)

  // 转换字段名
  const order = {
    ord_id: orderData.ordId,
    inst_id: orderData.instId,
    side: orderData.side,
    ord_type: orderData.ordType,
    px: orderData.px,
    sz: orderData.sz,
    fill_sz: orderData.fillSz || orderData.accFillSz || '0',
    state: orderData.state,
    c_time: orderData.cTime,
    u_time: orderData.uTime,
  }

  // 如果是完全成交或已撤销，从当前委托中移除
  if (['filled', 'canceled', 'mmp_canceled'].includes(order.state)) {
    if (existingIndex >= 0) {
      pendingOrders.value.splice(existingIndex, 1)
    }
    // 订单完成后刷新对应持仓（现货/合约），避免“成交了但仓位不更新”的误判
    if (orderTradeType === 'spot') {
      Promise.all([fetchSpotHoldings(), fetchAccountBalance()])
    } else {
      Promise.all([fetchContractPositions(), fetchMaxSize()])
    }
  } else {
    // 更新或添加到当前委托
    if (existingIndex >= 0) {
      pendingOrders.value[existingIndex] = order
    } else {
      pendingOrders.value.unshift(order)
    }
  }
}

// WebSocket 成交更新回调
const onFillUpdate = (fillData, wsMode) => {
  // 过滤：只处理与当前页面模式匹配的推送
  if (wsMode && wsMode !== props.mode) {
    console.log(`[WS] 忽略成交更新 (模式不匹配: ws=${wsMode}, page=${props.mode})`)
    return
  }

  const instType = fillData.instType
  const fillTradeType = mapInstTypeToTradeType(instType)
  // 过滤：只处理当前页面交易类型对应的成交推送
  if (fillTradeType && fillTradeType !== tradeType.value) {
    console.log(`[WS] 忽略成交更新 (instType=${instType}, tradeType=${tradeType.value})`)
    return
  }

  console.log('[WS] 收到成交更新:', fillData)
  // fillData 是单个成交对象
  const fill = {
    trade_id: fillData.tradeId,
    inst_id: fillData.instId,
    side: fillData.side,
    fill_px: fillData.fillPx,
    fill_sz: fillData.fillSz,
    fee: fillData.fee,
    fee_ccy: fillData.feeCcy,
    ts: fillData.ts,
  }

  // 检查是否已存在
  const exists = fills.value.some(f => f.trade_id === fill.trade_id)
  if (!exists) {
    fills.value.unshift(fill)
    // 保留最近 50 条
    if (fills.value.length > 50) {
      fills.value = fills.value.slice(0, 50)
    }
    // 成交后刷新对应持仓（现货/合约）
    if (fillTradeType === 'spot') {
      fetchSpotHoldings()
    } else {
      fetchContractPositions()
      fetchMaxSize()
    }
  }
}

// 初始化 WebSocket 连接
const initWebSocket = async () => {
  try {
    // 重要：私有通道订阅需要携带 mode，避免模拟盘/实盘页面收不到对应推送
    marketWS.setMode(props.mode)
    await marketWS.connect()
    wsConnected.value = marketWS.isConnected

    // 订阅当前交易对行情
    marketWS.subscribe(selectedSymbol.value, onPriceUpdate)

    // 订阅所有持仓币种的价格
    subscribeHoldingPrices()

    // 订阅私有通道（账户、订单、成交）
    marketWS.subscribeAccount(onAccountUpdate)
    marketWS.subscribeOrders(onOrderUpdate)
    marketWS.subscribeFills(onFillUpdate)

    console.log('[WS] 已订阅所有通道: ticker, holdings-tickers, account, orders, fills')
  } catch (e) {
    console.error('WebSocket 连接失败:', e)
    wsConnected.value = false
  }
}

// 清理 WebSocket 订阅
const cleanupWebSocket = () => {
  if (marketWS.isConnected) {
    marketWS.unsubscribe(selectedSymbol.value, onPriceUpdate)
    unsubscribeHoldingPrices()
    marketWS.unsubscribeAccount(onAccountUpdate)
    marketWS.unsubscribeOrders(onOrderUpdate)
    marketWS.unsubscribeFills(onFillUpdate)
  }
}

// 监听交易对变化
watch(selectedSymbol, (newSymbol, oldSymbol) => {
  // 取消旧交易对订阅
  if (marketWS.isConnected && oldSymbol) {
    marketWS.unsubscribe(oldSymbol, onPriceUpdate)
  }
  // 订阅新交易对
  if (marketWS.isConnected && newSymbol) {
    marketWS.subscribe(newSymbol, onPriceUpdate)
  }
  // 同时获取一次 HTTP 价格（作为初始值）
  fetchCurrentPrice()
  fetchMaxSize()
  // 持久化保存
  if (settingsLoaded.value) debouncedSave()
})

// 合约保证金模式切换：需要刷新杠杆与最大可开仓量，避免 UI 显示旧数据
watch(() => contractSettings.marginMode, () => {
  if (tradeType.value !== 'spot') {
    fetchContractLeverage()
    fetchMaxSize()
  }
})

// 合约方向切换：逐仓/双向持仓可能多空杠杆不同；同时 max size 也依赖方向
watch(contractSide, () => {
  if (tradeType.value !== 'spot') {
    fetchContractLeverage()
    fetchMaxSize()
  }
})

// 监听可用交易对变化（用户添加/删除时持久化）
watch(availableSymbols, () => {
  if (settingsLoaded.value) debouncedSave()
}, { deep: true })

// 监听交易模式变化（模拟盘/实盘切换时重载数据）
watch(() => props.mode, async (newMode, oldMode) => {
  if (!isInitialized || newMode === oldMode) return

  console.log(`[TradingView] 模式切换: ${oldMode} -> ${newMode}`)
  marketWS.setMode(newMode)

  // 重置状态
  spotHoldings.value = []
  holdingsBase.value = []
  pendingOrders.value = []
  fills.value = []
  Object.keys(holdingPrices).forEach(k => delete holdingPrices[k])

  // 重新加载所有数据
  await refreshAll()

  // 更新持仓币种列表
  const holdingPairs = spotHoldings.value
    .filter(h => !h.is_stablecoin && parseFloat(h.total || '0') > 0)
    .map(h => `${h.ccy}-USDT`)
  holdingSymbols.value = [...holdingPairs]

  // 重新订阅 WebSocket（私有通道会根据新模式获取数据）
  if (marketWS.isConnected) {
    subscribeHoldingPrices()
  }

  // 刷新当前价格和最大交易量
  fetchCurrentPrice()
  fetchMaxSize()
})

// 是否已初始化（用于区分首次挂载和从缓存激活）
let isInitialized = false

onMounted(async () => {
  // 先加载用户设置（交易对列表等）
  await loadSettings()

  // 初次加载数据 - 刷新持仓
  await refreshAll()

  // 从持仓中提取非稳定币
  const holdingPairs = []
  if (spotHoldings.value && spotHoldings.value.length > 0) {
    spotHoldings.value
      .filter(h => !h.is_stablecoin && parseFloat(h.total || '0') > 0)
      .forEach(h => holdingPairs.push(`${h.ccy}-USDT`))
  }

  // 记录持仓币种（用于锁定，不可删除）
  holdingSymbols.value = [...holdingPairs]

  // 将持仓币种加入可选列表（确保可选，但不强制覆盖用户设置）
  const existing = new Set(availableSymbols.value)
  holdingPairs.forEach(s => {
    if (!existing.has(s)) {
      availableSymbols.value.push(s)
    }
  })

  // 如果可选列表仍为空（首次使用），从持仓初始化
  if (availableSymbols.value.length === 0 && holdingPairs.length > 0) {
    availableSymbols.value = [...holdingPairs]
  }

  // 如果没有加载到有效的 selectedSymbol，使用第一个持仓或第一个可选
  if (!availableSymbols.value.includes(selectedSymbol.value)) {
    if (holdingPairs.length > 0) {
      selectedSymbol.value = holdingPairs[0]
    } else if (availableSymbols.value.length > 0) {
      selectedSymbol.value = availableSymbols.value[0]
    }
  }

  // 并行加载价格和最大可交易数量
  Promise.all([
    fetchCurrentPrice(),
    fetchMaxSize()
  ])
  document.addEventListener('click', handleClickOutside)

  // 初始化 WebSocket（行情 + 账户 + 订单 + 成交）
  initWebSocket()

  // 备用定时器：仅在 WebSocket 未连接时通过 HTTP 刷新
  // 价格每 10 秒刷新，订单每 30 秒刷新
  // 持仓和余额通过 WebSocket 账户推送实时更新，无需轮询
  priceRefreshTimer = setInterval(() => {
    if (tradingStatus.api_configured && !wsConnected.value) {
      fetchCurrentPrice()
    }
  }, 10000)

  refreshTimer = setInterval(() => {
    if (tradingStatus.api_configured && !wsConnected.value) {
      Promise.all([fetchPendingOrders(), fetchAccountBalance(), fetchSpotHoldings()])
    }
  }, 30000)

  isInitialized = true
})

// keep-alive 激活时调用（从其他页面切换回来）
onActivated(() => {
  // 首次挂载时 onMounted 已经处理，跳过
  if (!isInitialized) return

  // 重新添加事件监听
  document.addEventListener('click', handleClickOutside)

  // 重新订阅 WebSocket（订阅使用 Set，重复调用是安全的）
  if (wsConnected.value) {
    marketWS.subscribe(selectedSymbol.value, onPriceUpdate)
    subscribeHoldingPrices()
    marketWS.subscribeAccount(onAccountUpdate)
    marketWS.subscribeOrders(onOrderUpdate)
    marketWS.subscribeFills(onFillUpdate)
  } else {
    initWebSocket()
  }

  // 重新启动定时器（仅在 WebSocket 断连时作为备用）
  if (!priceRefreshTimer) {
    priceRefreshTimer = setInterval(() => {
      if (tradingStatus.api_configured && !wsConnected.value) {
        fetchCurrentPrice()
      }
    }, 10000)
  }

  if (!refreshTimer) {
    refreshTimer = setInterval(() => {
      if (tradingStatus.api_configured && !wsConnected.value) {
        Promise.all([fetchPendingOrders(), fetchAccountBalance(), fetchSpotHoldings()])
      }
    }, 30000)
  }

  // 仅刷新实时价格（其他数据通过 WebSocket 推送，保持缓存）
  fetchCurrentPrice()
})

// keep-alive 停用时调用（切换到其他页面）
onDeactivated(() => {
  // 移除事件监听
  document.removeEventListener('click', handleClickOutside)

  // 清理定时器（节省资源）
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (priceRefreshTimer) {
    clearInterval(priceRefreshTimer)
    priceRefreshTimer = null
  }

  // 清理 WebSocket 订阅（避免后台组件响应更新导致错误）
  cleanupWebSocket()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (priceRefreshTimer) {
    clearInterval(priceRefreshTimer)
  }
  // 清理 WebSocket 订阅
  cleanupWebSocket()
})
</script>

<style scoped>
.trading-view {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
  contain: layout style;
}

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 14px 20px;
  background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 下拉选择框 */
.dropdown-select {
  position: relative;
}

.dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  min-width: 160px;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.dropdown-trigger:hover {
  border-color: var(--accent-color);
  box-shadow: 0 0 12px var(--accent-glow);
}

.dropdown-label {
  color: var(--text-secondary);
  font-size: 12px;
}

.dropdown-value {
  color: var(--text-primary);
  font-weight: 600;
}

.dropdown-arrow {
  margin-left: auto;
  color: var(--text-secondary);
  font-size: 10px;
  transition: transform var(--transition-fast);
}

.dropdown-select:hover .dropdown-arrow {
  color: var(--accent-color);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 220px;
  max-height: 320px;
  overflow-y: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 100;
}

.dropdown-search {
  padding: 10px;
  border-bottom: 1px solid var(--border-color);
}

.dropdown-search input {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.dropdown-search input:focus {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-bg);
  outline: none;
}

.dropdown-list {
  max-height: 260px;
  overflow-y: auto;
}

.dropdown-add {
  padding: 10px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  gap: 8px;
}

.dropdown-add input {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 12px;
}

.btn-add {
  padding: 8px 14px;
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn-add:hover {
  box-shadow: var(--shadow-glow);
  transform: translateY(-1px);
}

.dropdown-item {
  padding: 10px 14px;
  cursor: pointer;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.dropdown-item .symbol-text {
  flex: 1;
}

.dropdown-item .lock-icon {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--accent-bg);
  color: var(--accent-color);
  border-radius: var(--radius-sm);
  margin-left: 8px;
}

.dropdown-item .btn-remove {
  display: none;
  padding: 3px 8px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 10px;
  margin-left: 8px;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.dropdown-item:hover .btn-remove {
  display: inline-block;
}

.dropdown-item .btn-remove:hover {
  background: var(--color-danger);
  color: #fff;
  border-color: var(--color-danger);
}

.dropdown-item.locked {
  background: var(--accent-bg);
}

.dropdown-item:hover {
  background: var(--bg-hover);
}

.dropdown-item.active {
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  color: #fff;
}

/* 模式指示器 */
.mode-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.default-mode-hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.mode-tag {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mode-tag.locked {
  opacity: 0.85;
}

.mode-lock-flag {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 9px;
  letter-spacing: 0.4px;
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.mode-tag.simulated {
  background: var(--accent-bg);
  color: var(--accent-color);
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.mode-tag.live {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
  animation: pulse 2s ease-in-out infinite;
}

/* 页面标题 */
.page-title {
  display: flex;
  align-items: center;
}

.title-text {
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--text-primary) 0%, var(--text-secondary) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* API 警告 */
.api-warning {
  text-align: center;
  padding: 60px 40px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
}

.api-warning h3 {
  color: var(--color-warning);
  margin-bottom: 16px;
  font-size: 18px;
}

.api-warning p {
  color: var(--text-secondary);
  margin-bottom: 24px;
}

/* 主布局 */
.trading-wrapper {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.trading-layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
}

/* 模式锁提示卡片：只读查看 + 禁止交易动作 */
.mode-lock-warning {
  border-color: rgba(239, 68, 68, 0.35);
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.10) 0%, var(--bg-secondary) 70%);
}

.mode-lock-warning p {
  margin: 0 0 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* 卡片 */
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 20px;
  transition: border-color 0.2s ease;
}

.card:hover {
  border-color: rgba(245, 158, 11, 0.3);
  box-shadow: 0 0 20px rgba(245, 158, 11, 0.05);
}

.card h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 8px;
}

.card h3::before {
  content: '';
  width: 3px;
  height: 14px;
  background: linear-gradient(180deg, var(--accent-color) 0%, var(--secondary-color) 100%);
  border-radius: 2px;
}

/* 卡片标题带信息 */
.card-header-with-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-color);
}

.card-header-with-info h3 {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.total-value {
  font-size: 15px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--secondary-color) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 现货持仓表格样式 */
.ccy-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ccy-name {
  font-weight: 600;
}

.stable-tag {
  font-size: 10px;
  padding: 3px 8px;
  background: var(--accent-bg);
  color: var(--accent-color);
  border-radius: 10px;
  font-weight: 500;
}

tr.stablecoin {
  background: rgba(245, 158, 11, 0.03);
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 账户信息 */
.account-info .info-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}

.account-info .label {
  color: var(--text-secondary);
}

.account-info .value {
  color: var(--text-primary);
  font-weight: 700;
  font-size: 20px;
}

.balance-details {
  margin-top: 14px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-size: 13px;
}

.detail-item .ccy {
  color: var(--text-primary);
  font-weight: 600;
}

.detail-item .amounts {
  display: flex;
  gap: 14px;
  color: var(--text-secondary);
}

/* 下单表单 */
.form-group {
  margin-bottom: 18px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.input, .select {
  width: 100%;
  padding: 12px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  font-family: var(--font-family);
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.input:focus, .select:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-bg);
}

.input-with-info {
  position: relative;
}

.input-with-info .input {
  padding-right: 55px;
}

.input-suffix {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.quick-amounts {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.quick-btn {
  flex: 1;
  padding: 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.quick-btn:hover {
  background: var(--accent-bg);
  color: var(--accent-color);
  border-color: rgba(245, 158, 11, 0.3);
}

/* 下单按钮 */
.order-buttons {
  margin-top: 24px;
}

.order-buttons .btn {
  width: 100%;
}

.btn-buy {
  background: linear-gradient(135deg, var(--color-success) 0%, #16A34A 100%);
  color: #fff;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.btn-buy:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
  transform: translateY(-1px);
}

.btn-sell {
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
  color: #fff;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.btn-sell:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
  transform: translateY(-1px);
}

/* 订单结果 */
.order-result {
  margin-top: 14px;
  padding: 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
}

.order-result.success {
  background: rgba(34, 197, 94, 0.1);
  color: var(--color-success);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.order-result.error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 表格容器 */
.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th, td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

th {
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: var(--bg-tertiary);
}

td {
  color: var(--text-primary);
}

tbody tr {
  transition: background var(--transition-fast);
}

tbody tr:hover {
  background: var(--bg-hover);
}

/* 方向样式 */
td.buy {
  color: var(--color-success);
  font-weight: 600;
}

td.sell {
  color: var(--color-danger);
  font-weight: 600;
}

/* 盈亏样式 */
.profit {
  color: var(--color-success);
  font-weight: 600;
}

.loss {
  color: var(--color-danger);
  font-weight: 600;
}

/* 无数据 */
.no-data {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

/* 按钮 */
.btn {
  padding: 10px 18px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.btn-primary:hover:not(:disabled) {
  box-shadow: var(--shadow-glow);
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--text-muted);
}

.btn-small {
  padding: 6px 12px;
  font-size: 12px;
}

.btn-danger {
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
  color: #fff;
}

.btn-danger:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
  transform: translateY(-1px);
}

/* 响应式 */
@media (max-width: 1024px) {
  .trading-layout {
    grid-template-columns: 1fr;
  }

  .left-panel {
    order: 1;
  }

  .right-panel {
    order: 2;
  }
}

/* 当前价格显示 */
.current-price-info {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  margin-bottom: 18px;
}

.current-price-info.loading {
  justify-content: center;
}

.price-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.price-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.price-change {
  font-size: 14px;
  font-weight: 600;
}

/* 买卖方向选择 */
.side-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 18px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.side-tab {
  flex: 1;
  padding: 12px;
  background: var(--bg-tertiary);
  border: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.side-tab:hover {
  background: var(--bg-hover);
}

.side-tab.active.buy {
  background: linear-gradient(135deg, var(--color-success) 0%, #16A34A 100%);
  color: #fff;
  box-shadow: inset 0 0 20px rgba(255, 255, 255, 0.1);
}

.side-tab.active.sell {
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
  color: #fff;
  box-shadow: inset 0 0 20px rgba(255, 255, 255, 0.1);
}

/* 可买可卖数量 */
.max-size-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.max-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.max-label {
  color: var(--text-muted);
}

.max-value {
  color: var(--text-secondary);
  font-weight: 500;
}

.max-divider {
  color: var(--border-color);
}

/* 预估金额 */
.estimated-amount {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-top: 14px;
}

.estimated-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.estimated-value {
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--secondary-color) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 确认弹窗 */
.confirm-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-dialog {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  padding: 28px;
  min-width: 360px;
  max-width: 420px;
  box-shadow: var(--shadow-lg);
}

.confirm-dialog h3 {
  margin: 0 0 24px 0;
  padding: 0;
  border: none;
  text-align: center;
  font-size: 20px;
  font-weight: 700;
}

.confirm-dialog h3::before {
  display: none;
}

.confirm-content {
  margin-bottom: 28px;
}

.confirm-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}

.confirm-row:last-child {
  border-bottom: none;
}

.confirm-row.highlight {
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  margin: 14px -14px 0;
  padding: 14px;
  border-radius: var(--radius-md);
  border-bottom: none;
}

.confirm-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.confirm-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-value.buy {
  color: var(--color-success);
}

.confirm-value.sell {
  color: var(--color-danger);
}

.confirm-buttons {
  display: flex;
  gap: 14px;
}

.confirm-buttons .btn {
  flex: 1;
  padding: 14px;
}

/* 合约确认弹窗 */
.contract-confirm .contract-warning {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 18px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--radius-md);
  color: var(--accent-color);
  font-size: 13px;
}

.contract-warning .warning-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(245, 158, 11, 0.2);
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.confirm-value.highlight-lever {
  color: var(--accent-color);
  font-weight: 700;
}

.confirm-value.open_long {
  color: var(--color-success);
}

.confirm-value.open_short,
.confirm-value.close_long {
  color: var(--color-danger);
}

.confirm-value.close_short {
  color: var(--color-success);
}

/* 无操作 */
.no-action {
  color: var(--text-muted);
}

/* 持仓卡片头部信息 */
.header-info {
  display: flex;
  align-items: center;
  gap: 18px;
}

.total-pnl {
  font-size: 14px;
  font-weight: 700;
}

/* 幽灵按钮 */
.btn-ghost {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.btn-ghost:hover:not(:disabled) {
  background: var(--accent-bg);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

/* 操作列 */
.actions-cell {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 编辑成本弹窗 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  padding: 28px;
  min-width: 360px;
  max-width: 420px;
  box-shadow: var(--shadow-lg);
}

.modal-dialog h3 {
  margin: 0 0 24px 0;
  padding: 0;
  border: none;
  text-align: center;
  font-size: 20px;
  font-weight: 700;
}

.modal-dialog h3::before {
  display: none;
}

.edit-cost-form {
  margin-bottom: 24px;
}

.form-row {
  margin-bottom: 14px;
}

.form-row label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-row input {
  width: 100%;
  padding: 12px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.form-row input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-bg);
}

.edit-cost-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 10px;
}

/* 成本统计信息 */
.cost-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  padding: 14px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 14px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.summary-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.summary-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

/* ========== 交易类型切换 ========== */
.trade-type-switch {
  display: flex;
  gap: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.type-btn {
  padding: 8px 14px;
  background: var(--bg-tertiary);
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.type-btn:hover {
  background: var(--bg-hover);
}

.type-btn.active {
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  color: #fff;
}

.type-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.type-btn .coming-soon {
  font-size: 10px;
  color: var(--text-muted);
}

/* ========== 合约设置区域 ========== */
.contract-settings {
  margin-bottom: 18px;
  padding: 14px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

/* 杠杆选择 */
.leverage-group {
  margin-bottom: 14px;
}

.leverage-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.leverage-btn {
  padding: 8px 12px;
  min-width: 48px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.leverage-btn:hover {
  border-color: var(--accent-color);
  color: var(--text-primary);
}

.leverage-btn.active {
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  border-color: var(--accent-color);
  color: #fff;
}

/* 保证金模式 */
.margin-mode-tabs {
  display: flex;
  gap: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.margin-btn {
  flex: 1;
  padding: 10px 18px;
  background: var(--bg-secondary);
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.margin-btn:hover {
  background: var(--bg-hover);
}

.margin-btn.active {
  background: linear-gradient(135deg, var(--secondary-color) 0%, var(--secondary-hover) 100%);
  color: #fff;
}

/* ========== 合约方向选择 ========== */
.contract-side-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 14px;
}

.contract-side-tab {
  padding: 12px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.contract-side-tab:hover {
  border-color: var(--text-secondary);
}

/* 开多 - 绿色 */
.contract-side-tab.open-long.active {
  background: linear-gradient(135deg, var(--color-success) 0%, #16A34A 100%);
  border-color: var(--color-success);
  color: #fff;
  box-shadow: 0 0 15px rgba(34, 197, 94, 0.3);
}

.contract-side-tab.open-long:hover:not(.active) {
  border-color: var(--color-success);
  color: var(--color-success);
}

/* 开空 - 红色 */
.contract-side-tab.open-short.active {
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
  border-color: var(--color-danger);
  color: #fff;
  box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);
}

.contract-side-tab.open-short:hover:not(.active) {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* 平多 - 浅红色 */
.contract-side-tab.close-long.active {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.8) 0%, rgba(220, 38, 38, 0.8) 100%);
  border-color: var(--color-danger);
  color: #fff;
}

.contract-side-tab.close-long:hover:not(.active) {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* 平空 - 浅绿色 */
.contract-side-tab.close-short.active {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.8) 0%, rgba(22, 163, 74, 0.8) 100%);
  border-color: var(--color-success);
  color: #fff;
}

.contract-side-tab.close-short:hover:not(.active) {
  border-color: var(--color-success);
  color: var(--color-success);
}

/* ========== 合约下单按钮 ========== */
.btn-open-long {
  background: linear-gradient(135deg, var(--color-success) 0%, #16A34A 100%);
  color: #fff;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn-open-long:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
  transform: translateY(-1px);
}

.btn-open-short {
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
  color: #fff;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn-open-short:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
  transform: translateY(-1px);
}

.btn-close-long {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.8) 0%, rgba(220, 38, 38, 0.8) 100%);
  color: #fff;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn-close-long:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--color-danger) 0%, #DC2626 100%);
}

.btn-close-short {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.8) 0%, rgba(22, 163, 74, 0.8) 100%);
  color: #fff;
  padding: 14px;
  font-size: 15px;
  font-weight: 600;
}

.btn-close-short:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--color-success) 0%, #16A34A 100%);
}

/* ========== 合约持仓表格 ========== */
.contract-positions .long-side {
  color: var(--color-success);
  font-weight: 700;
}

.contract-positions .short-side {
  color: var(--color-danger);
  font-weight: 700;
}

.contract-positions .net-side {
  color: var(--color-warning);
  font-weight: 700;
}

.contract-positions .upl-ratio {
  font-size: 12px;
  opacity: 0.8;
  margin-left: 5px;
}
</style>
