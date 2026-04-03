<template>
  <div class="strategy-view">
    <div class="page-header">
      <div>
        <h1>策略工作台</h1>
        <p>统一管理策略源码、外部策略文件、自动执行与风控配置</p>
      </div>
      <div class="header-badges">
        <span class="pill" :class="appStore.tradingMode">{{ modeLabel }}</span>
        <span class="pill subtle">外部目录：{{ externalDirectoryLabel }}</span>
      </div>
    </div>

    <div class="tab-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'source' }"
        @click="activeTab = 'source'"
      >
        策略源码 / IDE
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'execution' }"
        @click="activeTab = 'execution'"
      >
        自动执行 / 风控
      </button>
    </div>

    <section v-if="activeTab === 'source'" class="workspace source-workspace">
      <aside class="side-panel card">
        <!-- 侧边栏 tab 切换 -->
        <div class="side-tab-bar">
          <button
            class="side-tab"
            :class="{ active: sidePanelTab === 'registered' }"
            @click="sidePanelTab = 'registered'"
          >已注册策略</button>
          <button
            class="side-tab"
            :class="{ active: sidePanelTab === 'external' }"
            @click="sidePanelTab = 'external'"
          >
            外部文件
            <span v-if="externalFiles.length" class="side-tab-count">{{ externalFiles.length }}</span>
          </button>
        </div>

        <!-- 已注册策略 tab -->
        <template v-if="sidePanelTab === 'registered'">
          <div class="side-tab-toolbar">
            <span class="side-tab-desc">点击查看当前生效源码</span>
            <button class="btn btn-sm" @click="reloadAllStrategySources" :disabled="reloadingStrategies">
              {{ reloadingStrategies ? '加载中...' : '热加载' }}
            </button>
          </div>
          <div class="list-section">
            <button
              v-for="strategy in strategies"
              :key="strategy.id"
              class="list-item"
              :class="{ active: selectedSourceKind === 'registered' && selectedRegisteredStrategyId === strategy.id }"
              @click="selectRegisteredStrategy(strategy.id)"
            >
              <span class="list-item-title">{{ strategy.name }}</span>
              <span class="list-item-subtitle">{{ strategy.description || strategy.id }}</span>
            </button>
            <div v-if="!strategies.length" class="empty-hint">暂无已注册策略</div>
          </div>
        </template>

        <!-- 外部策略文件 tab -->
        <template v-else>
          <div class="side-tab-toolbar">
            <span class="side-tab-desc">可新建、编辑、删除并热加载</span>
            <div class="actions-inline">
              <button class="btn btn-sm btn-secondary" @click="createNewExternalFile">新建</button>
              <button class="btn btn-sm btn-secondary" @click="loadExternalFiles(editableFile.filename)">刷新</button>
            </div>
          </div>
          <div class="list-section">
            <button
              v-for="file in externalFiles"
              :key="file.filename"
              class="list-item"
              :class="{ active: selectedSourceKind === 'external' && editableFile.filename === file.filename && !editableFile.isNew }"
              @click="selectExternalFile(file.filename)"
            >
              <span class="list-item-title">{{ file.filename }}</span>
              <span class="list-item-subtitle">
                {{ file.strategy_ids?.length ? `注册策略：${file.strategy_ids.join(', ')}` : '尚未注册为策略' }}
              </span>
            </button>
            <div v-if="!externalFiles.length" class="empty-hint">还没有外部策略文件，点击「新建」开始</div>
          </div>
        </template>
      </aside>

      <div class="editor-panel card">
        <div class="panel-header">
          <div>
            <h3>{{ sourceTitle }}</h3>
            <p>{{ sourceSubtitle }}</p>
          </div>
          <div class="actions-inline">
            <template v-if="selectedSourceKind === 'external'">
              <button class="btn btn-sm btn-secondary" @click="createNewExternalFile">重置模板</button>
              <button class="btn btn-sm" @click="saveExternalFile" :disabled="sourceSaving">
                {{ sourceSaving ? '保存中...' : '保存并热加载' }}
              </button>
              <button
                v-if="!editableFile.isNew"
                class="btn btn-sm btn-danger"
                @click="deleteExternalFile"
                :disabled="sourceDeleting"
              >
                {{ sourceDeleting ? '删除中...' : '删除文件' }}
              </button>
            </template>
          </div>
        </div>

        <div class="source-meta">
          <template v-if="selectedSourceKind === 'external'">
            <label class="field grow">
              <span>文件名</span>
              <input v-model.trim="editableFile.filename" class="input" placeholder="例如 custom_strategy.py" />
            </label>
            <span class="badge" :class="editorDirty ? 'warn' : 'ok'">
              {{ editorDirty ? '未保存' : '已保存' }}
            </span>
          </template>
          <template v-else>
            <span class="badge">{{ registeredSource.filename || '未选择策略' }}</span>
            <span
              v-for="strategyId in registeredSource.strategyIds"
              :key="strategyId"
              class="badge subtle"
            >
              {{ strategyId }}
            </span>
          </template>
        </div>

        <!-- 已注册策略只读时的引导提示 -->
        <div v-if="selectedSourceKind === 'registered'" class="editor-guide-bar" :class="{ 'guide-empty': !registeredSource.filename }">
          <span class="guide-icon">{{ registeredSource.filename ? 'ℹ' : '←' }}</span>
          <span v-if="registeredSource.filename">当前为只读预览。如需编辑，请在左侧「外部策略文件」中选择或<button class="guide-link" @click="createNewExternalFile">新建文件</button>。</span>
          <span v-else>从左侧选择一个已注册策略查看源码，或点击「新建」创建可编辑的外部策略文件。</span>
        </div>

        <div class="editor-shell">
          <template v-if="selectedSourceKind === 'external'">
            <MonacoEditor
              v-model="editorContent"
              language="python"
              :read-only="false"
              class="editor-instance"
            />
          </template>
          <template v-else>
            <pre class="source-preview"><code>{{ registeredSource.source }}</code></pre>
          </template>
        </div>
      </div>
    </section>

    <section v-else class="workspace execution-workspace">
      <div class="execution-main card">
        <div class="panel-header">
          <div>
            <h3>策略自动执行</h3>
            <p>当前只支持现货 SPOT 自动执行，实际下单模式跟随后端默认模式</p>
          </div>
          <div class="actions-inline">
            <button class="btn btn-sm btn-secondary" @click="loadLiveState">刷新状态</button>
            <button class="btn btn-sm btn-danger" @click="stopLiveStrategy" :disabled="liveActionLoading || !isEngineActive">
              停止策略
            </button>
          </div>
        </div>

        <div class="status-strip">
          <div class="status-card">
            <span class="status-label">引擎状态</span>
            <span class="status-value" :class="statusTone">{{ liveStatus.status || 'stopped' }}</span>
          </div>
          <div class="status-card">
            <span class="status-label">运行策略</span>
            <span class="status-value">{{ liveStatus.strategy_name || '-' }}</span>
          </div>
          <div class="status-card">
            <span class="status-label">最近信号</span>
            <span class="status-value">{{ liveStatus.last_signal_type || '-' }}</span>
          </div>
          <div class="status-card">
            <span class="status-label">成功 / 失败</span>
            <span class="status-value">{{ liveStatus.successful_orders || 0 }} / {{ liveStatus.failed_orders || 0 }}</span>
          </div>
        </div>

        <div class="form-grid">
          <label class="field">
            <span>策略</span>
            <select v-model="liveForm.strategyId" class="input">
              <option v-for="strategy in executionStrategyList" :key="strategy.id" :value="strategy.id">
                {{ strategy.name }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>交易对</span>
            <input v-model.trim="liveForm.symbol" class="input" list="strategy-symbols" placeholder="BTC-USDT" />
            <datalist id="strategy-symbols">
              <option v-for="symbol in symbolOptions" :key="symbol" :value="symbol" />
            </datalist>
          </label>

          <label class="field">
            <span>周期</span>
            <select v-model="liveForm.timeframe" class="input">
              <option v-for="item in timeframeOptions" :key="item" :value="item">
                {{ item }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>仓位比例</span>
            <input v-model.number="liveForm.positionSize" class="input" type="number" min="0.01" max="1" step="0.01" />
          </label>

          <label class="field">
            <span>止损比例</span>
            <input v-model.number="liveForm.stopLoss" class="input" type="number" min="0" max="1" step="0.01" />
          </label>

          <label class="field">
            <span>止盈比例</span>
            <input v-model.number="liveForm.takeProfit" class="input" type="number" min="0" max="5" step="0.01" />
          </label>

          <label class="field">
            <span>初始资金</span>
            <input v-model.number="liveForm.initialCapital" class="input" type="number" min="1" step="100" />
          </label>

          <label class="field">
            <span>检查间隔（秒）</span>
            <input v-model.number="liveForm.checkInterval" class="input" type="number" min="1" step="1" />
          </label>
        </div>

        <div v-if="activeExecutionStrategy?.params?.length" class="dynamic-params">
          <div class="section-caption">策略参数</div>
          <div class="form-grid compact">
            <label v-for="param in activeExecutionStrategy.params" :key="param.name" class="field">
              <span>{{ param.label || param.name }}</span>
              <select
                v-if="param.type === 'select'"
                v-model="liveStrategyParams[param.name]"
                class="input"
              >
                <option v-for="option in param.options || []" :key="option" :value="option">
                  {{ option }}
                </option>
              </select>
              <select
                v-else-if="param.type === 'bool'"
                v-model="liveStrategyParams[param.name]"
                class="input"
              >
                <option :value="true">true</option>
                <option :value="false">false</option>
              </select>
              <input
                v-else
                v-model="liveStrategyParams[param.name]"
                class="input"
                :type="param.type === 'int' || param.type === 'float' ? 'number' : 'text'"
                :step="param.type === 'int' ? '1' : '0.01'"
                :min="param.min"
                :max="param.max"
              />
            </label>
          </div>
        </div>

        <div class="actions-row">
          <button class="btn" @click="startLiveStrategy" :disabled="liveActionLoading">
            {{ liveActionLoading ? '提交中...' : '启动自动执行' }}
          </button>
          <span class="inline-note">
            实际下单模式：{{ modeLabel }}，订单执行前会走统一风控校验
          </span>
        </div>

        <div class="section-caption">最近订单</div>
        <div class="table-shell">
          <table class="table">
            <thead>
              <tr>
                <th>时间</th>
                <th>方向</th>
                <th>交易对</th>
                <th>数量</th>
                <th>价格</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in liveOrders" :key="item.id || `${item.order_id}-${item.client_order_id}`">
                <td>{{ formatDateTime(item.ts || item.timestamp) }}</td>
                <td>{{ item.side || '-' }}</td>
                <td>{{ item.inst_id || '-' }}</td>
                <td>{{ item.size || '-' }}</td>
                <td>{{ item.price || '-' }}</td>
                <td :class="item.success ? 'ok-text' : 'danger-text'">
                  {{ item.success ? '成功' : (item.error_message || '失败') }}
                </td>
              </tr>
              <tr v-if="!liveOrders.length">
                <td colspan="6" class="empty-cell">暂无自动执行订单记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <aside class="risk-panel card">
        <div class="panel-header">
          <div>
            <h3>风险控制面板</h3>
            <p>手动下单和策略自动执行共用同一套风控规则</p>
          </div>
          <button class="btn btn-sm btn-secondary" @click="loadRiskSummary">刷新风险</button>
        </div>

        <div class="risk-metrics">
          <div class="metric-card">
            <span>总权益</span>
            <strong>{{ formatMoney(riskSummary.total_equity) }}</strong>
          </div>
          <div class="metric-card">
            <span>总风险敞口</span>
            <strong>{{ formatMoney(riskSummary.total_exposure) }}</strong>
          </div>
          <div class="metric-card">
            <span>敞口占比</span>
            <strong>{{ formatRatio(riskSummary.exposure_ratio) }}</strong>
          </div>
          <div class="metric-card">
            <span>浮盈浮亏</span>
            <strong :class="riskSummary.floating_pnl >= 0 ? 'ok-text' : 'danger-text'">
              {{ formatMoney(riskSummary.floating_pnl) }}
            </strong>
          </div>
          <div class="metric-card">
            <span>现货敞口</span>
            <strong>{{ formatMoney(riskSummary.spot_exposure) }}</strong>
          </div>
          <div class="metric-card">
            <span>合约敞口</span>
            <strong>{{ formatMoney(riskSummary.contract_exposure) }}</strong>
          </div>
        </div>

        <div class="form-grid compact">
          <label class="field checkbox-field">
            <input v-model="riskConfig.enabled" type="checkbox" />
            <span>启用统一风控</span>
          </label>

          <label class="field">
            <span>单笔最大亏损比例</span>
            <input v-model.number="riskConfig.max_single_loss_ratio" class="input" type="number" min="0" max="1" step="0.01" />
          </label>

          <label class="field">
            <span>默认止损比例</span>
            <input v-model.number="riskConfig.default_stop_loss_ratio" class="input" type="number" min="0" max="1" step="0.01" />
          </label>

          <label class="field">
            <span>总风险敞口上限</span>
            <input v-model.number="riskConfig.max_total_position_ratio" class="input" type="number" min="0" max="10" step="0.05" />
          </label>
        </div>

        <div class="note-box">
          估算规则：单笔风险 = 下单金额 × 止损比例；总风险敞口按现货市值 + 合约名义价值汇总。
        </div>

        <button class="btn" @click="saveRiskConfig" :disabled="riskSaving">
          {{ riskSaving ? '保存中...' : '保存风控配置' }}
        </button>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useAppStore } from '../stores/app';
import { api } from '../services/api';

defineOptions({
  name: 'StrategyView',
});

const MonacoEditor = defineAsyncComponent(() => import('../components/MonacoEditor.vue'));

const appStore = useAppStore();

const activeTab = ref('source');
const strategies = ref([]);
const liveStrategies = ref([]);
const externalFiles = ref([]);
const externalDirectory = ref('');
const selectedSourceKind = ref('registered');
const sidePanelTab = ref('registered'); // 'registered' | 'external'
const selectedRegisteredStrategyId = ref('');
const reloadingStrategies = ref(false);
const sourceSaving = ref(false);
const sourceDeleting = ref(false);
const liveActionLoading = ref(false);
const riskSaving = ref(false);
const symbolOptions = ref(['BTC-USDT', 'ETH-USDT']);

const registeredSource = reactive({
  filename: '',
  source: '# 请选择一个已注册策略查看源码',
  strategyIds: [],
});

const editableFile = reactive({
  filename: 'custom_strategy.py',
  source: '',
  savedSource: '',
  strategyIds: [],
  isNew: true,
});

const liveStatus = reactive({
  status: 'stopped',
  mode: '',
  strategy_id: '',
  strategy_name: '',
  symbol: '',
  timeframe: '',
  inst_type: 'SPOT',
  start_time: null,
  last_signal_time: null,
  last_signal_type: '',
  total_signals: 0,
  total_orders: 0,
  successful_orders: 0,
  failed_orders: 0,
  error_message: '',
  check_interval: 60,
});

const liveOrders = ref([]);

const riskConfig = reactive({
  enabled: true,
  max_single_loss_ratio: 0.02,
  default_stop_loss_ratio: 0.03,
  max_total_position_ratio: 1.0,
});

const riskSummary = reactive({
  total_equity: 0,
  available_cash: 0,
  spot_exposure: 0,
  contract_exposure: 0,
  total_exposure: 0,
  exposure_ratio: 0,
  floating_pnl: 0,
});

const liveForm = reactive({
  strategyId: '',
  symbol: 'BTC-USDT',
  timeframe: '1H',
  instType: 'SPOT',
  initialCapital: 10000,
  positionSize: 0.1,
  stopLoss: 0.05,
  takeProfit: 0.1,
  checkInterval: 60,
});

const liveStrategyParams = ref({});
const timeframeOptions = ['1m', '5m', '1H', '4H', '1D'];

let pollTimer = null;

const modeLabel = computed(() => (appStore.tradingMode === 'live' ? '默认模式：实盘' : '默认模式：模拟盘'));
const externalDirectoryLabel = computed(() => externalDirectory.value || '未加载');
const editorDirty = computed(() => (
  selectedSourceKind.value === 'external' && editableFile.source !== editableFile.savedSource
));
const sourceTitle = computed(() => (
  selectedSourceKind.value === 'external' ? '外部策略 IDE' : '策略源码查看'
));
const sourceSubtitle = computed(() => (
  selectedSourceKind.value === 'external'
    ? '保存后会自动热加载策略注册表，无需重启后端'
    : '这里展示当前已注册策略对应的生效源码，编辑请切换到外部文件'
));
const executionStrategyList = computed(() => (
  liveStrategies.value.length ? liveStrategies.value : strategies.value
));
const activeExecutionStrategy = computed(() => (
  executionStrategyList.value.find((item) => item.id === liveForm.strategyId) || null
));
const statusTone = computed(() => {
  if (liveStatus.status === 'running') return 'ok-text';
  if (liveStatus.status === 'starting' || liveStatus.status === 'stopping') return 'warn-text';
  if (liveStatus.status === 'error') return 'danger-text';
  return '';
});
const isEngineActive = computed(() => ['starting', 'running', 'stopping'].includes(liveStatus.status));

const editorContent = computed({
  get() {
    return selectedSourceKind.value === 'external' ? editableFile.source : registeredSource.source;
  },
  set(value) {
    if (selectedSourceKind.value === 'external') {
      editableFile.source = value;
    }
  },
});

const getErrorDetail = (error) => (
  error?.response?.data?.detail || error?.response?.data?.message || error?.message || '请求失败'
);

const normalizeIdentifier = (value) => (
  String(value || '')
    .replace(/\.py$/i, '')
    .replace(/[^a-zA-Z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase() || 'custom_strategy'
);

const toClassName = (value) => (
  normalizeIdentifier(value)
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('') || 'CustomStrategy'
);

const buildStrategyTemplate = (filename) => {
  const strategyId = normalizeIdentifier(filename);
  const className = toClassName(filename);

  return `from typing import Dict, List

from app.strategies.base import BaseStrategy, Signal, SignalType, StrategyConfig
from pydantic import BaseModel, Field


class ${className}Params(BaseModel):
    fast_period: int = Field(default=5, ge=2, le=60, description="短周期")
    slow_period: int = Field(default=20, ge=5, le=200, description="长周期")


class ${className}(BaseStrategy):
    strategy_id = "${strategyId}"
    strategy_name = "${className}"
    strategy_description = "外部策略示例，可在策略工作台中直接编辑"
    params_schema = ${className}Params

    @classmethod
    def create_instance(
        cls,
        symbol: str = "BTC-USDT",
        timeframe: str = "1H",
        initial_capital: float = 10000,
        position_size: float = 0.1,
        stop_loss: float = 0.05,
        take_profit: float = 0.10,
        inst_type: str = "SPOT",
        **strategy_params,
    ):
        config = StrategyConfig(
            name=cls.strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            params=strategy_params,
        )
        return cls(config)

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        closes = [float(item.close) for item in candles]
        return {"close": closes}

    def generate_signal(self, index: int):
        if index < 1:
            return None

        current_price = float(self._candles[index].close)
        previous_price = float(self._candles[index - 1].close)

        if previous_price <= 0:
            return None

        if current_price > previous_price and self.position.is_empty:
            return Signal(
                type=SignalType.BUY,
                price=current_price,
                timestamp=self._candles[index].timestamp,
                reason="示例策略：价格上行",
            )

        if current_price < previous_price and not self.position.is_empty:
            return Signal(
                type=SignalType.SELL,
                price=current_price,
                timestamp=self._candles[index].timestamp,
                reason="示例策略：价格回落",
            )

        return None
`;
};

const updateRiskConfig = (configData = {}) => {
  riskConfig.enabled = Boolean(configData.enabled);
  riskConfig.max_single_loss_ratio = Number(configData.max_single_loss_ratio ?? 0.02);
  riskConfig.default_stop_loss_ratio = Number(configData.default_stop_loss_ratio ?? 0.03);
  riskConfig.max_total_position_ratio = Number(configData.max_total_position_ratio ?? 1);
};

const updateRiskSummary = (summary = {}) => {
  riskSummary.total_equity = Number(summary.total_equity || 0);
  riskSummary.available_cash = Number(summary.available_cash || 0);
  riskSummary.spot_exposure = Number(summary.spot_exposure || 0);
  riskSummary.contract_exposure = Number(summary.contract_exposure || 0);
  riskSummary.total_exposure = Number(summary.total_exposure || 0);
  riskSummary.exposure_ratio = Number(summary.exposure_ratio || 0);
  riskSummary.floating_pnl = Number(summary.floating_pnl || 0);
};

const canLeaveEditor = () => {
  if (!editorDirty.value) return true;
  return window.confirm('当前外部策略文件有未保存修改，是否放弃这些更改？');
};

const castParamValue = (param, value) => {
  if (param.type === 'int') return Number.parseInt(value, 10);
  if (param.type === 'float') return Number.parseFloat(value);
  if (param.type === 'bool') return value === true || value === 'true';
  return value;
};

const resetLiveStrategyParams = () => {
  const strategy = activeExecutionStrategy.value;
  const next = {};
  (strategy?.params || []).forEach((param) => {
    if (param.type === 'bool') {
      next[param.name] = param.default ?? false;
      return;
    }
    next[param.name] = param.default ?? '';
  });
  liveStrategyParams.value = next;
};

const loadRegisteredSource = async (strategyId) => {
  if (!strategyId) return;

  try {
    const res = await api.getStrategySource(strategyId);
    if (res.code === 0 && res.data) {
      registeredSource.filename = res.data.filename || '';
      registeredSource.source = res.data.source || '# 当前策略没有可展示源码';
      registeredSource.strategyIds = [strategyId];
    }
  } catch (error) {
    registeredSource.filename = '';
    registeredSource.source = `# 加载源码失败\n# ${getErrorDetail(error)}`;
    registeredSource.strategyIds = [strategyId];
  }
};

const loadStrategies = async () => {
  const [strategyResult, liveStrategyResult] = await Promise.allSettled([
    api.getStrategies(),
    api.getLiveAvailableStrategies(),
  ]);

  if (strategyResult.status === 'fulfilled' && strategyResult.value.code === 0) {
    strategies.value = strategyResult.value.data || [];
  }

  if (liveStrategyResult.status === 'fulfilled') {
    liveStrategies.value = liveStrategyResult.value.strategies || [];
  }

  if (!selectedRegisteredStrategyId.value && strategies.value.length) {
    selectedRegisteredStrategyId.value = strategies.value[0].id;
  } else if (selectedRegisteredStrategyId.value && !strategies.value.some((item) => item.id === selectedRegisteredStrategyId.value)) {
    selectedRegisteredStrategyId.value = strategies.value[0]?.id || '';
  }

  if (!liveForm.strategyId && executionStrategyList.value.length) {
    liveForm.strategyId = executionStrategyList.value[0].id;
  } else if (liveForm.strategyId && !executionStrategyList.value.some((item) => item.id === liveForm.strategyId)) {
    liveForm.strategyId = executionStrategyList.value[0]?.id || '';
  }

  if (selectedSourceKind.value === 'registered' && selectedRegisteredStrategyId.value) {
    await loadRegisteredSource(selectedRegisteredStrategyId.value);
  }
};

const loadExternalFiles = async (preferredFilename = '') => {
  try {
    const res = await api.listExternalStrategyFiles();
    if (res.code === 0 && res.data) {
      externalFiles.value = res.data.files || [];
      externalDirectory.value = res.data.directory || '';

      if (
        selectedSourceKind.value === 'external' &&
        !editableFile.isNew &&
        !externalFiles.value.some((item) => item.filename === editableFile.filename)
      ) {
        createNewExternalFile(true);
      }

      if (preferredFilename && selectedSourceKind.value === 'external') {
        const matched = externalFiles.value.find((item) => item.filename === preferredFilename);
        if (matched && editableFile.filename !== preferredFilename) {
          await selectExternalFile(preferredFilename, true);
        }
      }
    }
  } catch (error) {
    console.error('加载外部策略文件失败:', error);
  }
};

const loadSymbolOptions = async () => {
  const symbols = new Set(['BTC-USDT', 'ETH-USDT', 'SOL-USDT']);
  const [availableResult, instrumentResult] = await Promise.allSettled([
    api.getAvailableSymbols(),
    api.getInstruments('SPOT'),
  ]);

  if (availableResult.status === 'fulfilled' && availableResult.value.code === 0) {
    (availableResult.value.data || []).forEach((symbol) => symbols.add(symbol));
  }

  if (instrumentResult.status === 'fulfilled') {
    (instrumentResult.value.data || [])
      .filter((item) => String(item.inst_id || '').endsWith('-USDT'))
      .slice(0, 200)
      .forEach((item) => symbols.add(item.inst_id));
  }

  symbolOptions.value = Array.from(symbols).sort();
};

const selectRegisteredStrategy = async (strategyId) => {
  if (!canLeaveEditor()) return;
  selectedSourceKind.value = 'registered';
  sidePanelTab.value = 'registered';
  selectedRegisteredStrategyId.value = strategyId;
  await loadRegisteredSource(strategyId);
};

const selectExternalFile = async (filename, force = false) => {
  if (!force && !canLeaveEditor()) return;

  try {
    const res = await api.getExternalStrategyFile(filename);
    if (res.code === 0 && res.data) {
      selectedSourceKind.value = 'external';
      sidePanelTab.value = 'external';
      editableFile.filename = res.data.filename;
      editableFile.source = res.data.source || '';
      editableFile.savedSource = res.data.source || '';
      editableFile.strategyIds = res.data.strategy_ids || [];
      editableFile.isNew = false;
    }
  } catch (error) {
    window.alert(`读取外部策略文件失败：${getErrorDetail(error)}`);
  }
};

const createNewExternalFile = (force = false) => {
  if (!force && !canLeaveEditor()) return;

  const template = buildStrategyTemplate('custom_strategy.py');
  selectedSourceKind.value = 'external';
  sidePanelTab.value = 'external';
  editableFile.filename = 'custom_strategy.py';
  editableFile.source = template;
  editableFile.savedSource = template;
  editableFile.strategyIds = [];
  editableFile.isNew = true;
};

const reloadAllStrategySources = async () => {
  reloadingStrategies.value = true;
  try {
    const res = await api.reloadStrategies();
    await Promise.all([loadStrategies(), loadExternalFiles(editableFile.filename)]);
    window.alert(res.message || '策略热加载完成');
  } catch (error) {
    window.alert(`策略热加载失败：${getErrorDetail(error)}`);
  } finally {
    reloadingStrategies.value = false;
  }
};

const saveExternalFile = async () => {
  if (selectedSourceKind.value !== 'external') return;
  if (!editableFile.filename) {
    window.alert('请先填写文件名');
    return;
  }

  sourceSaving.value = true;
  try {
    const res = await api.saveExternalStrategyFile({
      filename: editableFile.filename,
      source: editableFile.source,
    });
    editableFile.filename = res.data?.filename || editableFile.filename;
    editableFile.savedSource = editableFile.source;
    editableFile.strategyIds = res.data?.strategy_ids || [];
    editableFile.isNew = false;

    await Promise.all([loadStrategies(), loadExternalFiles(editableFile.filename)]);

    const suffix = editableFile.strategyIds.length
      ? `已注册：${editableFile.strategyIds.join(', ')}`
      : '文件已保存，但当前还未注册为可执行策略，请检查 strategy_id、class 定义或语法';
    window.alert(`${res.message || '保存成功'}\n${suffix}`);
  } catch (error) {
    window.alert(`保存外部策略失败：${getErrorDetail(error)}`);
  } finally {
    sourceSaving.value = false;
  }
};

const deleteExternalFile = async () => {
  if (editableFile.isNew) {
    createNewExternalFile(true);
    return;
  }

  if (!window.confirm(`确认删除外部策略文件 ${editableFile.filename} 吗？`)) return;

  sourceDeleting.value = true;
  try {
    const res = await api.deleteExternalStrategyFile(editableFile.filename);
    await Promise.all([loadStrategies(), loadExternalFiles()]);
    if (selectedRegisteredStrategyId.value) {
      await selectRegisteredStrategy(selectedRegisteredStrategyId.value);
    } else {
      createNewExternalFile(true);
    }
    window.alert(res.message || '文件已删除');
  } catch (error) {
    window.alert(`删除外部策略失败：${getErrorDetail(error)}`);
  } finally {
    sourceDeleting.value = false;
  }
};

const loadLiveState = async () => {
  try {
    const status = await api.getLiveStrategyStatus();
    Object.assign(liveStatus, {
      status: status.status || 'stopped',
      mode: status.mode || '',
      strategy_id: status.strategy_id || '',
      strategy_name: status.strategy_name || '',
      symbol: status.symbol || '',
      timeframe: status.timeframe || '',
      inst_type: status.inst_type || 'SPOT',
      start_time: status.start_time || null,
      last_signal_time: status.last_signal_time || null,
      last_signal_type: status.last_signal_type || '',
      total_signals: status.total_signals || 0,
      total_orders: status.total_orders || 0,
      successful_orders: status.successful_orders || 0,
      failed_orders: status.failed_orders || 0,
      error_message: status.error_message || '',
      check_interval: status.check_interval || 60,
    });

    const orderMode = liveStatus.mode || appStore.tradingMode;
    const ordersRes = await api.getLiveOrders(20, orderMode);
    liveOrders.value = ordersRes.orders || [];
  } catch (error) {
    console.error('加载实时策略状态失败:', error);
  }
};

const buildLivePayload = () => {
  const params = {};
  (activeExecutionStrategy.value?.params || []).forEach((param) => {
    const rawValue = liveStrategyParams.value[param.name];
    if (rawValue === '' || rawValue === null || rawValue === undefined) {
      return;
    }
    params[param.name] = castParamValue(param, rawValue);
  });

  return {
    strategyId: liveForm.strategyId,
    symbol: liveForm.symbol,
    timeframe: liveForm.timeframe,
    instType: 'SPOT',
    initialCapital: Number(liveForm.initialCapital),
    positionSize: Number(liveForm.positionSize),
    stopLoss: Number(liveForm.stopLoss),
    takeProfit: Number(liveForm.takeProfit),
    checkInterval: Number(liveForm.checkInterval),
    params,
  };
};

const startLiveStrategy = async () => {
  liveActionLoading.value = true;
  try {
    const payload = buildLivePayload();
    const res = await api.startLiveStrategy(payload);
    await loadLiveState();
    activeTab.value = 'execution';
    window.alert(res.message || '策略已启动');
  } catch (error) {
    window.alert(`启动策略失败：${getErrorDetail(error)}`);
  } finally {
    liveActionLoading.value = false;
  }
};

const stopLiveStrategy = async () => {
  liveActionLoading.value = true;
  try {
    const res = await api.stopLiveStrategy();
    await loadLiveState();
    window.alert(res.message || '策略已停止');
  } catch (error) {
    window.alert(`停止策略失败：${getErrorDetail(error)}`);
  } finally {
    liveActionLoading.value = false;
  }
};

const loadRiskSummary = async () => {
  try {
    const res = await api.getRiskSummary(appStore.tradingMode);
    updateRiskConfig(res.config || {});
    updateRiskSummary(res.summary || {});
  } catch (error) {
    console.error('加载风险摘要失败:', error);
  }
};

const saveRiskConfig = async () => {
  riskSaving.value = true;
  try {
    const res = await api.updateRiskControlConfig({
      enabled: riskConfig.enabled,
      max_single_loss_ratio: Number(riskConfig.max_single_loss_ratio),
      default_stop_loss_ratio: Number(riskConfig.default_stop_loss_ratio),
      max_total_position_ratio: Number(riskConfig.max_total_position_ratio),
    });
    updateRiskConfig(res.config || {});
    await loadRiskSummary();
    window.alert(res.message || '风控配置已更新');
  } catch (error) {
    window.alert(`保存风控配置失败：${getErrorDetail(error)}`);
  } finally {
    riskSaving.value = false;
  }
};

const formatMoney = (value) => {
  const number = Number(value || 0);
  return Number.isFinite(number)
    ? number.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '0.00';
};

const formatRatio = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;

const formatDateTime = (value) => {
  if (!value) return '-';
  const date = typeof value === 'number' || /^\d+$/.test(String(value))
    ? new Date(Number(value) * (String(value).length <= 10 ? 1000 : 1))
    : new Date(value);

  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

watch(
  () => liveForm.strategyId,
  () => {
    resetLiveStrategyParams();
  },
  { immediate: true }
);

watch(
  () => editableFile.filename,
  (value, oldValue) => {
    if (
      selectedSourceKind.value === 'external' &&
      editableFile.isNew &&
      editableFile.source === editableFile.savedSource &&
      value &&
      value !== oldValue
    ) {
      const template = buildStrategyTemplate(value);
      editableFile.source = template;
      editableFile.savedSource = template;
    }
  }
);

watch(
  () => appStore.tradingMode,
  async () => {
    await Promise.all([loadRiskSummary(), loadLiveState()]);
  }
);

onMounted(async () => {
  await Promise.all([
    loadStrategies(),
    loadExternalFiles(),
    loadSymbolOptions(),
    loadLiveState(),
    loadRiskSummary(),
  ]);

  if (!selectedRegisteredStrategyId.value && !externalFiles.value.length) {
    createNewExternalFile(true);
  }

  pollTimer = window.setInterval(() => {
    loadLiveState();
    loadRiskSummary();
  }, 8000);
});

onUnmounted(() => {
  if (pollTimer) {
    window.clearInterval(pollTimer);
  }
});
</script>
<style scoped src="../assets/styles/views/strategy-view.css"></style>
