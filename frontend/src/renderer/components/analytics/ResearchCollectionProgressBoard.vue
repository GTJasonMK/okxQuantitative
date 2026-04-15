<template>
  <section class="card trend-research-card">
    <div class="collection-progress-head">
      <div>
        <h4>采集进度</h4>
        <p>把计划完成度、建窗准备度和下个 15m 边界拆开显示，直接看到当前采样阶段。</p>
      </div>
      <span class="trend-state-badge" :class="badgeTone">
        {{ statusLabel }}
      </span>
    </div>
    <div class="collection-progress-grid">
      <article v-for="card in summaryCards" :key="card.label" class="trend-summary-stat">
        <span class="trend-summary-stat-label">{{ card.label }}</span>
        <strong class="trend-summary-stat-value">{{ card.value }}</strong>
        <small class="collection-progress-caption">{{ card.caption }}</small>
      </article>
    </div>
    <div class="collection-progress-bars">
      <section v-for="bar in progressBars" :key="bar.label" class="collection-progress-row">
        <div class="collection-progress-row-head">
          <strong>{{ bar.label }}</strong>
          <span>{{ bar.value }}</span>
        </div>
        <div class="collection-progress-track">
          <span class="collection-progress-fill" :style="{ width: bar.width }"></span>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const FULL_WINDOW_SECONDS = 7200;
const BOUNDARY_SECONDS = 900;

const props = defineProps({
  session: {
    type: Object,
    default: null,
  },
  coverage: {
    type: Object,
    default: () => ({}),
  },
  progress: {
    type: Object,
    default: () => ({}),
  },
});

const summaryCards = computed(() => [
  buildCard('已写入秒条', `${Number(props.progress?.writtenSeconds || 0)}`, '当前会话累计秒数'),
  buildCard('剩余计划秒数', formatSeconds(props.progress?.remainingSeconds), '距离本次计划结束'),
  buildCard('距完整 7200s', formatSeconds(props.progress?.secondsToFullWindow), '达到可建窗样本所需'),
  buildCard('距下个 15m 边界', formatSeconds(props.progress?.secondsToNextBoundary), '下一次标签对齐时刻'),
  buildCard('覆盖率', formatPercent(props.coverage?.coverageRatio), '有效秒条 / 计划秒条'),
  buildCard('会话时长', formatSeconds(props.session?.planned_duration_sec), '本次采集目标时长'),
]);

const progressBars = computed(() => [
  buildBar('计划完成度', props.progress?.writtenSeconds, props.session?.planned_duration_sec, formatSeconds(props.progress?.writtenSeconds)),
  buildBar('建窗准备度', props.progress?.writtenSeconds, FULL_WINDOW_SECONDS, formatSeconds(FULL_WINDOW_SECONDS - Number(props.progress?.secondsToFullWindow || 0))),
  buildBar('15m 边界进度', BOUNDARY_SECONDS - Number(props.progress?.secondsToNextBoundary || BOUNDARY_SECONDS), BOUNDARY_SECONDS, formatSeconds(BOUNDARY_SECONDS - Number(props.progress?.secondsToNextBoundary || BOUNDARY_SECONDS))),
]);

const statusLabel = computed(() => String(props.session?.status || 'idle'));
const badgeTone = computed(() => resolveBadgeTone(statusLabel.value));

function buildCard(label, value, caption) {
  return { label, value, caption };
}

function buildBar(label, currentValue, totalValue, valueLabel) {
  const safeCurrent = Math.max(Number(currentValue || 0), 0);
  const safeTotal = Math.max(Number(totalValue || 0), 0);
  const ratio = safeTotal > 0 ? Math.min(safeCurrent / safeTotal, 1) : 0;
  return {
    label,
    value: `${Math.round(ratio * 100)}% · ${valueLabel}`,
    width: `${Math.max(ratio * 100, 0)}%`,
  };
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function formatSeconds(value) {
  const totalSeconds = Math.max(Number(value || 0), 0);
  if (totalSeconds < 60) {
    return `${totalSeconds}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function resolveBadgeTone(status) {
  if (status === 'running' || status === 'finished') {
    return 'tone-up';
  }
  if (status === 'failed') {
    return 'tone-down';
  }
  return 'tone-warning';
}
</script>

<style scoped src="./trendResearchPanel.css"></style>

<style scoped>
.collection-progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.collection-progress-head h4,
.collection-progress-row-head strong {
  color: var(--text-primary);
}

.collection-progress-head p,
.collection-progress-row-head span,
.collection-progress-caption {
  color: var(--text-muted);
}

.collection-progress-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.collection-progress-caption {
  display: block;
  margin-top: 6px;
}

.collection-progress-bars {
  display: grid;
  gap: 10px;
}

.collection-progress-row {
  display: grid;
  gap: 8px;
}

.collection-progress-row-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.collection-progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  overflow: hidden;
}

.collection-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(247, 147, 26, 0.52), rgba(250, 204, 21, 0.82));
}

@media (max-width: 640px) {
  .collection-progress-head,
  .collection-progress-row-head {
    flex-direction: column;
  }
}
</style>
