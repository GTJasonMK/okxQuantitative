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
    <div v-if="!currentModeConfigured" class="api-warning card">
      <h3>{{ apiWarningTitle }}</h3>
      <p>{{ apiWarningMessage }}</p>
      <div class="api-warning-statuses">
        <span
          class="api-warning-chip"
          :class="{ configured: okxConfigStatus.demoConfigured, active: props.mode === 'simulated' }"
        >
          模拟盘：{{ okxConfigStatus.demoConfigured ? '已配置' : '未配置' }}
        </span>
        <span
          class="api-warning-chip"
          :class="{ configured: okxConfigStatus.liveConfigured, active: props.mode === 'live' }"
        >
          实盘：{{ okxConfigStatus.liveConfigured ? '已配置' : '未配置' }}
        </span>
      </div>
      <div class="api-warning-actions">
        <router-link
          v-if="otherModeConfigured"
          :to="otherModeRoute"
          class="btn btn-secondary"
        >
          切换到{{ otherModeText }}
        </router-link>
        <router-link to="/settings" class="btn btn-primary">前往设置</router-link>
      </div>
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

      <!-- 右侧：tab 切换（持仓 | 委托 | 成交） -->
      <div class="right-panel">
        <div class="rp-tab-bar">
          <button class="rp-tab" :class="{ active: rightPanelTab === 'positions' }" @click="rightPanelTab = 'positions'">
            持仓
          </button>
          <button class="rp-tab" :class="{ active: rightPanelTab === 'orders' }" @click="rightPanelTab = 'orders'">
            委托 <span v-if="pendingOrders.length > 0" class="rp-tab-count">{{ pendingOrders.length }}</span>
          </button>
          <button class="rp-tab" :class="{ active: rightPanelTab === 'fills' }" @click="rightPanelTab = 'fills'">
            成交
          </button>
        </div>

        <!-- 持仓面板 -->
        <div v-show="rightPanelTab === 'positions'" class="rp-panel">
          <!-- 现货持仓 -->
          <template v-if="tradeType === 'spot'">
            <div class="card-header-with-info">
              <h3>现货持仓</h3>
              <button class="btn btn-small btn-ghost" @click="syncFills" :disabled="syncingFills">
                {{ syncingFills ? '同步中...' : '同步记录' }}
              </button>
            </div>
            <div class="cost-summary" v-if="totalCostUsdt !== '0'">
              <div class="summary-item">
                <span class="summary-label">市值</span>
                <span class="summary-value">${{ formatNumber(totalValueWithCost) }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">成本</span>
                <span class="summary-value">${{ formatNumber(totalCostUsdt) }}</span>
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
          </template>

          <!-- 合约持仓 -->
          <template v-else>
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
          </template>
        </div>

        <!-- 委托面板 -->
        <div v-show="rightPanelTab === 'orders'" class="rp-panel">
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

        <!-- 成交面板 -->
        <div v-show="rightPanelTab === 'fills'" class="rp-panel">
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
      </div><!-- right-panel -->
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
import { useTradingViewRuntime } from '../composables/useTradingViewRuntime'

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

// 右侧面板 tab
const rightPanelTab = ref('positions')

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

const okxConfigStatus = reactive({
  demoConfigured: false,
  liveConfigured: false,
})

const currentModeConfigured = computed(() => (
  props.mode === 'simulated' ? okxConfigStatus.demoConfigured : okxConfigStatus.liveConfigured
))

const syncTradingConfiguredState = () => {
  tradingStatus.api_configured = currentModeConfigured.value
}

const loadOKXConfigStatus = async () => {
  try {
    const result = await api.getOKXConfig()
    okxConfigStatus.demoConfigured = !!result.demo?.is_configured
    okxConfigStatus.liveConfigured = !!result.live?.is_configured
    syncTradingConfiguredState()
  } catch (e) {
    console.warn('加载 OKX 配置状态失败:', e)
  }
}

const otherMode = computed(() => (props.mode === 'simulated' ? 'live' : 'simulated'))
const otherModeText = computed(() => (otherMode.value === 'simulated' ? '模拟盘' : '实盘'))
const otherModeConfigured = computed(() => (
  otherMode.value === 'simulated' ? okxConfigStatus.demoConfigured : okxConfigStatus.liveConfigured
))

const apiWarningTitle = computed(() => `${pageModeText.value} API 未配置`)
const apiWarningMessage = computed(() => {
  if (otherModeConfigured.value) {
    return `当前显示的是${pageModeText.value}交易页，但已配置的是${otherModeText.value} API。切换到${otherModeText.value}页签即可查看并交易。`
  }
  return `当前显示的是${pageModeText.value}交易页，尚未配置该模式所需的 OKX API Key、Secret Key 和 Passphrase。`
})

const otherModeRoute = computed(() => ({
  path: '/trading',
  query: {
    tab: otherMode.value,
  },
}))

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

const { formatNumber, formatPrice, formatPercent, formatTime, getPlClass, getChangeClass, formatChange, getOrderStateText, toggleSymbolDropdown, selectSymbol, addCustomSymbol, removeSymbol, fetchCurrentPrice, fetchMaxSize, setQuickAmount, refreshAll, fetchTradingStatus, fetchAccountBalance, onHoldingPriceUpdate, subscribeHoldingPrices, unsubscribeHoldingPrices, fetchSpotHoldings, fetchPendingOrders, fetchFills, placeOrder, cancelOrder, confirmOrder, executeOrder, cancelConfirm, switchTradeType, fetchContractAccountConfig, getDesiredContractPosSide, setLeverage, fetchContractLeverage, fetchContractPositions, confirmContractOrder, cancelContractConfirm, executeContractOrder, quickSell, syncFills, openEditCostDialog, closeEditCostDialog, saveCostBasis, getPnlClass, formatPnl, handleClickOutside, onPriceUpdate, onAccountUpdate, mapInstTypeToTradeType, onOrderUpdate, onFillUpdate, initWebSocket, cleanupWebSocket, refreshTimer, priceRefreshTimer, isInitialized } = useTradingViewRuntime({ api, marketWS, props, appStore, selectedSymbol, availableSymbols, settingsLoaded, symbolDropdownOpen, symbolSearch, newSymbolInput, holdingSymbols, loading, orderLoading, cancelingOrderId, currentPrice, priceLoading, wsConnected, maxTradeSize, showConfirmDialog, pendingOrder, showContractConfirmDialog, pendingContractOrder, currentSide, tradeType, contractSide, contractSettings, contractPosMode, contractPositions, tradingStatus, accountBalance, spotHoldings, totalValueUsdt, totalValueWithCost, totalCostUsdt, totalFeeUsdt, totalPnlUsdt, totalPnlPercent, holdingsBase, holdingPrices, syncingFills, showEditCostDialog, editingCcy, editCostValue, savingCost, pendingOrders, fills, orderResult, orderForm, defaultModeText, isModeLocked, buildModeLockMessage, getErrorDetail, recalcHoldings, isHoldingSymbol, estimatedAmount, priceChange24h, contractInstId, baseCurrency, contractSideClass, contractSideText });

onMounted(() => {
  void loadOKXConfigStatus()
})

onActivated(() => {
  void loadOKXConfigStatus()
})

watch(
  () => props.mode,
  () => {
    syncTradingConfiguredState()
    void loadOKXConfigStatus()
  },
)

watch(
  [currentModeConfigured, () => tradingStatus.api_configured],
  ([configured, statusConfigured]) => {
    if (configured !== statusConfigured) {
      tradingStatus.api_configured = configured
    }
  },
  { immediate: true },
)

</script>
<style scoped src="../assets/styles/views/trading-view.css"></style>
