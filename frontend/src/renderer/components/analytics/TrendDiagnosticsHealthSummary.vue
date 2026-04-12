<template>
  <section class="trend-diagnostics-card trend-diagnostics-summary">
    <header class="trend-diagnostics-block-header">
      <div>
        <p class="trend-diagnostics-eyebrow">结论与状态概览</p>
        <h4>链路健康概览</h4>
        <p class="trend-diagnostics-block-desc">进入页面后优先判断当前卡在哪一步，以及最近一次有效输入/输出。</p>
      </div>
      <div class="trend-diagnostics-summary-status">
        <span class="trend-diagnostics-stage">{{ stageLabel }}</span>
        <span class="trend-diagnostics-state" :class="`tone-${statusTone}`">{{ statusLabel }}</span>
      </div>
    </header>

    <div class="trend-diagnostics-summary-pills">
      <div v-for="item in globalItems" :key="item.label" class="trend-diagnostics-pill-stat">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>

    <div class="trend-diagnostics-metrics">
      <article v-for="item in metricItems" :key="item.label" class="trend-diagnostics-metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div v-if="instrumentHealth.current_error" class="trend-diagnostics-error-banner">
      <strong>当前异常</strong>
      <span>{{ instrumentHealth.current_error }}</span>
    </div>
    <div v-else class="trend-diagnostics-summary-note">
      {{ summaryNote }}
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import {
  formatRelativeSeconds,
  formatUnixSeconds,
  resolveHealthLabel,
  resolveHealthTone,
  resolvePipelineStageLabel,
} from './trendDiagnosticsView.mjs';

const props = defineProps({
  emittedAt: {
    type: Number,
    default: null,
  },
  globalHealth: {
    type: Object,
    default: () => ({}),
  },
  instrumentHealth: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const stageLabel = computed(() => resolvePipelineStageLabel(props.instrumentHealth.pipeline_stage));
const statusTone = computed(() => resolveHealthTone(props.instrumentHealth));
const statusLabel = computed(() => resolveHealthLabel(props.instrumentHealth));
const summaryNote = computed(() => {
  if (props.loading) {
    return '正在同步诊断快照与实时事件...';
  }
  if (props.instrumentHealth.is_stale && props.emittedAt) {
    return '当前只有诊断快照在刷新，所选合约的真实链路事件没有更新。';
  }
  return '当前没有运行异常，优先结合时间线观察链路是否停在某一阶段。';
});

const globalItems = computed(() => {
  return [
    { label: '全局白名单', value: props.globalHealth.whitelist_count ?? 0 },
    { label: '全局活跃', value: props.globalHealth.active_count ?? 0 },
    { label: '全局停滞', value: props.globalHealth.stale_count ?? 0 },
    { label: '全局异常', value: props.globalHealth.error_count ?? 0 },
  ];
});

const metricItems = computed(() => {
  return [
    { label: 'Trade 新鲜度', value: formatRelativeSeconds(props.instrumentHealth.trade_age_seconds) },
    { label: 'Book 新鲜度', value: formatRelativeSeconds(props.instrumentHealth.book_age_seconds) },
    { label: 'State 新鲜度', value: formatRelativeSeconds(props.instrumentHealth.state_age_seconds) },
    { label: '最近特征', value: formatUnixSeconds(props.instrumentHealth.last_feature_at) },
    { label: '最近推断', value: formatUnixSeconds(props.instrumentHealth.last_inference_at) },
    { label: '当前合约最近事件', value: formatUnixSeconds(props.instrumentHealth.last_event_at) },
    { label: '最近快照', value: formatUnixSeconds(props.emittedAt) },
  ];
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
