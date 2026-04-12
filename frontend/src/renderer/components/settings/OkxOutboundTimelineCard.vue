<template>
  <div class="card okx-outbound-card">
    <div class="card-header compact">
      <div class="header-left">
        <span class="card-icon">&#128200;</span>
        <h3 class="card-title">OKX 出站时间线</h3>
      </div>
      <span class="status-badge small" :class="statusClass">
        {{ statusText }}
      </span>
    </div>

    <div class="okx-outbound-summary">
      <div class="summary-item">
        <span class="summary-label">10分钟事件</span>
        <span class="summary-value">{{ summary.eventCount }}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">错误事件</span>
        <span class="summary-value danger">{{ summary.errorCount }}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">最频繁</span>
        <span class="summary-value compact">{{ summary.topOperation }}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">最慢调用</span>
        <span class="summary-value compact">{{ summary.slowestOperation }}</span>
      </div>
    </div>

    <div class="okx-outbound-chart-shell">
      <div ref="chartEl" class="okx-outbound-chart"></div>
      <div v-if="overlayMessage" class="okx-outbound-overlay" :class="{ error: Boolean(errorMessage) }">
        {{ overlayMessage }}
      </div>
    </div>

    <div class="okx-outbound-meta">
      <span>仅统计后端实际发往 OKX 的出站事件</span>
      <span>窗口: {{ Math.round(props.windowSeconds / 60) }} 分钟</span>
      <span>更新时间: {{ generatedAtLabel }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import { api } from '../../services/api';
import { createChart, disposeChart, ensureChartResize } from '../../utils/chart';
import { buildOkxOutboundTimelineOption } from './okxOutboundTimelineChart.mjs';

const props = defineProps({
  active: {
    type: Boolean,
    default: false,
  },
  refreshKey: {
    type: Number,
    default: 0,
  },
  windowSeconds: {
    type: Number,
    default: 600,
  },
  pollIntervalMs: {
    type: Number,
    default: 5000,
  },
});

const chartEl = ref(null);
const loading = ref(false);
const errorMessage = ref('');
const snapshot = ref({
  events: [],
  summary: {
    event_count: 0,
    error_count: 0,
    top_operations: [],
    slowest_operations: [],
  },
  generated_at: null,
});

let chart = null;
let pollTimer = null;

const statusClass = computed(() => {
  if (errorMessage.value) return 'error';
  if (loading.value) return 'warning';
  return 'success';
});

const statusText = computed(() => {
  if (errorMessage.value) return '拉取失败';
  if (loading.value) return '更新中';
  return '实时';
});

const generatedAtLabel = computed(() => {
  if (!snapshot.value.generated_at) {
    return '--';
  }
  return new Date(snapshot.value.generated_at * 1000).toLocaleTimeString();
});

const overlayMessage = computed(() => {
  if (errorMessage.value) {
    return errorMessage.value;
  }
  if (loading.value && snapshot.value.events.length === 0) {
    return '正在拉取 OKX 出站时间线...';
  }
  if (!snapshot.value.events.length) {
    return '近 10 分钟没有实际发往 OKX 的调用事件';
  }
  return '';
});

const summary = computed(() => {
  const meta = snapshot.value.summary || {};
  const topOperation = meta.top_operations?.[0];
  const slowestOperation = meta.slowest_operations?.[0];
  return {
    eventCount: meta.event_count || 0,
    errorCount: meta.error_count || 0,
    topOperation: topOperation ? `${topOperation.op_key} · ${topOperation.count}` : '--',
    slowestOperation: slowestOperation ? `${slowestOperation.op_key} · ${slowestOperation.latency_ms}ms` : '--',
  };
});

const ensureChart = async () => {
  await nextTick();
  if (!chart && chartEl.value) {
    chart = createChart(chartEl.value);
  }
  return chart;
};

const renderChart = async () => {
  const chartInstance = await ensureChart();
  if (!chartInstance) {
    return;
  }
  chartInstance.setOption(
    buildOkxOutboundTimelineOption({
      windowSeconds: props.windowSeconds,
      generatedAt: snapshot.value.generated_at || Date.now() / 1000,
      events: snapshot.value.events || [],
    }),
    { notMerge: true, lazyUpdate: true },
  );
  if (props.active) {
    ensureChartResize(chartInstance);
  }
};

const refresh = async () => {
  if (loading.value) {
    return;
  }
  loading.value = true;
  try {
    const payload = await api.getOkxOutboundTimeline({
      window_seconds: props.windowSeconds,
      limit: 2000,
    });
    snapshot.value = payload;
    errorMessage.value = '';
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '时间线拉取失败';
  } finally {
    loading.value = false;
    await renderChart();
  }
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

const startPolling = async () => {
  stopPolling();
  if (!props.active) {
    return;
  }
  await refresh();
  pollTimer = setInterval(refresh, props.pollIntervalMs);
};

watch(() => props.active, async (active) => {
  if (!active) {
    stopPolling();
    return;
  }
  await startPolling();
});

watch(() => props.refreshKey, async () => {
  if (props.active) {
    await refresh();
  }
});

onMounted(async () => {
  await ensureChart();
  if (props.active) {
    await startPolling();
  } else {
    await renderChart();
  }
});

onUnmounted(() => {
  stopPolling();
  if (chart) {
    disposeChart(chart);
    chart = null;
  }
});
</script>

<style scoped>
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
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
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

.status-badge {
  padding: 3px 10px;
  font-size: 10px;
  border-radius: 20px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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

.okx-outbound-card {
  grid-column: span 2;
  min-width: 0;
}

.okx-outbound-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.summary-item {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(15, 23, 42, 0.16)),
    radial-gradient(circle at top right, rgba(245, 158, 11, 0.08), transparent 55%);
}

.summary-label {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.summary-value {
  display: block;
  min-width: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-value.compact {
  font-size: 13px;
  line-height: 1.35;
  word-break: break-word;
}

.summary-value.danger {
  color: var(--color-danger);
}

.okx-outbound-chart-shell {
  position: relative;
  min-height: 280px;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(15, 23, 42, 0.92)),
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.06), transparent 32%);
}

.okx-outbound-chart {
  width: 100%;
  height: 280px;
}

.okx-outbound-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  background: rgba(15, 23, 42, 0.72);
  backdrop-filter: blur(4px);
}

.okx-outbound-overlay.error {
  color: #fecaca;
}

.okx-outbound-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 14px;
  font-size: 11px;
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .okx-outbound-card {
    grid-column: span 1;
  }
}

@media (max-width: 900px) {
  .okx-outbound-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .okx-outbound-summary {
    grid-template-columns: 1fr;
  }
}
</style>
