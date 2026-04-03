<template>
  <div class="settings-view">
    <!-- 命令栏 -->
    <header class="sv-command-bar">
      <div class="sv-left">
        <h1 class="sv-title">系统设置</h1>
        <nav class="sv-tabs">
          <button class="sv-tab" :class="{ active: settingsTab === 'config' }" @click="settingsTab = 'config'">配置管理</button>
          <button class="sv-tab" :class="{ active: settingsTab === 'monitor' }" @click="settingsTab = 'monitor'">状态监控</button>
        </nav>
      </div>
      <div class="sv-right">
        <button class="btn btn-sm" :class="{ spinning: isRefreshing }" @click="refreshStatus" :disabled="isRefreshing">
          {{ isRefreshing ? '刷新中' : '刷新' }}
        </button>
      </div>
    </header>

    <!-- 配置管理 tab -->
    <div v-show="settingsTab === 'config'" class="sv-panel">
      <div class="settings-main">
        <div class="card okx-config-card">
          <div class="card-header">
            <div class="header-left">
              <span class="card-icon">&#9830;</span>
              <h3 class="card-title">OKX API 配置</h3>
            </div>
            <span class="status-badge" :class="okxStatus.apiAccessible ? 'success' : 'warning'">
              {{ okxStatus.apiAccessible ? '已连接' : '未连接' }}
            </span>
          </div>

          <!-- 当前状态概览 -->
          <div class="okx-overview">
            <div class="overview-item">
              <span class="overview-label">当前模式</span>
              <span class="overview-value" :class="okxConfig.useSimulated ? 'simulated' : 'live'">
                {{ okxConfig.useSimulated ? '模拟盘' : '实盘' }}
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">BTC 价格</span>
              <span class="overview-value price">
                {{ okxStatus.btcPrice ? '$' + okxStatus.btcPrice.toLocaleString() : '--' }}
              </span>
            </div>
          </div>

          <!-- 模式选择 -->
          <div class="mode-selector">
            <label class="mode-option" :class="{ active: okxConfig.useSimulated }">
              <input type="radio" v-model="okxConfig.useSimulated" :value="true" />
              <div class="mode-content">
                <span class="mode-icon simulated">&#9673;</span>
                <div class="mode-info">
                  <span class="mode-label">模拟盘</span>
                  <span class="mode-desc">使用虚拟资金进行测试交易</span>
                </div>
              </div>
              <span class="mode-status" :class="okxConfigStatus.demo.isConfigured ? 'configured' : ''">
                {{ okxConfigStatus.demo.isConfigured ? '已配置' : '未配置' }}
              </span>
            </label>
            <label class="mode-option" :class="{ active: !okxConfig.useSimulated }">
              <input type="radio" v-model="okxConfig.useSimulated" :value="false" />
              <div class="mode-content">
                <span class="mode-icon live">&#9673;</span>
                <div class="mode-info">
                  <span class="mode-label">实盘</span>
                  <span class="mode-desc">使用真实资金进行交易</span>
                </div>
              </div>
              <span class="mode-status" :class="okxConfigStatus.live.isConfigured ? 'configured' : ''">
                {{ okxConfigStatus.live.isConfigured ? '已配置' : '未配置' }}
              </span>
            </label>
          </div>

          <!-- API 密钥配置区 -->
          <div class="api-config-area">
            <!-- 模拟盘配置 -->
            <div class="credentials-section" :class="{ active: okxConfig.useSimulated }">
              <div class="section-header">
                <div class="section-title">
                  <span class="dot simulated"></span>
                  <span>模拟盘 API 密钥</span>
                </div>
                <a href="https://www.okx.com/zh-hans/demo-trading" target="_blank" class="help-link">获取密钥</a>
              </div>
              <div class="credentials-form">
                <div class="form-row">
                  <label>API Key</label>
                  <input type="text" v-model="okxConfig.demo.apiKey" class="input" placeholder="输入模拟盘 API Key" />
                </div>
                <div class="form-row">
                  <label>Secret Key</label>
                  <input type="password" v-model="okxConfig.demo.secretKey" class="input" placeholder="输入模拟盘 Secret Key" />
                </div>
                <div class="form-row">
                  <label>Passphrase</label>
                  <input type="password" v-model="okxConfig.demo.passphrase" class="input" placeholder="输入模拟盘 Passphrase" />
                </div>
              </div>
            </div>

            <!-- 实盘配置 -->
            <div class="credentials-section" :class="{ active: !okxConfig.useSimulated }">
              <div class="section-header">
                <div class="section-title">
                  <span class="dot live"></span>
                  <span>实盘 API 密钥</span>
                </div>
                <a href="https://www.okx.com/account/my-api" target="_blank" class="help-link">获取密钥</a>
              </div>
              <div class="credentials-form">
                <div class="form-row">
                  <label>API Key</label>
                  <input type="text" v-model="okxConfig.live.apiKey" class="input" placeholder="输入实盘 API Key" />
                </div>
                <div class="form-row">
                  <label>Secret Key</label>
                  <input type="password" v-model="okxConfig.live.secretKey" class="input" placeholder="输入实盘 Secret Key" />
                </div>
                <div class="form-row">
                  <label>Passphrase</label>
                  <input type="password" v-model="okxConfig.live.passphrase" class="input" placeholder="输入实盘 Passphrase" />
                </div>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <button class="btn btn-primary" @click="saveOKXConfig" :disabled="savingOKXConfig">
              {{ savingOKXConfig ? '保存中...' : '保存配置' }}
            </button>
            <button class="btn btn-secondary" @click="testOKXConnection" :disabled="testingOKXConnection">
              {{ testingOKXConnection ? '测试中...' : '测试连接' }}
            </button>
          </div>

          <!-- 提示信息 -->
          <div class="config-tip">
            <div class="tip-icon">&#9432;</div>
            <div class="tip-content">
              <p><strong>模拟盘：</strong>登录 OKX 后进入 交易 > 模拟交易，点击右上角用户图标选择 Demo Trading API</p>
              <p><strong>实盘：</strong>登录 OKX 后进入 用户中心 > API 创建，需开启读取和交易权限</p>
              <p><strong>默认模式：</strong>仅影响交易动作（下单/撤单/合约设置/策略运行）。即使同时配置两套密钥，也可以在“模拟盘交易/实盘交易”页分别查看两套盘的数据。</p>
            </div>
          </div>
        </div>

        <div class="card assistant-config-card">
          <div class="card-header">
            <div class="header-left">
              <span class="card-icon">&#129302;</span>
              <h3 class="card-title">AI 助手配置</h3>
            </div>
            <span
              class="status-badge"
              :class="assistantConfig.enabled ? (assistantStatus.configured ? 'success' : 'warning') : 'error'"
            >
              {{ assistantConfig.enabled ? (assistantStatus.configured ? '已配置' : '待配置') : '已停用' }}
            </span>
          </div>

          <div class="assistant-overview">
            <div class="overview-item">
              <span class="overview-label">当前模型</span>
              <span class="overview-value assistant-value">
                {{ assistantConfig.model || '--' }}
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">服务商</span>
              <span class="overview-value assistant-value">
                {{ assistantConfig.providerName || '--' }}
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">密钥状态</span>
              <span class="overview-value" :class="assistantStatus.hasKey ? 'simulated' : 'live'">
                {{ assistantStatus.hasKey ? '已保存' : '未保存' }}
              </span>
            </div>
          </div>

          <div class="assistant-toggle-row">
            <label class="checkbox-toggle">
              <input v-model="assistantConfig.enabled" type="checkbox" />
              <span>启用行情页 AI 助手与 Agent 分析</span>
            </label>
            <span class="mode-status" :class="{ configured: assistantStatus.configured }">
              {{ assistantStatus.providerName || assistantConfig.providerName || 'OpenAI-Compatible' }}
            </span>
          </div>

          <div class="credentials-section active assistant-credentials-section">
            <div class="section-header">
              <div class="section-title">
                <span class="dot simulated"></span>
                <span>AI 模型接入参数</span>
              </div>
            </div>
            <div class="credentials-form assistant-form-grid">
              <div class="form-row">
                <label>Base URL</label>
                <input
                  type="text"
                  v-model="assistantConfig.baseUrl"
                  class="input"
                  placeholder="https://api.openai.com/v1"
                />
              </div>
              <div class="form-row">
                <label>Provider</label>
                <input
                  type="text"
                  v-model="assistantConfig.providerName"
                  class="input"
                  placeholder="OpenAI-Compatible"
                />
              </div>
              <div class="form-row">
                <label>Model</label>
                <input
                  type="text"
                  v-model="assistantConfig.model"
                  class="input"
                  placeholder="gpt-4.1-mini"
                />
              </div>
              <div class="form-row assistant-api-key-row">
                <label>API Key</label>
                <input
                  type="password"
                  v-model="assistantConfig.apiKey"
                  class="input"
                  placeholder="留空表示保留当前已保存密钥"
                />
                <span v-if="assistantStatus.apiKeyMasked" class="field-tip">
                  当前已保存：{{ assistantStatus.apiKeyMasked }}
                </span>
              </div>
            </div>
          </div>

          <div class="action-buttons">
            <button class="btn btn-primary" @click="saveAssistantConfig" :disabled="savingAssistantConfig">
              {{ savingAssistantConfig ? '保存中...' : '保存 AI 配置' }}
            </button>
          </div>

          <div class="config-tip">
            <div class="tip-icon">&#9432;</div>
            <div class="tip-content">
              <p><strong>用途：</strong>该配置会直接驱动行情页 AI 助手、Agent 工具调用与会话分析。</p>
              <p><strong>安全：</strong>输入框留空不会清空现有密钥，只会保留服务器已保存的值。</p>
              <p><strong>建议：</strong>如果使用 OpenAI 兼容接口，优先填写完整的 Base URL、模型名和 API Key。</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 状态监控 tab -->
    <div v-show="settingsTab === 'monitor'" class="sv-panel">
      <div class="monitor-grid">
        <!-- 系统状态 -->
        <div class="card">
          <div class="card-header compact">
            <div class="header-left">
              <span class="card-icon">&#9881;</span>
              <h3 class="card-title">系统状态</h3>
            </div>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ systemStatus.uptime || '--' }}</span>
              <span class="stat-label">运行时间</span>
            </div>
            <div class="stat-item">
              <span class="stat-value highlight">{{ systemStatus.memoryMb ? systemStatus.memoryMb + ' MB' : '--' }}</span>
              <span class="stat-label">内存占用</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ systemStatus.cpuPercent !== undefined ? systemStatus.cpuPercent + '%' : '--' }}</span>
              <span class="stat-label">CPU</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ systemStatus.pid || '--' }}</span>
              <span class="stat-label">进程ID</span>
            </div>
          </div>
          <div class="stats-meta">
            <span>{{ systemStatus.pythonVersion || 'Python --' }}</span>
            <span class="divider">|</span>
            <span>{{ systemStatus.os || '--' }}</span>
          </div>
        </div>

        <!-- API调用频率 -->
        <div class="card">
          <div class="card-header compact">
            <div class="header-left">
              <span class="card-icon">&#9889;</span>
              <h3 class="card-title">API 调用</h3>
            </div>
            <span class="status-badge small" :class="getRateLimitClass()">
              {{ rateLimitStatus.usagePercent }}%
            </span>
          </div>
          <div class="rate-limit-bar">
            <div class="rate-limit-progress" :style="{ width: rateLimitStatus.usagePercent + '%' }" :class="getRateLimitClass()"></div>
          </div>
          <div class="stats-row">
            <div class="stat-mini">
              <span class="value">{{ rateLimitStatus.callsPerMinute }}</span>
              <span class="label">当前/分钟</span>
            </div>
            <div class="stat-mini">
              <span class="value">{{ rateLimitStatus.remainingQuota }}</span>
              <span class="label">剩余配额</span>
            </div>
            <div class="stat-mini">
              <span class="value">{{ rateLimitStatus.totalCalls.toLocaleString() }}</span>
              <span class="label">总调用</span>
            </div>
          </div>
        </div>

        <!-- 缓存状态 -->
        <div class="card">
          <div class="card-header compact">
            <div class="header-left">
              <span class="card-icon">&#9736;</span>
              <h3 class="card-title">缓存</h3>
            </div>
          </div>
          <div class="stats-row">
            <div class="stat-mini">
              <span class="value">{{ cacheStatus.candleEntries }}</span>
              <span class="label">K线</span>
            </div>
            <div class="stat-mini">
              <span class="value">{{ cacheStatus.tickerEntries }}</span>
              <span class="label">Ticker</span>
            </div>
            <div class="stat-mini">
              <span class="value">{{ cacheStatus.syncCooldowns }}</span>
              <span class="label">冷却</span>
            </div>
          </div>
        </div>

        <!-- 数据存储 -->
        <div class="card">
          <div class="card-header compact">
            <div class="header-left">
              <span class="card-icon">&#9776;</span>
              <h3 class="card-title">数据存储</h3>
            </div>
          </div>
          <div class="stats-row">
            <div class="stat-mini">
              <span class="value">{{ dataStatus.symbolCount }}</span>
              <span class="label">交易对</span>
            </div>
            <div class="stat-mini">
              <span class="value highlight">{{ dataStatus.candleCount.toLocaleString() }}</span>
              <span class="label">K线总数</span>
            </div>
            <div class="stat-mini">
              <span class="value">{{ dataStatus.dbSize || '0 B' }}</span>
              <span class="label">数据库</span>
            </div>
          </div>
          <div class="stats-meta">
            <span>最后同步: {{ dataStatus.lastSync || '从未' }}</span>
          </div>
        </div>

        <!-- 后端连接 -->
        <div class="card">
          <div class="card-header compact">
            <div class="header-left">
              <span class="card-icon">&#9951;</span>
              <h3 class="card-title">后端服务</h3>
            </div>
            <span class="status-badge small" :class="isConnected ? 'success' : 'error'">
              {{ isConnected ? '在线' : '离线' }}
            </span>
          </div>
          <div class="backend-config">
            <input type="text" v-model="backendUrl" class="input input-sm" placeholder="http://127.0.0.1:8000" />
            <button class="btn btn-sm btn-primary" @click="saveBackendUrl">保存</button>
          </div>
        </div>

        <!-- 关于 -->
        <div class="card">
          <div class="card-header compact">
            <div class="header-left">
              <span class="card-icon">&#9432;</span>
              <h3 class="card-title">关于</h3>
            </div>
          </div>
          <div class="about-info">
            <div class="about-row">
              <span class="label">应用</span>
              <span class="value">OKX量化交易系统</span>
            </div>
            <div class="about-row">
              <span class="label">版本</span>
              <span class="value version">v0.1.0</span>
            </div>
            <div class="about-row">
              <span class="label">技术栈</span>
              <span class="value">Electron + Vue3 + FastAPI</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { api, updateBaseURL, getBaseURL } from '../services/api';
import { useAppStore } from '../stores/app';

// 状态
const settingsTab = ref('config');
const isConnected = ref(false);
const isRefreshing = ref(false);
const savingOKXConfig = ref(false);
const savingAssistantConfig = ref(false);
const testingOKXConnection = ref(false);

// 后端地址
const backendUrl = ref('');

// 全局应用状态（用于同步左下角“默认模式”展示）
const appStore = useAppStore();

// OKX配置（模拟盘 + 实盘两组密钥）
const okxConfig = reactive({
  demo: {
    apiKey: '',
    secretKey: '',
    passphrase: '',
  },
  live: {
    apiKey: '',
    secretKey: '',
    passphrase: '',
  },
  useSimulated: true,
});

// OKX配置状态（从后端加载的状态信息）
const okxConfigStatus = reactive({
  demo: { isConfigured: false },
  live: { isConfigured: false },
});

const assistantConfig = reactive({
  enabled: true,
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  model: 'gpt-4.1-mini',
  providerName: 'OpenAI-Compatible',
});

const assistantStatus = reactive({
  configured: false,
  enabled: true,
  hasKey: false,
  apiKeyMasked: '',
  providerName: '',
});

// 系统状态
const systemStatus = reactive({
  uptime: null,
  pythonVersion: null,
  os: null,
  pid: null,
  memoryMb: null,
  cpuPercent: null,
});

// OKX状态
const okxStatus = reactive({
  apiConfigured: false,
  apiAccessible: false,
  btcPrice: null,
});

// 缓存状态
const cacheStatus = reactive({
  candleEntries: 0,
  tickerEntries: 0,
  syncCooldowns: 0,
});

// 数据状态
const dataStatus = reactive({
  symbolCount: 0,
  candleCount: 0,
  dbSize: '0 B',
  lastSync: null,
});

// API调用频率状态
const rateLimitStatus = reactive({
  totalCalls: 0,
  callsPerMinute: 0,
  rateLimit: 3000,
  remainingQuota: 3000,
  usagePercent: 0,
});

// 获取频率限制进度条的样式类
const getRateLimitClass = () => {
  if (rateLimitStatus.usagePercent < 50) return 'success';
  if (rateLimitStatus.usagePercent < 80) return 'warning';
  return 'error';
};

// 刷新系统状态
const refreshStatus = async () => {
  if (isRefreshing.value) return;

  isRefreshing.value = true;
  try {
    const result = await api.getSystemStatus();
    isConnected.value = true;

    // 系统信息
    if (result.system) {
      systemStatus.uptime = result.system.uptime;
      systemStatus.pythonVersion = result.system.python_version;
      systemStatus.os = result.system.os;
      systemStatus.pid = result.system.pid;
      systemStatus.memoryMb = result.system.memory_mb;
      systemStatus.cpuPercent = result.system.cpu_percent;
    }

    // OKX状态
    if (result.okx) {
      okxStatus.apiConfigured = result.okx.api_configured;
      okxStatus.apiAccessible = result.okx.api_accessible;
      okxStatus.btcPrice = result.okx.btc_price;
    }

    // 缓存状态
    if (result.cache) {
      cacheStatus.candleEntries = result.cache.candle_entries;
      cacheStatus.tickerEntries = result.cache.ticker_entries;
      cacheStatus.syncCooldowns = result.cache.sync_cooldowns;
    }

    // 数据状态
    if (result.data) {
      dataStatus.symbolCount = result.data.symbol_count;
      dataStatus.candleCount = result.data.candle_count;
      dataStatus.dbSize = result.data.db_size;
      dataStatus.lastSync = result.data.last_sync;
    }

    // API调用频率状态
    if (result.rate_limit) {
      rateLimitStatus.totalCalls = result.rate_limit.total_calls;
      rateLimitStatus.callsPerMinute = result.rate_limit.calls_per_minute;
      rateLimitStatus.rateLimit = result.rate_limit.rate_limit;
      rateLimitStatus.remainingQuota = result.rate_limit.remaining_quota;
      rateLimitStatus.usagePercent = result.rate_limit.usage_percent;
    }
  } catch (error) {
    isConnected.value = false;
    console.error('加载系统状态失败:', error);
  } finally {
    isRefreshing.value = false;
  }
};

// 加载OKX配置
// 注意：后端返回的密钥是遮蔽后的（如 ab12****ef34），不能回填到输入框
// 否则用户点保存会把遮蔽值写入 .env，导致 API 认证失败
const loadOKXConfig = async () => {
  try {
    const result = await api.getOKXConfig();
    // 不回填遮蔽后的密钥，仅加载配置状态和当前模式
    okxConfig.useSimulated = result.use_simulated !== false;
    // 同步到全局状态：让侧边栏左下角模式徽章即时更新
    appStore.setSimulated(okxConfig.useSimulated);
    okxConfigStatus.demo.isConfigured = result.demo?.is_configured || false;
    okxConfigStatus.live.isConfigured = result.live?.is_configured || false;
  } catch (error) {
    console.error('加载OKX配置失败:', error);
  }
};

const loadAssistantConfig = async () => {
  try {
    const result = await api.getAssistantConfig();
    assistantConfig.enabled = result.enabled !== false;
    assistantConfig.baseUrl = result.base_url || 'https://api.openai.com/v1';
    assistantConfig.apiKey = '';
    assistantConfig.model = result.model || 'gpt-4.1-mini';
    assistantConfig.providerName = result.provider_name || 'OpenAI-Compatible';

    assistantStatus.configured = !!result.configured;
    assistantStatus.enabled = result.enabled !== false;
    assistantStatus.apiKeyMasked = result.api_key || '';
    assistantStatus.hasKey = Boolean(result.api_key);
    assistantStatus.providerName = result.provider_name || 'OpenAI-Compatible';
  } catch (error) {
    console.error('加载 AI 助手配置失败:', error);
  }
};

// 保存OKX配置
const saveOKXConfig = async () => {
  // 检查当前模式对应的配置是否填写完整
  const currentConfig = okxConfig.useSimulated ? okxConfig.demo : okxConfig.live;
  const modeName = okxConfig.useSimulated ? '模拟盘' : '实盘';

  // 如果当前模式的配置为空，但之前已配置过，则允许保存（保留原有配置）
  const currentStatus = okxConfig.useSimulated ? okxConfigStatus.demo : okxConfigStatus.live;
  const hasNewInput = currentConfig.apiKey || currentConfig.secretKey || currentConfig.passphrase;
  const isIncomplete = hasNewInput && (!currentConfig.apiKey || !currentConfig.secretKey || !currentConfig.passphrase);

  if (isIncomplete) {
    alert(`${modeName}配置不完整，请填写完整的 API Key、Secret Key 和 Passphrase`);
    return;
  }

  savingOKXConfig.value = true;
  try {
    const result = await api.saveOKXConfig({
      demo: okxConfig.demo,
      live: okxConfig.live,
      useSimulated: okxConfig.useSimulated,
    });
    alert(result.message || '配置已保存');
    await loadOKXConfig();
    await refreshStatus();
  } catch (error) {
    alert('保存配置失败: ' + error.message);
  } finally {
    savingOKXConfig.value = false;
  }
};

// 测试OKX API连接
const testOKXConnection = async () => {
  testingOKXConnection.value = true;
  try {
    const result = await api.testOKXConnection();
    if (result.success) {
      alert(result.message);
      await refreshStatus();
    } else {
      alert('测试失败: ' + result.message);
    }
  } catch (error) {
    alert('测试失败: ' + error.message);
  } finally {
    testingOKXConnection.value = false;
  }
};

const saveAssistantConfig = async () => {
  const hasStoredKey = assistantStatus.hasKey;
  const hasNewApiKey = assistantConfig.apiKey.trim();

  if (assistantConfig.enabled && !hasNewApiKey && !hasStoredKey) {
    alert('请填写 AI Assistant API Key');
    return;
  }

  if (assistantConfig.enabled && !assistantConfig.model.trim()) {
    alert('请填写 AI 模型名称');
    return;
  }

  if (assistantConfig.enabled && !assistantConfig.baseUrl.trim()) {
    alert('请填写 AI Base URL');
    return;
  }

  savingAssistantConfig.value = true;
  try {
    const result = await api.saveAssistantConfig({
      enabled: assistantConfig.enabled,
      baseUrl: assistantConfig.baseUrl.trim(),
      apiKey: assistantConfig.apiKey.trim(),
      model: assistantConfig.model.trim(),
      providerName: assistantConfig.providerName.trim(),
    });
    alert(result.message || 'AI 配置已保存');
    await loadAssistantConfig();
  } catch (error) {
    alert('保存 AI 配置失败: ' + error.message);
  } finally {
    savingAssistantConfig.value = false;
  }
};

// 保存后端地址
const saveBackendUrl = () => {
  const url = backendUrl.value.trim();
  if (!url) {
    alert('请输入后端地址');
    return;
  }
  updateBaseURL(url);
  localStorage.setItem('backend-url', url);
  alert('后端地址已保存');
  refreshStatus();
};

// 加载后端地址
const loadBackendUrl = () => {
  const saved = localStorage.getItem('backend-url');
  backendUrl.value = saved || getBaseURL();
};

onMounted(() => {
  loadBackendUrl();
  refreshStatus();
  loadOKXConfig();
  loadAssistantConfig();
});
</script>

<style scoped>
.settings-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

/* 命令栏 */
.sv-command-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 20px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.sv-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.sv-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
  background: linear-gradient(to right, var(--text-primary), var(--accent-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sv-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.sv-tab {
  padding: 6px 18px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: 0.3px;
  border-radius: var(--radius-pill);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s ease;
}

.sv-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.sv-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #EA580C, #F7931A);
  box-shadow: 0 0 16px -4px rgba(247, 147, 26, 0.4);
}

.sv-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* tab 面板 */
.sv-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
}

/* 状态监控网格 */
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn-refresh:hover {
  background: var(--accent-bg);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.btn-refresh .refresh-icon {
  font-size: 16px;
}

.btn-refresh.spinning .refresh-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 主内容区 */
.settings-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 右侧边栏 */
.settings-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 卡片通用样式 */
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 20px;
  transition: border-color 0.2s ease;
}

.card:hover {
  border-color: rgba(247, 147, 26, 0.32);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.card-header.compact {
  margin-bottom: 14px;
  padding-bottom: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-icon {
  font-size: 18px;
  color: var(--accent-color);
}

.card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 状态徽章 */
.status-badge {
  padding: 5px 12px;
  font-size: 11px;
  border-radius: 20px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-badge.small {
  padding: 3px 10px;
  font-size: 10px;
}

.status-badge.success {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-badge.warning {
  background: rgba(247, 147, 26, 0.15);
  color: var(--accent-color);
  border: 1px solid rgba(247, 147, 26, 0.3);
}

.status-badge.error {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* ========== OKX 配置卡片 ========== */
.okx-config-card {
  padding: 24px;
}

.assistant-config-card {
  padding: 24px;
}

.okx-overview {
  display: flex;
  gap: 32px;
  padding: 16px 20px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.overview-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.overview-value.simulated {
  color: var(--accent-color);
}

.overview-value.live {
  color: var(--color-danger);
}

.overview-value.price {
  color: var(--color-success);
  font-family: var(--font-mono);
}

.overview-value.assistant-value {
  color: var(--secondary-color);
  font-size: 15px;
}

.assistant-overview {
  display: flex;
  gap: 24px;
  padding: 16px 20px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, rgba(234, 88, 12, 0.08) 100%);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}

.assistant-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.checkbox-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
}

.checkbox-toggle input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent-color);
}

.assistant-credentials-section {
  opacity: 1;
}

.assistant-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.assistant-api-key-row {
  grid-column: 1 / -1;
}

.field-tip {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  word-break: break-all;
}

/* 模式选择器 */
.mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: var(--bg-tertiary);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.mode-option:hover {
  border-color: var(--text-muted);
}

.mode-option.active {
  border-color: var(--accent-color);
  background: var(--accent-bg);
  box-shadow: 0 0 20px rgba(247, 147, 26, 0.15);
}

.mode-option input[type="radio"] {
  display: none;
}

.mode-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.mode-icon {
  font-size: 24px;
}

.mode-icon.simulated {
  color: var(--accent-color);
  text-shadow: 0 0 10px var(--accent-glow);
}

.mode-icon.live {
  color: var(--color-danger);
  text-shadow: 0 0 10px rgba(239, 68, 68, 0.32);
}

.mode-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mode-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.mode-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.mode-status {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 12px;
  background: var(--bg-primary);
  color: var(--text-muted);
}

.mode-status.configured {
  background: rgba(34, 197, 94, 0.14);
  color: var(--color-success);
}

/* API 配置区 */
.api-config-area {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.credentials-section {
  padding: 18px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  opacity: 0.6;
  transition: border-color 0.2s ease, background-color 0.2s ease, opacity 0.2s ease;
}

.credentials-section.active {
  opacity: 1;
  border-color: var(--accent-color);
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, rgba(247, 147, 26, 0.07) 100%);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-title .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.section-title .dot.simulated {
  background: var(--accent-color);
  box-shadow: 0 0 8px var(--accent-glow);
}

.section-title .dot.live {
  background: var(--color-danger);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.32);
}

.help-link {
  font-size: 11px;
  font-weight: 500;
  color: var(--secondary-color);
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 10px;
  background: var(--secondary-bg);
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.help-link:hover {
  background: var(--secondary-color);
  color: #FFFFFF;
}

.credentials-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-row label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-row .input {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 13px;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.form-row .input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-bg);
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.action-buttons .btn {
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 600;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  color: #FFFFFF;
}

.btn-primary:hover:not(:disabled) {
  box-shadow: var(--shadow-glow);
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--text-muted);
}

.btn-sm {
  padding: 8px 14px;
  font-size: 12px;
}

/* 提示信息 */
.config-tip {
  display: flex;
  gap: 14px;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--secondary-color);
}

.tip-icon {
  font-size: 18px;
  color: var(--secondary-color);
  flex-shrink: 0;
}

.tip-content p {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 6px 0;
}

.tip-content p:last-child {
  margin-bottom: 0;
}

.tip-content strong {
  color: var(--accent-color);
}

/* ========== 右侧统计卡片 ========== */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-value.highlight {
  color: var(--accent-color);
}

.stat-label {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stats-meta {
  font-size: 11px;
  color: var(--text-muted);
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
}

.stats-meta .divider {
  margin: 0 8px;
  color: var(--border-color);
}

.stats-row {
  display: flex;
  gap: 12px;
}

.stat-mini {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.stat-mini .value {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-mini .value.highlight {
  color: var(--accent-color);
}

.stat-mini .label {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
}

/* API 进度条 */
.rate-limit-bar {
  height: 6px;
  background: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 14px;
}

.rate-limit-progress {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.rate-limit-progress.success {
  background: linear-gradient(90deg, var(--color-success) 0%, #16A34A 100%);
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.32);
}

.rate-limit-progress.warning {
  background: linear-gradient(90deg, var(--accent-color) 0%, #D97706 100%);
  box-shadow: 0 0 8px rgba(247, 147, 26, 0.32);
}

.rate-limit-progress.error {
  background: linear-gradient(90deg, var(--color-danger) 0%, #DC2626 100%);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.32);
}

/* 后端配置 */
.backend-config {
  display: flex;
  gap: 8px;
}

.backend-config .input {
  flex: 1;
}

.input-sm {
  padding: 8px 12px;
  font-size: 12px;
}

/* 关于信息 */
.about-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.about-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.about-row .label {
  font-size: 12px;
  color: var(--text-muted);
}

.about-row .value {
  font-size: 12px;
  color: var(--text-primary);
}

.about-row .value.version {
  color: var(--secondary-color);
  font-weight: 600;
}

/* 响应式 */
@media (max-width: 1200px) {
  .settings-content {
    grid-template-columns: 1fr;
  }

  .settings-sidebar {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .api-config-area {
    grid-template-columns: 1fr;
  }

  .assistant-form-grid,
  .mode-selector {
    grid-template-columns: 1fr;
  }

  .assistant-overview,
  .assistant-toggle-row {
    flex-direction: column;
    align-items: stretch;
  }

  .settings-sidebar {
    grid-template-columns: 1fr;
  }
}
</style>
