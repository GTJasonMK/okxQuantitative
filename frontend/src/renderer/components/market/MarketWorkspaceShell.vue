<template>
  <div class="market-shell">
    <section class="market-workspace">
      <header class="command-bar" :class="{ collapsed: headerCollapsed }">
        <div class="command-bar-minibar">
          <div class="command-summary-line compact">
            <span class="command-symbol">{{ activeSymbol || '未选择币种' }}</span>
            <template v-if="activeSymbol">
              <span
                class="command-price"
                :class="[getTickerClass(activeSymbol), getPriceFlashClass(activeSymbol)]"
              >
                {{ formatPrice(activeTicker?.last) }}
              </span>
              <span class="command-change" :class="getTickerClass(activeSymbol)">
                {{ formatChange(activeTicker?.change_24h) }}
              </span>
              <span class="command-chip compact" :class="{ live: wsConnected }">
                {{ commandContextLabel }}
              </span>
              <span
                class="command-chip compact command-chip-health"
                :class="`health-${activeSymbolHealthStatus}`"
                :title="activeSymbolHealthSummaryText"
              >
                {{ activeSymbolHealthBadgeText }}
              </span>
            </template>
            <template v-else>
              <span class="command-placeholder">
                搜索并打开交易对后开始分析。
              </span>
            </template>
          </div>
          <div class="command-minibar-actions">
            <button class="command-toggle-btn" @click="toggleHeaderCollapsed">
              {{ headerCollapsed ? '展开' : '收起' }}
            </button>
          </div>
        </div>
        <template v-if="!headerCollapsed">
          <div class="command-bar-top" v-memo="[commandControlsMemoKey]">
            <div class="command-controls">
              <div class="dropdown-select" ref="marketTypeDropdown">
                <button class="dropdown-trigger" @click="toggleMarketTypeDropdown">
                  <span class="label">价格</span>
                  <span class="dropdown-value">{{ currentMarketTypeLabel }}</span>
                  <span class="dropdown-arrow" :class="{ open: showMarketTypeDropdown }">▼</span>
                </button>
                <div class="dropdown-menu dropdown-menu-sm" v-show="showMarketTypeDropdown">
                  <label
                    v-for="type in marketTypeOptions"
                    :key="type.value"
                    class="dropdown-option"
                    :class="{ selected: marketInstType === type.value }"
                    @click="selectMarketType(type.value)"
                  >
                    <span class="radio-mark"></span>
                    {{ type.label }}
                  </label>
                </div>
              </div>
              <div class="dropdown-select" ref="timeframeDropdown">
                <button class="dropdown-trigger" @click="toggleTimeframeDropdown">
                  <span class="label">周期</span>
                  <span class="dropdown-value">{{ currentTimeframeLabel }}</span>
                  <span class="dropdown-arrow" :class="{ open: showTimeframeDropdown }">▼</span>
                </button>
                <div class="dropdown-menu dropdown-menu-sm" v-show="showTimeframeDropdown">
                  <label
                    v-for="tf in timeframes"
                    :key="tf.value"
                    class="dropdown-option"
                    :class="{ selected: currentTimeframe === tf.value }"
                    @click="selectTimeframe(tf.value)"
                  >
                    <span class="radio-mark"></span>
                    {{ tf.label }}
                  </label>
                </div>
              </div>
              <div class="dropdown-select" ref="indicatorDropdown">
                <button class="dropdown-trigger dropdown-trigger-wide" @click="toggleIndicatorDropdown">
                  <span class="label">指标</span>
                  <span class="dropdown-value">已选 {{ selectedIndicatorsCount }} 个</span>
                  <span class="dropdown-arrow" :class="{ open: showIndicatorDropdown }">▼</span>
                </button>
                <div class="dropdown-menu dropdown-menu-indicator" v-show="showIndicatorDropdown">
                  <div class="dropdown-options">
                    <div class="indicator-group">
                      <div class="group-header">均线 MA</div>
                      <label
                        v-for="ma in maIndicators"
                        :key="ma.key"
                        class="dropdown-option"
                        :class="{ selected: indicators[ma.key] }"
                        @click.prevent="toggleIndicator(ma.key)"
                      >
                        <span class="checkbox-mark"></span>
                        <span class="indicator-color" :style="{ background: ma.color }"></span>
                        {{ ma.label }}
                      </label>
                    </div>
                    <div class="indicator-group">
                      <div class="group-header">指数均线 EMA</div>
                      <label
                        v-for="ema in emaIndicators"
                        :key="ema.key"
                        class="dropdown-option"
                        :class="{ selected: indicators[ema.key] }"
                        @click.prevent="toggleIndicator(ema.key)"
                      >
                        <span class="checkbox-mark"></span>
                        <span class="indicator-color" :style="{ background: ema.color }"></span>
                        {{ ema.label }}
                      </label>
                    </div>
                    <div class="indicator-group">
                      <div class="group-header">布林带 BOLL</div>
                      <label
                        class="dropdown-option"
                        :class="{ selected: indicators.boll }"
                        @click.prevent="toggleIndicator('boll')"
                      >
                        <span class="checkbox-mark"></span>
                        <span class="indicator-color" style="background: #ff9800;"></span>
                        BOLL(20,2)
                      </label>
                    </div>
                    <div class="indicator-group">
                      <div class="group-header">成交量均线 VMA</div>
                      <label
                        v-for="vma in volumeMaIndicators"
                        :key="vma.key"
                        class="dropdown-option"
                        :class="{ selected: indicators[vma.key] }"
                        @click.prevent="toggleIndicator(vma.key)"
                      >
                        <span class="checkbox-mark"></span>
                        <span class="indicator-color" :style="{ background: vma.color }"></span>
                        {{ vma.label }}
                      </label>
                    </div>
                    <div class="indicator-group">
                      <div class="group-header">其他</div>
                      <label
                        class="dropdown-option"
                        :class="{ selected: indicators.sar }"
                        @click.prevent="toggleIndicator('sar')"
                      >
                        <span class="checkbox-mark"></span>
                        <span class="indicator-color" style="background: #e91e63;"></span>
                        SAR
                      </label>
                    </div>
                  </div>
                  <div class="dropdown-actions">
                    <button class="btn-text" @click="clearAllIndicators">清空全部</button>
                  </div>
                </div>
              </div>
              <div class="range-chip-group" role="group" aria-label="图表显示范围">
                <span class="range-chip-label">范围</span>
                <button
                  v-for="option in displayRangeOptions"
                  :key="option.value"
                  class="range-chip-btn"
                  :class="{ active: displayRangeDays === option.value }"
                  @click="selectDisplayRangeDays(option.value)"
                >
                  {{ option.label }}
                </button>
              </div>
              <template v-if="!wsConnected">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="autoRefresh" @change="toggleAutoRefresh" />
                  轮询刷新
                </label>
                <select
                  v-if="autoRefresh"
                  v-model="refreshInterval"
                  class="select-small"
                  @change="restartAutoRefresh"
                >
                  <option :value="3">3秒</option>
                  <option :value="5">5秒</option>
                  <option :value="10">10秒</option>
                  <option :value="30">30秒</option>
                </select>
              </template>
            </div>
          </div>
          <div class="command-bar-bottom">
            <div class="watchlist-launcher">
              <span class="watchlist-launcher-label">关注币种</span>
              <select
                class="select-small watchlist-symbol-select"
                :value="activeSymbol || ''"
                :disabled="watchlistSymbols.length === 0"
                @change="selectWatchlistSymbol($event.target.value)"
              >
                <option value="" disabled>
                  {{ watchlistSelectPlaceholder }}
                </option>
                <option
                  v-for="symbol in watchlistSymbols"
                  :key="symbol"
                  :value="symbol"
                >
                  {{ getWatchlistOptionLabel(symbol) }}
                </option>
              </select>
            </div>
          </div>
        </template>
      </header>

      <div v-if="activeSymbol" class="workspace-grid">
        <section class="chart-stage">
          <div class="chart-stage-shell">
            <div class="chart-frame chart-frame-immersive">
              <div class="chart-frame-header compact">
                <div class="chart-frame-heading chart-frame-heading-with-toolbox">
                  <div
                    class="chart-toolbox-anchor"
                    :class="{ expanded: chartToolboxExpanded }"
                    @mouseenter="handleChartToolboxPointerEnter"
                    @mouseleave="handleChartToolboxPointerLeave"
                  >
                    <button
                      class="chart-toolbox-trigger"
                      :class="{ active: chartToolboxExpanded }"
                      @click.stop="toggleChartToolboxExpanded"
                      @mousedown.stop
                      @touchstart.stop
                      @pointerdown.stop
                    >
                      <span class="chart-toolbox-trigger-kicker">工具</span>
                      <span class="chart-toolbox-trigger-label">{{ currentAnalysisToolLabel }}</span>
                      <span class="chart-toolbox-trigger-meta">标注 {{ activeAnnotationCount }}</span>
                    </button>

                    <aside
                      v-show="chartToolboxExpanded"
                      class="chart-toolbox chart-toolbox-floating"
                      :class="{ expanded: chartToolboxExpanded }"
                    >
                      <div
                        class="chart-toolbox-panel"
                        @mousedown.stop
                        @touchstart.stop
                        @pointerdown.stop
                      >
                        <div class="chart-toolbox-header">
                          <div class="chart-toolbox-heading">
                            <div class="chart-toolbox-kicker">分析工具</div>
                            <div class="chart-toolbox-title">图表工具库</div>
                          </div>
                          <span class="chart-toolbox-pill">
                            {{ currentMarketTypeLabel }} / {{ currentTimeframeLabel }}
                          </span>
                        </div>

                        <section class="chart-toolbox-section">
                          <div class="chart-toolbox-section-label">绘图工具</div>
                          <div class="chart-toolbox-grid">
                            <button
                              v-for="tool in analysisToolOptions"
                              :key="tool.key"
                              class="chart-tool-btn"
                              :class="{ active: activeAnalysisTool === tool.key }"
                              @click="selectAnalysisTool(tool.key)"
                            >
                              {{ tool.label }}
                            </button>
                            <button
                              class="chart-tool-btn"
                              :disabled="!activeAnnotationDraft"
                              @click="cancelChartAnnotationDraft(activeSymbol)"
                            >
                              取消落点
                            </button>
                            <button
                              class="chart-tool-btn"
                              :disabled="activeAnnotationCount === 0"
                              @click="removeLastChartAnnotation(activeSymbol)"
                            >
                              撤销标注
                            </button>
                            <button
                              class="chart-tool-btn"
                              :disabled="!activeSelectedAnnotation"
                              @click="clearSelectedChartAnnotation(activeSymbol)"
                            >
                              取消选中
                            </button>
                            <button
                              class="chart-tool-btn danger"
                              :disabled="!activeSelectedAnnotation"
                              @click="removeSelectedChartAnnotation(activeSymbol)"
                            >
                              删除选中
                            </button>
                            <button
                              class="chart-tool-btn danger"
                              :disabled="activeAssistantAnnotationCount === 0"
                              @click="clearChartAnnotationsBySource(activeSymbol, ['assistant', 'assistant_patrol'])"
                            >
                              清空 AI 标注
                            </button>
                            <button
                              class="chart-tool-btn danger"
                              :disabled="activeAnnotationCount === 0 && !activeAnnotationDraft"
                              @click="clearChartAnnotations(activeSymbol)"
                            >
                              清空标注
                            </button>
                          </div>
                          <div class="chart-toolbox-note">
                            {{ chartToolboxHint }}
                          </div>
                        </section>
                      </div>
                    </aside>
                  </div>

                  <div
                    ref="inspectorAnchorRef"
                    class="chart-inspector-anchor chart-inspector-anchor-left"
                    :class="{ expanded: inspectorExpanded }"
                    @mouseenter="handleInspectorPointerEnter"
                    @mouseleave="handleInspectorPointerLeave"
                  >
                    <button
                      class="chart-inspector-trigger"
                      :class="{ active: inspectorExpanded }"
                      @click.stop="toggleInspectorExpanded"
                      @mousedown.stop
                      @touchstart.stop
                      @pointerdown.stop
                    >
                      <span class="chart-inspector-trigger-kicker">面板</span>
                      <span class="chart-inspector-trigger-label">{{ currentInspectorTabLabel }}</span>
                      <span class="chart-inspector-trigger-meta">{{ currentInspectorTriggerMeta }}</span>
                    </button>
                  </div>
                </div>

                <div class="chart-frame-actions">
                  <div
                    ref="assistantAnchorRef"
                    class="chart-ai-anchor chart-ai-anchor-bottom-right"
                    :class="{ expanded: assistantExpanded }"
                  >
                    <button
                      class="chart-ai-trigger"
                      :class="{ active: assistantExpanded }"
                      @click.stop="toggleAssistantExpanded"
                      @mousedown.stop
                      @touchstart.stop
                      @pointerdown.stop
                    >
                      <span class="chart-ai-trigger-kicker">AI</span>
                      <span class="chart-ai-trigger-label">交易助手</span>
                      <span class="chart-ai-trigger-meta">{{ assistantTriggerMeta }}</span>
                    </button>
                  </div>

                  <Teleport to="body">
                    <aside
                      v-show="assistantExpanded"
                      class="assistant-shell chart-assistant chart-assistant-teleported"
                      :class="{ expanded: assistantExpanded }"
                      :style="assistantFloatingStyle"
                    >
                      <div
                        ref="assistantPanelRef"
                        class="assistant-panel"
                        @click.stop
                        @mousedown.stop
                        @touchstart.stop
                        @pointerdown.stop
                      >
                        <div class="assistant-topbar">
                          <div class="assistant-heading">
                            <div class="assistant-title-row">
                              <div class="assistant-title">AI 交易助手</div>
                              <span class="assistant-context-chip">
                                {{ assistantContextSummary }}
                              </span>
                            </div>
                            <div class="assistant-summary-line">
                              <span class="assistant-summary-status">
                                {{ assistantSessionStatusText }}
                              </span>
                              <span class="assistant-summary-session">
                                {{ assistantCurrentSessionTitle }}
                              </span>
                            </div>
                          </div>
                          <div class="assistant-actions">
                            <button
                              class="btn-icon"
                              :disabled="assistantBusy"
                              title="新建会话"
                              @click="clearAssistantConversation"
                            >
                              +
                            </button>
                            <button
                              class="btn-icon"
                              :disabled="!assistantBusy"
                              title="停止生成"
                              @click="stopAssistantResponse"
                            >
                              &#x25a0;
                            </button>
                            <button class="btn-icon btn-remove" title="关闭助手" @click="toggleAssistantExpanded">
                              ×
                            </button>
                          </div>
                        </div>

                        <div class="assistant-toolbar">
                          <div class="assistant-tabs">
                            <button
                              v-for="tab in assistantPanelTabs"
                              :key="tab.key"
                              class="assistant-tab-btn"
                              :class="{ active: assistantPanelTab === tab.key }"
                              @click="setAssistantPanelTab(tab.key)"
                            >
                              <span>{{ tab.label }}</span>
                              <span v-if="tab.badge > 0" class="assistant-tab-badge">{{ tab.badge }}</span>
                            </button>
                          </div>
                          <span v-if="assistantLatestStepTitle" class="assistant-toolbar-chip">
                            {{ assistantLatestStepTitle }}
                          </span>
                        </div>

                        <div class="assistant-workspace-body">
                          <div
                            v-if="assistantPanelTab === 'chat'"
                            ref="assistantMessagesRef"
                            class="assistant-messages"
                          >
                            <div
                              v-for="entry in activeAssistantTimelineEntries"
                              :key="entry.id"
                              class="assistant-timeline-entry"
                              :class="[
                                entry.role ? `is-${entry.role}` : '',
                              ]"
                            >
                              <div class="assistant-message" :class="`is-${entry.role}`">
                                <div class="assistant-message-role">
                                  {{ entry.role === 'user' ? '你' : 'AI' }}
                                </div>
                                <div class="assistant-message-bubble" :class="{ pending: entry.pending }">
                                  <div
                                    v-if="entry.role === 'assistant' && entry.inlineSteps && entry.inlineSteps.length > 0"
                                    class="assistant-message-tool-trace"
                                  >
                                    <article
                                      v-for="step in entry.inlineSteps"
                                      :key="step.id"
                                      class="assistant-message-tool-row"
                                      :class="`is-${step.status}`"
                                    >
                                      <div class="assistant-message-tool-head">
                                        <div class="assistant-message-tool-heading">
                                          <span class="assistant-step-icon" :class="`is-${step.status}`">
                                            <span v-if="step.status === 'completed'">✓</span>
                                            <span v-else-if="step.status === 'failed'">×</span>
                                          </span>
                                          <div class="assistant-message-tool-title-group">
                                            <div class="assistant-message-tool-title">
                                              {{ step.title || '工具调用' }}
                                            </div>
                                            <div class="assistant-message-tool-name">
                                              {{ step.toolName || 'planning' }}
                                            </div>
                                          </div>
                                        </div>
                                        <span class="assistant-message-tool-status" :class="`is-${step.status}`">
                                          {{ step.status === 'completed' ? '完成' : (step.status === 'failed' ? '失败' : '执行中') }}
                                        </span>
                                      </div>
                                      <div class="assistant-message-tool-preview">
                                        {{ step.preview }}
                                      </div>
                                      <div v-if="step.hasChartAnnotations" class="assistant-message-tool-actions">
                                        <button
                                          class="assistant-step-apply-btn"
                                          @click="applyAssistantStepChartAnnotations(step)"
                                        >
                                          应用到图表
                                        </button>
                                      </div>
                                      <div v-if="step.createdAt" class="assistant-message-tool-time">
                                        {{ formatAssistantTimestamp(step.createdAt) }}
                                      </div>
                                    </article>
                                  </div>
                                  <div
                                    v-if="entry.htmlContent && (entry.role === 'user' || entry.role === 'assistant')"
                                    class="assistant-message-text"
                                    v-html="entry.htmlContent"
                                  ></div>
                                  <div
                                    v-else-if="entry.role === 'assistant' && entry.inlineSteps && entry.inlineSteps.length > 0 && !entry.pending"
                                    class="assistant-message-tool-summary"
                                  >
                                    本轮工具调用已完成，正在等待最终结论展示。
                                  </div>
                                  <div v-if="entry.pending" class="assistant-message-pending">生成中...</div>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div v-else-if="assistantPanelTab === 'steps'" class="assistant-steps">
                            <div v-if="assistantDetailLoading" class="assistant-empty-state">
                              正在整理工具步骤...
                            </div>
                            <div v-else-if="activeAssistantSteps.length === 0" class="assistant-empty-state">
                              本轮还没有工具调用记录。
                            </div>
                            <article
                              v-for="step in activeAssistantSteps"
                              v-else
                              :key="step.id || `${step.step_index}-${step.tool_name}`"
                              class="assistant-step-card"
                              :class="{ failed: step.status === 'failed' }"
                            >
                              <div class="assistant-step-head">
                                <div class="assistant-step-index">
                                  <span class="assistant-step-icon" :class="`is-${step.status}`">
                                    <span v-if="step.status === 'completed'">✓</span>
                                    <span v-else-if="step.status === 'failed'">×</span>
                                  </span>
                                  <span>#{{ step.step_index }}</span>
                                </div>
                                <div class="assistant-step-heading">
                                  <div class="assistant-step-title">
                                    {{ step.title || step.tool_name || '工具调用' }}
                                  </div>
                                  <div class="assistant-step-tool">{{ step.tool_name || step.step_type }}</div>
                                </div>
                                <span class="assistant-step-status" :class="`is-${step.status}`">
                                  {{ step.status === 'completed' ? '成功' : (step.status === 'failed' ? '失败' : '执行中') }}
                                </span>
                              </div>
                              <div class="assistant-step-preview">{{ step.preview }}</div>
                              <div v-if="step.hasChartAnnotations" class="assistant-step-actions">
                                <button
                                  class="assistant-step-apply-btn"
                                  @click="applyAssistantStepChartAnnotations(step)"
                                >
                                  应用到图表
                                </button>
                              </div>
                              <div v-if="step.created_at" class="assistant-step-time">
                                {{ formatAssistantTimestamp(step.created_at) }}
                              </div>
                            </article>
                          </div>

                          <div v-else-if="assistantPanelTab === 'patrol'" class="assistant-patrol">
                            <section class="assistant-patrol-summary">
                              <div class="assistant-patrol-summary-head">
                                <div>
                                  <div class="assistant-section-label">主动巡检</div>
                                  <div class="assistant-patrol-summary-text">{{ assistantPatrolSummary }}</div>
                                </div>
                                <div class="assistant-patrol-actions">
                                  <button
                                    class="assistant-step-apply-btn"
                                    :disabled="assistantPatrolBusy"
                                    @click="runAssistantPatrolNow"
                                  >
                                    {{ assistantPatrolBusy ? '巡检中...' : '立即巡检' }}
                                  </button>
                                  <button
                                    class="assistant-step-apply-btn"
                                    :disabled="assistantPatrolBusy"
                                    @click="setAssistantPatrolEnabled(!assistantPatrolConfig.enabled)"
                                  >
                                    {{ assistantPatrolConfig.enabled ? '关闭后台巡检' : '开启后台巡检' }}
                                  </button>
                                </div>
                              </div>
                              <div class="assistant-patrol-meta-row">
                                <span class="assistant-toolbar-chip">
                                  {{ assistantPatrolConfig.enabled ? '已启用' : '未启用' }}
                                </span>
                                <span class="assistant-toolbar-chip">{{ assistantPatrolMeta }}</span>
                                <span
                                  v-if="assistantPatrolStatus.lastRunFinishedAt"
                                  class="assistant-toolbar-chip"
                                >
                                  {{ formatAssistantTimestamp(assistantPatrolStatus.lastRunFinishedAt) }}
                                </span>
                              </div>
                            </section>

                            <section class="assistant-patrol-section">
                              <div class="assistant-section-label">
                                实时推送
                                <span class="assistant-section-count">{{ assistantPatrolEvents.length }}</span>
                              </div>
                              <div v-if="!assistantPatrolStatusLoaded && assistantPatrolEvents.length === 0" class="assistant-empty-state">
                                正在读取巡检状态...
                              </div>
                              <div v-else-if="assistantPatrolEvents.length === 0" class="assistant-empty-state">
                                暂无实时推送。开启后台巡检后，新的候选机会会自动推送到这里。
                              </div>
                              <section
                                v-for="event in assistantPatrolEvents"
                                v-else
                                :key="event.id"
                                class="assistant-patrol-event"
                              >
                                <div class="assistant-patrol-event-head">
                                  <div>
                                    <div class="assistant-patrol-event-title">{{ event.title || '候选机会推送' }}</div>
                                    <div class="assistant-patrol-event-message">{{ event.message }}</div>
                                  </div>
                                  <div v-if="event.created_at" class="assistant-step-time">
                                    {{ formatAssistantTimestamp(event.created_at) }}
                                  </div>
                                </div>

                                <article
                                  v-for="candidate in event.candidates || []"
                                  :key="`${event.id}-${candidate.inst_id}`"
                                  class="assistant-patrol-candidate"
                                >
                                  <div class="assistant-patrol-candidate-head">
                                    <div class="assistant-patrol-candidate-title-row">
                                      <div class="assistant-patrol-candidate-symbol">{{ candidate.symbol }}</div>
                                      <span class="assistant-session-card-status" :class="candidate.bias === 'bullish' ? 'is-completed' : 'is-failed'">
                                        {{ candidate.bias === 'bullish' ? '偏多' : (candidate.bias === 'bearish' ? '偏空' : '中性') }}
                                      </span>
                                    </div>
                                    <div class="assistant-patrol-candidate-score">
                                      优先级 {{ Number(candidate.priority_score || 0).toFixed(1) }}
                                    </div>
                                  </div>
                                  <div class="assistant-patrol-candidate-action">{{ candidate.action || '继续观察' }}</div>
                                  <div class="assistant-patrol-meta-row">
                                    <span class="assistant-toolbar-chip assistant-health-chip" :class="`health-${candidate.healthStatus}`">
                                      {{ candidate.healthBadgeText }}
                                    </span>
                                    <span class="assistant-toolbar-chip">健康 {{ Number(candidate.healthScore || 0).toFixed(0) }}</span>
                                  </div>
                                  <div class="assistant-patrol-health-summary">
                                    {{ candidate.healthSummaryText }}
                                  </div>
                                  <div class="assistant-patrol-sync-row">
                                    <span class="assistant-patrol-sync-label">数据补齐</span>
                                    <div v-if="candidate.repairPlans?.length > 0" class="assistant-patrol-sync-actions">
                                      <button
                                        v-for="plan in candidate.repairPlans"
                                        :key="`${event.id}-${candidate.inst_id}-${plan.timeframe}`"
                                        class="assistant-patrol-sync-chip"
                                        :class="{ 'is-running': plan.disabled }"
                                        :disabled="plan.disabled"
                                        @click="syncAssistantPatrolCandidateTimeframe(candidate, plan.timeframe)"
                                      >
                                        <span>{{ plan.timeframe }}</span>
                                        <span v-if="plan.statusText">{{ plan.statusText }}</span>
                                      </button>
                                    </div>
                                    <span v-else class="assistant-patrol-sync-note">{{ candidate.repairHintText }}</span>
                                  </div>
                                  <div class="assistant-patrol-candidate-levels">
                                    <span>参考位 {{ formatPrice(candidate.entry_reference) }}</span>
                                    <span>失效位 {{ formatPrice(candidate.invalidation_reference) }}</span>
                                    <span v-if="candidate.trade_plan?.stop_loss?.price">止损 {{ formatPrice(candidate.trade_plan.stop_loss.price) }}</span>
                                    <span v-if="candidate.trade_plan?.targets?.[0]?.price">目标 {{ formatPrice(candidate.trade_plan.targets[0].price) }}</span>
                                  </div>
                                  <div v-if="candidate.setup_status || candidate.setup_confidence != null" class="assistant-patrol-meta-row">
                                    <span>
                                      计划 {{
                                        candidate.setup_status === 'ready'
                                          ? '可执行'
                                          : (candidate.setup_status === 'watch' ? '等待触发' : '回避')
                                      }}
                                    </span>
                                    <span v-if="candidate.setup_confidence != null">
                                      置信度 {{ (Number(candidate.setup_confidence || 0) * 100).toFixed(0) }}%
                                    </span>
                                  </div>
                                  <div class="assistant-patrol-candidate-actions">
                                    <button
                                      class="assistant-step-apply-btn"
                                      @click="applyAssistantPatrolCandidate(candidate)"
                                    >
                                      打开并应用计划
                                    </button>
                                  </div>
                                </article>
                              </section>
                            </section>

                            <section class="assistant-patrol-section assistant-patrol-history">
                              <div class="assistant-patrol-section-head">
                                <div class="assistant-section-label">
                                  历史巡检
                                  <span class="assistant-section-count">{{ assistantPatrolRuns.length }}</span>
                                </div>
                                <button
                                  class="assistant-step-apply-btn"
                                  :disabled="assistantPatrolRunsLoading"
                                  @click="loadAssistantPatrolRuns(true)"
                                >
                                  {{ assistantPatrolRunsLoading ? '刷新中...' : '刷新历史' }}
                                </button>
                              </div>
                              <div v-if="assistantPatrolRunsLoading && assistantPatrolRuns.length === 0" class="assistant-empty-state">
                                正在读取巡检历史...
                              </div>
                              <div v-else-if="assistantPatrolRuns.length === 0" class="assistant-empty-state">
                                还没有巡检历史记录。
                              </div>
                              <article
                                v-for="run in assistantPatrolRuns"
                                v-else
                                :key="run.run_id"
                                class="assistant-patrol-run"
                              >
                                <div class="assistant-patrol-run-head">
                                  <div>
                                    <div class="assistant-patrol-event-title">{{ run.triggerLabel }}</div>
                                    <div class="assistant-patrol-event-message">{{ run.summaryText }}</div>
                                  </div>
                                  <div class="assistant-step-time">
                                    {{ run.displayTime || formatAssistantTimestamp(run.created_at) }}
                                  </div>
                                </div>
                                <div class="assistant-patrol-meta-row">
                                  <span class="assistant-toolbar-chip">{{ run.inst_type || '--' }}</span>
                                  <span class="assistant-toolbar-chip">{{ run.mode || '--' }}</span>
                                  <span class="assistant-toolbar-chip">{{ run.candidateCount }} 个候选</span>
                                </div>
                                <article
                                  v-for="candidate in (run.candidates || []).slice(0, 3)"
                                  :key="`${run.run_id}-${candidate.inst_id}`"
                                  class="assistant-patrol-candidate"
                                >
                                  <div class="assistant-patrol-candidate-head">
                                    <div class="assistant-patrol-candidate-title-row">
                                      <div class="assistant-patrol-candidate-symbol">{{ candidate.symbol || candidate.inst_id }}</div>
                                      <span class="assistant-session-card-status" :class="candidate.bias === 'bullish' ? 'is-completed' : 'is-failed'">
                                        {{ candidate.bias === 'bullish' ? '偏多' : (candidate.bias === 'bearish' ? '偏空' : '中性') }}
                                      </span>
                                    </div>
                                    <div class="assistant-patrol-candidate-score">
                                      优先级 {{ Number(candidate.priority_score || 0).toFixed(1) }}
                                    </div>
                                  </div>
                                  <div class="assistant-patrol-candidate-action">{{ candidate.action || '继续观察' }}</div>
                                  <div class="assistant-patrol-meta-row">
                                    <span class="assistant-toolbar-chip assistant-health-chip" :class="`health-${candidate.healthStatus}`">
                                      {{ candidate.healthBadgeText }}
                                    </span>
                                    <span class="assistant-toolbar-chip">健康 {{ Number(candidate.healthScore || 0).toFixed(0) }}</span>
                                  </div>
                                  <div class="assistant-patrol-health-summary">
                                    {{ candidate.healthSummaryText }}
                                  </div>
                                  <div class="assistant-patrol-sync-row">
                                    <span class="assistant-patrol-sync-label">数据补齐</span>
                                    <div v-if="candidate.repairPlans?.length > 0" class="assistant-patrol-sync-actions">
                                      <button
                                        v-for="plan in candidate.repairPlans"
                                        :key="`${run.run_id}-${candidate.inst_id}-${plan.timeframe}`"
                                        class="assistant-patrol-sync-chip"
                                        :class="{ 'is-running': plan.disabled }"
                                        :disabled="plan.disabled"
                                        @click="syncAssistantPatrolCandidateTimeframe(candidate, plan.timeframe)"
                                      >
                                        <span>{{ plan.timeframe }}</span>
                                        <span v-if="plan.statusText">{{ plan.statusText }}</span>
                                      </button>
                                    </div>
                                    <span v-else class="assistant-patrol-sync-note">{{ candidate.repairHintText }}</span>
                                  </div>
                                  <div class="assistant-patrol-candidate-levels">
                                    <span>参考位 {{ formatPrice(candidate.entry_reference) }}</span>
                                    <span>失效位 {{ formatPrice(candidate.invalidation_reference) }}</span>
                                  </div>
                                  <div class="assistant-patrol-candidate-actions">
                                    <button
                                      class="assistant-step-apply-btn"
                                      @click="applyAssistantPatrolCandidate(candidate)"
                                    >
                                      应用到图表
                                    </button>
                                  </div>
                                </article>
                              </article>
                            </section>
                          </div>

                          <div v-else class="assistant-sessions-layout">
                            <section class="assistant-sessions-section assistant-sessions-history">
                              <div class="assistant-section-label">历史会话</div>
                              <div v-if="assistantSessionListLoading" class="assistant-empty-state">
                                正在加载会话...
                              </div>
                              <div v-else-if="assistantVisibleSessions.length === 0" class="assistant-empty-state">
                                当前币种还没有历史分析会话。
                              </div>
                              <button
                                v-for="session in assistantVisibleSessions"
                                v-else
                                :key="session.session_id"
                                class="assistant-session-card"
                                :class="{ active: session.isActive }"
                                @click="activateAssistantSession(session.session_id)"
                              >
                                <div class="assistant-session-card-head">
                                  <div class="assistant-session-card-title">
                                    {{ session.title || `${session.inst_id || '分析会话'}` }}
                                  </div>
                                  <span class="assistant-session-card-status" :class="`is-${session.status}`">
                                    {{ session.status === 'completed' ? '已完成' : (session.status === 'failed' ? '失败' : '进行中') }}
                                  </span>
                                </div>
                                <div class="assistant-session-card-meta">
                                  <span>{{ session.inst_id || '未指定标的' }}</span>
                                  <span>{{ session.displayTime || formatAssistantTimestamp(session.updated_at || session.created_at) }}</span>
                                </div>
                              </button>
                            </section>

                            <div class="assistant-resource-stack">
                              <section class="assistant-sessions-section assistant-snapshots-section">
                                <div class="assistant-resource-section-head">
                                  <div class="assistant-section-label">
                                    关键位快照
                                    <span class="assistant-section-count">{{ assistantVisibleLevelSnapshots.length }}</span>
                                  </div>
                                  <div class="assistant-patrol-actions">
                                    <button
                                      class="assistant-step-apply-btn"
                                      :disabled="assistantSnapshotBusy || !activeSymbol"
                                      @click="saveAssistantLevelSnapshot"
                                    >
                                      {{ assistantSnapshotBusy ? '保存中...' : '保存当前关键位' }}
                                    </button>
                                    <button
                                      class="assistant-step-apply-btn"
                                      :disabled="assistantLevelSnapshotsLoading"
                                      @click="loadAssistantLevelSnapshots(true)"
                                    >
                                      {{ assistantLevelSnapshotsLoading ? '刷新中...' : '刷新' }}
                                    </button>
                                  </div>
                                </div>
                                <div v-if="assistantLevelSnapshotsLoading && assistantVisibleLevelSnapshots.length === 0" class="assistant-empty-state">
                                  正在加载关键位快照...
                                </div>
                                <div v-else-if="assistantVisibleLevelSnapshots.length === 0" class="assistant-empty-state">
                                  还没有当前币种的关键位快照。
                                </div>
                                <article
                                  v-for="snapshot in assistantVisibleLevelSnapshots"
                                  v-else
                                  :key="snapshot.snapshot_id"
                                  class="assistant-snapshot-card"
                                >
                                  <div class="assistant-session-card-head">
                                    <div class="assistant-session-card-title">
                                      {{ snapshot.title || `${snapshot.inst_id} 关键位快照` }}
                                    </div>
                                    <span class="assistant-session-card-status">
                                      {{ snapshot.source || 'assistant' }}
                                    </span>
                                  </div>
                                  <div class="assistant-tool-description">{{ snapshot.summaryText }}</div>
                                  <div class="assistant-session-card-meta">
                                    <span>{{ snapshot.timeframeLabel }}</span>
                                    <span>{{ snapshot.displayTime || formatAssistantTimestamp(snapshot.created_at) }}</span>
                                  </div>
                                  <div class="assistant-patrol-candidate-levels">
                                    <span>支撑 {{ snapshot.supportCount }}</span>
                                    <span>压力 {{ snapshot.resistanceCount }}</span>
                                    <span v-if="snapshot.nearestSupport != null">最近支撑 {{ formatPrice(snapshot.nearestSupport) }}</span>
                                    <span v-if="snapshot.nearestResistance != null">最近压力 {{ formatPrice(snapshot.nearestResistance) }}</span>
                                  </div>
                                  <div class="assistant-patrol-candidate-actions">
                                    <button
                                      class="assistant-step-apply-btn"
                                      @click="applyAssistantLevelSnapshot(snapshot)"
                                    >
                                      应用到图表
                                    </button>
                                  </div>
                                </article>
                              </section>

                              <section class="assistant-sessions-section assistant-drafts-section">
                                <div class="assistant-resource-section-head">
                                  <div class="assistant-section-label">
                                    订单草案
                                    <span class="assistant-section-count">{{ assistantVisibleOrderDrafts.length }}</span>
                                  </div>
                                  <div class="assistant-patrol-actions">
                                    <button
                                      class="assistant-step-apply-btn"
                                      :disabled="assistantOrderDraftsLoading"
                                      @click="loadAssistantOrderDrafts(true)"
                                    >
                                      {{ assistantOrderDraftsLoading ? '刷新中...' : '刷新' }}
                                    </button>
                                  </div>
                                </div>
                                <div v-if="assistantOrderDraftsLoading && assistantVisibleOrderDrafts.length === 0" class="assistant-empty-state">
                                  正在加载订单草案...
                                </div>
                                <div v-else-if="assistantVisibleOrderDrafts.length === 0" class="assistant-empty-state">
                                  当前币种还没有订单草案。
                                </div>
                                <article
                                  v-for="draft in assistantVisibleOrderDrafts"
                                  v-else
                                  :key="draft.draft_id"
                                  class="assistant-draft-card"
                                >
                                  <div class="assistant-session-card-head">
                                    <div class="assistant-session-card-title">
                                      {{ draft.title || `${draft.inst_id} 订单草案` }}
                                    </div>
                                    <span class="assistant-session-card-status" :class="draft.statusClass">
                                      {{ draft.statusLabel }}
                                    </span>
                                  </div>
                                  <div class="assistant-patrol-meta-row">
                                    <span class="assistant-toolbar-chip">{{ draft.inst_type || '--' }}</span>
                                    <span class="assistant-toolbar-chip">{{ draft.modeLabel }}</span>
                                    <span class="assistant-toolbar-chip">{{ draft.sideLabel }}</span>
                                  </div>
                                  <div class="assistant-tool-description">{{ draft.summaryText }}</div>
                                  <div class="assistant-patrol-candidate-levels">
                                    <span>价格 {{ draft.priceLabel }}</span>
                                    <span>数量 {{ draft.size || '--' }}</span>
                                    <span>止损 {{ draft.stopLossLabel }}</span>
                                    <span v-if="draft.takeProfitCount > 0">目标 {{ draft.takeProfitCount }} 个</span>
                                    <span v-if="draft.annotationCount > 0">标注 {{ draft.annotationCount }} 个</span>
                                  </div>
                                  <div class="assistant-session-card-meta">
                                    <span>{{ draft.inst_id || '未指定标的' }}</span>
                                    <span>{{ draft.displayTime || formatAssistantTimestamp(draft.updated_at || draft.created_at) }}</span>
                                  </div>
                                  <div class="assistant-patrol-candidate-actions">
                                    <button
                                      class="assistant-step-apply-btn"
                                      @click="applyAssistantOrderDraft(draft)"
                                    >
                                      应用到图表
                                    </button>
                                  </div>
                                </article>
                              </section>

                              <section class="assistant-sessions-section assistant-sessions-tools">
                                <div class="assistant-section-label">
                                  可用工具
                                  <span class="assistant-section-count">{{ assistantToolCount }}</span>
                                </div>
                                <div class="assistant-tool-list">
                                  <article
                                    v-for="tool in assistantToolCatalog"
                                    :key="tool.name"
                                    class="assistant-tool-card"
                                  >
                                    <div class="assistant-tool-name">{{ tool.name }}</div>
                                    <div class="assistant-tool-description">{{ tool.description }}</div>
                                  </article>
                                </div>
                              </section>
                            </div>
                          </div>
                        </div>

                        <div v-if="assistantError" class="assistant-error-banner">
                          {{ assistantError }}
                        </div>

                        <div v-if="assistantPanelTab === 'chat'" class="assistant-quick-prompts">
                          <button
                            v-for="prompt in quickPromptOptions"
                            :key="prompt"
                            class="assistant-prompt-chip"
                            :disabled="assistantBusy || !activeSymbol"
                            @click="submitAssistantMessage(prompt)"
                          >
                            {{ prompt }}
                          </button>
                        </div>

                        <div class="assistant-composer">
                          <textarea
                            ref="assistantInputRef"
                            v-model="assistantInput"
                            class="assistant-input"
                            rows="1"
                            :disabled="assistantBusy || !activeSymbol"
                            :placeholder="assistantInputPlaceholder"
                            @input="syncAssistantInputHeight"
                            @keydown.enter.exact.prevent="submitAssistantMessage()"
                          ></textarea>
                          <button
                            class="btn btn-primary btn-sm assistant-send-btn"
                            :disabled="!assistantCanSend"
                            @click="submitAssistantMessage()"
                          >
                            {{ assistantBusy ? '分析中...' : '发送' }}
                          </button>
                        </div>
                      </div>
                    </aside>
                  </Teleport>

                  <Teleport to="body">
                    <aside
                      v-show="inspectorExpanded"
                      class="inspector-shell inspector-shell-compact chart-inspector chart-inspector-floating chart-inspector-teleported"
                      :class="{
                        expanded: inspectorExpanded,
                        'is-depth-chart-mode': orderBookViewMode === 'depth',
                        'is-depth-table-mode': orderBookViewMode === 'table',
                      }"
                      :style="inspectorFloatingStyle"
                      @mouseenter="handleInspectorPointerEnter"
                      @mouseleave="handleInspectorPointerLeave"
                    >
                      <div
                        ref="chartInspectorPanelRef"
                        class="chart-inspector-panel"
                        :class="{
                          'is-depth-chart-mode': orderBookViewMode === 'depth',
                          'is-depth-table-mode': orderBookViewMode === 'table',
                        }"
                        @click.stop
                        @mousedown.stop
                        @touchstart.stop
                        @pointerdown.stop
                      >
                        <div class="inspector-topbar">
                          <div class="inspector-head compact inspector-head-compact">
                            <div class="inspector-heading-inline">
                              <div class="inspector-title inspector-title-compact">盘口</div>
                              <span class="inspector-market-type">
                                {{ currentMarketTypeLabel }} / {{ currentTimeframeLabel }}
                              </span>
                            </div>
                            <div class="inspector-summary-chips">
                              <span class="context-chip">{{ activeOrderBookLevelCount }} 档</span>
                              <span class="context-chip">点差 {{ activeOrderBookSpreadLabel }}</span>
                            </div>
                          </div>
                          <div class="inspector-topbar-actions">
                            <button
                              class="orderbook-view-tab inspector-focus-toggle"
                              :class="{ active: inspectorFocusMode }"
                              @click="toggleInspectorFocusMode"
                            >
                              {{ inspectorFocusMode ? '退出专注' : '专注模式' }}
                            </button>
                            <div class="inspector-mode-tabs">
                              <button
                                v-for="tab in orderBookViewTabs"
                                :key="tab.key"
                                class="orderbook-view-tab"
                                :class="{ active: orderBookViewMode === tab.key }"
                                @click="orderBookViewMode = tab.key"
                              >
                                {{ tab.label }}
                              </button>
                            </div>
                          </div>
                        </div>

                        <div class="inspector-body">
                          <section class="inspector-pane inspector-pane-depth">
                            <div ref="depthInspectorScrollRef" class="inspector-scroll inspector-scroll-depth">
                              <div class="inspector-block block-fill depth-primary-block">
                                <div class="orderbook-toolbar" :class="{ compact: inspectorFocusMode }">
                                  <div class="orderbook-inline-stats">
                                    <span class="context-chip">精度 {{ activeOrderBookPrecisionLabel }}</span>
                                    <span class="context-chip">聚合 {{ activeOrderBookGroupingLabel }}</span>
                                    <span class="context-chip">{{ activeOrderBookSpreadPercentLabel }}</span>
                                  </div>
                                  <div v-if="!inspectorFocusMode" class="orderbook-header-actions">
                                    <div class="orderbook-grouping">
                                      <span class="orderbook-grouping-label">聚合</span>
                                      <button
                                        v-for="option in orderBookGroupingOptions"
                                        :key="option.value"
                                        class="orderbook-grouping-pill"
                                        :class="{ active: orderBookGrouping === option.value }"
                                        @click="orderBookGrouping = option.value"
                                      >
                                        {{ option.label }}
                                      </button>
                                    </div>
                                    <div class="orderbook-grouping">
                                      <span class="orderbook-grouping-label">档位</span>
                                      <button
                                        v-for="option in orderBookDepthOptions"
                                        :key="option.value"
                                        class="orderbook-grouping-pill"
                                        :class="{ active: orderBookDepthLimit === option.value }"
                                        @click="applyOrderBookDepthLimit(option.value)"
                                      >
                                        {{ option.label }}
                                      </button>
                                      <div class="orderbook-grouping-custom">
                                        <input
                                          v-model="orderBookDepthInput"
                                          class="orderbook-grouping-input"
                                          type="number"
                                          inputmode="numeric"
                                          :min="ORDERBOOK_DEPTH_MIN"
                                          :max="ORDERBOOK_DEPTH_MAX"
                                          step="1"
                                          placeholder="自定义"
                                          @keydown.enter.prevent="commitCustomOrderBookDepthLimit"
                                          @blur="commitCustomOrderBookDepthLimit"
                                        />
                                        <button
                                          class="orderbook-grouping-pill"
                                          :class="{ active: customOrderBookDepthActive }"
                                          @click="commitCustomOrderBookDepthLimit"
                                        >
                                          应用
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                <div
                                  class="orderbook-panel"
                                  :class="{
                                    'is-depth-mode': orderBookViewMode === 'depth',
                                    'is-table-mode': orderBookViewMode === 'table',
                                  }"
                                  @wheel="handleDepthPanelWheel"
                                >
                                  <div
                                    v-if="orderBookLoading[activeSymbol] && activeOrderBookLevelCount === 0"
                                    class="pane-empty"
                                  >
                                    正在加载盘口深度...
                                  </div>
                                  <div v-else-if="orderBookError[activeSymbol] && activeOrderBookLevelCount === 0" class="panel-alert">
                                    {{ orderBookError[activeSymbol] }}
                                  </div>
                                  <div v-else-if="activeOrderBookLevelCount === 0" class="pane-empty">
                                    暂无盘口深度数据
                                  </div>

                                  <template v-else-if="orderBookViewMode === 'table'">
                                    <div class="orderbook-table">
                                      <div class="orderbook-ladder-toolbar">
                                        <div class="orderbook-ladder-side-label is-bid">
                                          买入 ({{ activeOrderBookAssetLabel }})
                                        </div>
                                        <div class="orderbook-ladder-center-meta">
                                          <span class="orderbook-ladder-step">{{ activeOrderBookPrecisionLabel }}</span>
                                          <span class="orderbook-ladder-spread-chip">点差 {{ activeOrderBookSpreadLabel }}</span>
                                        </div>
                                        <div class="orderbook-ladder-side-label is-ask">
                                          卖出 ({{ activeOrderBookAssetLabel }})
                                        </div>
                                      </div>
                                      <div class="orderbook-ladder-header">
                                        <span class="is-bid">数量</span>
                                        <span class="is-bid">买价</span>
                                        <span class="is-ask">卖价</span>
                                        <span class="is-ask">数量</span>
                                      </div>
                                      <div class="orderbook-ladder-body">
                                        <div
                                          v-for="row in activeOrderBookLadderRows"
                                          :key="row.key"
                                          class="orderbook-ladder-row"
                                        >
                                          <div
                                            class="orderbook-ladder-cell orderbook-ladder-cell-size is-bid"
                                            :class="{ 'is-wall': row.bid && isOrderBookWall(row.bid, 'bid') }"
                                          >
                                            <span
                                              v-if="row.bid"
                                              class="orderbook-ladder-bar is-bid"
                                              :style="{ width: `${getOrderBookLevelSizeRatio(row.bid)}%` }"
                                            ></span>
                                            <span class="orderbook-ladder-value">
                                              {{ row.bid ? formatTradeSize(row.bid.size) : '--' }}
                                            </span>
                                          </div>
                                          <div class="orderbook-ladder-cell orderbook-ladder-cell-price is-bid">
                                            {{ row.bid ? formatPrice(row.bid.price) : '--' }}
                                          </div>
                                          <div class="orderbook-ladder-cell orderbook-ladder-cell-price is-ask">
                                            {{ row.ask ? formatPrice(row.ask.price) : '--' }}
                                          </div>
                                          <div
                                            class="orderbook-ladder-cell orderbook-ladder-cell-size is-ask"
                                            :class="{ 'is-wall': row.ask && isOrderBookWall(row.ask, 'ask') }"
                                          >
                                            <span
                                              v-if="row.ask"
                                              class="orderbook-ladder-bar is-ask"
                                              :style="{ width: `${getOrderBookLevelSizeRatio(row.ask)}%` }"
                                            ></span>
                                            <span class="orderbook-ladder-value">
                                              {{ row.ask ? formatTradeSize(row.ask.size) : '--' }}
                                            </span>
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                  </template>

                                  <template v-else>
                                    <div class="depth-chart-panel">
                                      <div class="depth-chart-toolbar">
                                        <div class="depth-chart-summary depth-chart-summary-inline">
                                          <div class="depth-chart-metric is-bid">
                                            <span>买盘</span>
                                            <strong>{{ activeOrderBookDepthChart?.bidDepthLabel || '--' }}</strong>
                                          </div>
                                          <div class="depth-chart-metric is-ask">
                                            <span>卖盘</span>
                                            <strong>{{ activeOrderBookDepthChart?.askDepthLabel || '--' }}</strong>
                                          </div>
                                          <div class="depth-chart-metric is-neutral">
                                            <span>点差</span>
                                            <strong>{{ activeOrderBookSpreadLabel }}</strong>
                                          </div>
                                          <div class="depth-chart-metric is-neutral">
                                            <span>档位</span>
                                            <strong>{{ activeOrderBookLevelCount }}</strong>
                                          </div>
                                        </div>
                                        <div v-if="activePrimaryBidWall || activePrimaryAskWall" class="depth-chart-insights depth-chart-insights-inline">
                                          <span v-if="activePrimaryBidWall" class="depth-chart-insight is-bid">
                                            买墙 {{ formatPrice(activePrimaryBidWall.price) }} · {{ formatTradeSize(activePrimaryBidWall.size) }}
                                          </span>
                                          <span v-if="activePrimaryAskWall" class="depth-chart-insight is-ask">
                                            卖墙 {{ formatPrice(activePrimaryAskWall.price) }} · {{ formatTradeSize(activePrimaryAskWall.size) }}
                                          </span>
                                        </div>
                                      </div>

                                      <div class="depth-chart-main depth-chart-main-full">
                                        <div class="depth-chart-visual depth-chart-visual-full">
                                          <div
                                            ref="depthChartCanvasRef"
                                            class="depth-chart-canvas"
                                            @wheel="handleDepthPanelWheel"
                                            @pointermove="handleDepthChartPointerMove"
                                            @pointerleave="hideDepthChartHover"
                                          >
                                            <svg
                                              v-if="activeOrderBookDepthChart"
                                              class="depth-chart-svg"
                                              :viewBox="activeOrderBookDepthChart.viewBox"
                                              preserveAspectRatio="none"
                                            >
                                              <defs>
                                                <linearGradient id="depthBidFill" x1="0%" y1="0%" x2="0%" y2="100%">
                                                  <stop offset="0%" stop-color="#00c88c" stop-opacity="0.46" />
                                                  <stop offset="100%" stop-color="#00c88c" stop-opacity="0.04" />
                                                </linearGradient>
                                                <linearGradient id="depthAskFill" x1="0%" y1="0%" x2="0%" y2="100%">
                                                  <stop offset="0%" stop-color="#ff6b6b" stop-opacity="0.44" />
                                                  <stop offset="100%" stop-color="#ff6b6b" stop-opacity="0.04" />
                                                </linearGradient>
                                              </defs>
                                              <rect
                                                :x="Math.min(activeOrderBookDepthChart.bestBidX, activeOrderBookDepthChart.bestAskX)"
                                                :y="activeOrderBookDepthChart.topY"
                                                :width="Math.max(2, Math.abs(activeOrderBookDepthChart.bestAskX - activeOrderBookDepthChart.bestBidX))"
                                                :height="activeOrderBookDepthChart.baselineY - activeOrderBookDepthChart.topY"
                                                class="depth-chart-spread-band"
                                              />
                                              <line
                                                :x1="activeOrderBookDepthChart.centerX"
                                                :x2="activeOrderBookDepthChart.centerX"
                                                :y1="activeOrderBookDepthChart.topY"
                                                :y2="activeOrderBookDepthChart.baselineY"
                                                class="depth-chart-center-line"
                                              />
                                              <template v-if="depthChartHover.visible">
                                                <line
                                                  :x1="depthChartHover.xSvg"
                                                  :x2="depthChartHover.xSvg"
                                                  :y1="activeOrderBookDepthChart.topY"
                                                  :y2="activeOrderBookDepthChart.baselineY"
                                                  class="depth-chart-hover-line"
                                                />
                                                <circle
                                                  :cx="depthChartHover.xSvg"
                                                  :cy="depthChartHover.ySvg"
                                                  r="5"
                                                  class="depth-chart-hover-point"
                                                  :class="depthChartHover.side === 'bid' ? 'is-bid' : 'is-ask'"
                                                />
                                              </template>
                                              <template v-if="activeOrderBookDepthChart.bidWallPoints?.length">
                                                <g
                                                  v-for="point in activeOrderBookDepthChart.bidWallPoints"
                                                  :key="`bid-wall-${point.price}`"
                                                  class="depth-chart-wall-group is-bid"
                                                >
                                                  <circle
                                                    :cx="point.x"
                                                    :cy="point.y"
                                                    r="5"
                                                    class="depth-chart-wall-point is-bid"
                                                  />
                                                </g>
                                              </template>
                                              <template v-if="activeOrderBookDepthChart.askWallPoints?.length">
                                                <g
                                                  v-for="point in activeOrderBookDepthChart.askWallPoints"
                                                  :key="`ask-wall-${point.price}`"
                                                  class="depth-chart-wall-group is-ask"
                                                >
                                                  <circle
                                                    :cx="point.x"
                                                    :cy="point.y"
                                                    r="5"
                                                    class="depth-chart-wall-point is-ask"
                                                  />
                                                </g>
                                              </template>
                                              <template v-if="activeOrderBookDepthChart.yTicks?.length">
                                                <g
                                                  v-for="tick in activeOrderBookDepthChart.yTicks"
                                                  :key="`depth-tick-${tick.value}`"
                                                  class="depth-chart-y-tick"
                                                >
                                                  <line
                                                    x1="0"
                                                    x2="960"
                                                    :y1="tick.y"
                                                    :y2="tick.y"
                                                    class="depth-chart-y-grid"
                                                  />
                                                  <text
                                                    x="944"
                                                    :y="tick.y - 6"
                                                    class="depth-chart-y-label"
                                                    text-anchor="end"
                                                  >
                                                    {{ tick.label }}
                                                  </text>
                                                </g>
                                              </template>
                                              <line
                                                x1="0"
                                                x2="960"
                                                :y1="activeOrderBookDepthChart.baselineY"
                                                :y2="activeOrderBookDepthChart.baselineY"
                                                class="depth-chart-base-line"
                                              />
                                              <path
                                                v-if="activeOrderBookDepthChart.bidAreaPath"
                                                :d="activeOrderBookDepthChart.bidAreaPath"
                                                class="depth-chart-area is-bid"
                                              />
                                              <path
                                                v-if="activeOrderBookDepthChart.askAreaPath"
                                                :d="activeOrderBookDepthChart.askAreaPath"
                                                class="depth-chart-area is-ask"
                                              />
                                              <path
                                                v-if="activeOrderBookDepthChart.bidLinePath"
                                                :d="activeOrderBookDepthChart.bidLinePath"
                                                class="depth-chart-line is-bid"
                                              />
                                              <path
                                                v-if="activeOrderBookDepthChart.askLinePath"
                                                :d="activeOrderBookDepthChart.askLinePath"
                                                class="depth-chart-line is-ask"
                                              />
                                            </svg>
                                            <div
                                              v-if="depthChartHover.visible"
                                              class="depth-chart-tooltip"
                                              :class="depthChartHover.side === 'bid' ? 'is-bid' : 'is-ask'"
                                              :style="{ left: `${depthChartHover.left}px`, top: `${depthChartHover.top}px` }"
                                            >
                                              <strong>{{ formatPrice(depthChartHover.price) }}</strong>
                                              <span>累计 {{ formatTradeSize(depthChartHover.total) }}</span>
                                              <span>单档 {{ formatTradeSize(depthChartHover.size) }}</span>
                                              <span>{{ formatPercentValue(depthChartHover.distancePercent, 3) }}</span>
                                            </div>
                                          </div>
                                          <div class="depth-chart-axis">
                                            <span>{{ activeOrderBookDepthChart?.leftPriceLabel || '--' }}</span>
                                            <span class="current">{{ activeOrderBookDepthChart?.centerPriceLabel || '--' }}</span>
                                            <span>{{ activeOrderBookDepthChart?.rightPriceLabel || '--' }}</span>
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                  </template>
                                </div>
                              </div>
                            </div>
                          </section>
                        </div>
                      </div>
                    </aside>
                  </Teleport>

                  <button class="btn-icon" @click="refreshChart(activeSymbol)" :disabled="activeChartLoading">
                    <span v-if="activeChartLoading" class="spinner-small"></span>
                    <span v-else>&#x21bb;</span>
                  </button>
                  <button class="btn-icon btn-remove" @click="closeSymbolTab(activeSymbol)">×</button>
                </div>
              </div>

              <div class="chart-canvas chart-canvas-immersive">
                <div
                  :ref="el => setChartRef(activeSymbol, el)"
                  :class="['chart', 'chart-analysis', { 'chart-drawing-mode': activeAnalysisTool !== 'none' }]"
                ></div>

                <div v-if="activeChartLoading" class="chart-loading">
                  <div class="spinner"></div>
                </div>
                <div v-else-if="activeChartError" class="chart-error">
                  <div class="error-icon">!</div>
                  <div class="error-text">{{ activeChartError }}</div>
                  <button class="btn btn-sm" @click="refreshChart(activeSymbol)">重试</button>
                </div>
                <template v-else>
                  <div class="chart-overlay chart-overlay-top-right">
                    <div class="chart-overlay-panel chart-overlay-panel-price">
                      <div class="overlay-price-line">
                        <strong
                          class="overlay-price"
                          :class="[getTickerClass(activeSymbol), getPriceFlashClass(activeSymbol)]"
                        >
                          {{ formatPrice(activeTicker?.last) }}
                        </strong>
                        <span class="overlay-change" :class="getTickerClass(activeSymbol)">
                          {{ formatChange(activeTicker?.change_24h) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div v-else class="workspace-empty">
        <div class="workspace-empty-kicker">Trading Workspace</div>
        <div class="workspace-empty-title">当前没有打开的行情标签</div>
        <div class="workspace-empty-text">
          从顶部关注币种下拉栏选择交易对后，主区域会进入图表分析视图。
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { defineComponent, inject } from 'vue';
import { MARKET_VIEW_CONTEXT } from './marketViewContext';

export default defineComponent({
  name: 'MarketWorkspaceShell',
  setup() {
    const context = inject(MARKET_VIEW_CONTEXT, null);
    if (!context) {
      throw new Error('MarketWorkspaceShell 缺少 MarketView 上下文');
    }
    return context;
  },
});
</script>
<style scoped src="../../assets/styles/views/market-view-layout.css"></style>
<style scoped src="../../assets/styles/views/market-view-controls.css"></style>
<style scoped src="../../assets/styles/views/market-view-panels.css"></style>
<style scoped src="../../assets/styles/views/market-view-assistant.css"></style>
