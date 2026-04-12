<template>
  <details class="trend-diagnostics-card trend-diagnostics-details">
    <summary class="trend-diagnostics-details-summary">
      <span>必要细节</span>
      <span class="trend-diagnostics-block-caption">订阅状态、计数器与最近错误时间</span>
    </summary>

    <div class="trend-diagnostics-detail-grid">
      <article v-for="item in detailItems" :key="item.label" class="trend-diagnostics-detail-item">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>
  </details>
</template>

<script setup>
import { computed } from 'vue';

import {
  formatBucketLabel,
  formatUnixSeconds,
} from './trendDiagnosticsView.mjs';

const props = defineProps({
  details: {
    type: Object,
    default: () => ({}),
  },
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
});

const detailItems = computed(() => {
  return [
    { label: '订阅状态', value: props.details.subscription_state || '--' },
    { label: '待处理 Trade 数', value: props.details.pending_trade_count ?? 0 },
    { label: '最近特征秒桶', value: formatBucketLabel(props.details.last_feature_bucket) },
    { label: '最近推断秒桶', value: formatBucketLabel(props.details.last_inference_bucket) },
    { label: '最近错误时间', value: formatUnixSeconds(props.details.last_error_at) },
    { label: '当前合约最近事件', value: formatUnixSeconds(props.instrumentHealth.last_event_at) },
    { label: '全局最近事件', value: formatUnixSeconds(props.globalHealth.last_event_at) },
    { label: '最近诊断快照', value: formatUnixSeconds(props.emittedAt) },
    { label: '当前异常消息', value: props.instrumentHealth.current_error || '无' },
  ];
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
