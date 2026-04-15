<template>
  <section class="card trend-research-card">
    <div class="research-panel-header">
      <div>
        <h4>Bootstrap</h4>
        <p class="research-panel-desc">展示 forecast layer 与 decision layer 的 stationary block bootstrap 区间。</p>
      </div>
    </div>
    <div v-if="!bootstrap" class="trend-subpage-placeholder empty-state trend-empty-info">
      <strong>尚无 bootstrap_result</strong>
      <p>训练运行生成后，这里会展示 `joint_nll` 与 `mean_utility` 的 `ci_95`。</p>
    </div>
    <div v-else class="research-kv-grid">
      <article v-for="item in rows" :key="item.label" class="research-kv-card">
        <span class="research-kv-label">{{ item.label }}</span>
        <strong class="research-kv-value">{{ item.mean }}</strong>
        <p class="research-kv-meta">ci_95: {{ item.ci95 }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import { formatCompactNumber } from '../../utils/formatting.js';

const props = defineProps({
  bootstrap: {
    type: Object,
    default: null,
  },
});

const rows = computed(() => ([
  buildRow('joint_nll', props.bootstrap?.joint_nll),
  buildRow('mean_utility', props.bootstrap?.mean_utility),
]));

function buildRow(label, payload) {
  return {
    label,
    mean: formatMetric(payload?.mean),
    ci95: formatInterval(payload?.ci_95),
  };
}

function formatMetric(value) {
  return formatCompactNumber(value, { digits: 6, scientificDigits: 3, maxChars: 12 });
}

function formatInterval(value) {
  if (!Array.isArray(value) || value.length !== 2) {
    return '--';
  }
  return `[${formatMetric(value[0])}, ${formatMetric(value[1])}]`;
}
</script>

<style scoped src="./trendResearchPanel.css"></style>
