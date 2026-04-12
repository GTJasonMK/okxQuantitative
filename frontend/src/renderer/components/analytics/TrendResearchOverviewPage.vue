<template>
  <div v-if="selectedTrendRow" class="trend-summary-overview">
    <section class="trend-summary-hero">
      <TrendResearchPredictionSummary :row="selectedTrendRow" :model="predictionSummaryModel" />
    </section>
    <TrendResearchModelStatus class="trend-summary-model" :model-status="modelStatus" />
    <section class="trend-distribution-section">
      <TrendResearchTimeDistributions :model="timeDistributionModel" />
    </section>
  </div>
  <div
    v-else
    class="empty-state"
    :class="panelState.tone === 'warning' ? 'trend-empty-warning' : 'trend-empty-info'"
  >
    <TrendResearchModelStatus class="trend-summary-model" :model-status="modelStatus" />
    <strong>{{ panelState.title || '暂无趋势研究数据' }}</strong>
    <p>{{ panelState.description || '后端暂时没有可展示的趋势研究结果。' }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue';

import TrendResearchModelStatus from './TrendResearchModelStatus.vue';
import TrendResearchPredictionSummary from './TrendResearchPredictionSummary.vue';
import TrendResearchTimeDistributions from './TrendResearchTimeDistributions.vue';
import { buildTrendPredictionSummaryModel, buildTrendTimeDistributionModel } from './trendResearchPredictionSummaryViewModel.mjs';

const props = defineProps({
  modelStatus: {
    type: Object,
    default: () => ({}),
  },
  panelState: {
    type: Object,
    default: () => ({}),
  },
  selectedProcessInstrument: {
    type: Object,
    default: null,
  },
  selectedTrendRow: {
    type: Object,
    default: null,
  },
});

const predictionSummaryModel = computed(() => {
  return buildTrendPredictionSummaryModel({
    selectedTrendRow: props.selectedTrendRow,
    processStateLabel: props.selectedProcessInstrument?.displayState || '',
  });
});

const timeDistributionModel = computed(() => buildTrendTimeDistributionModel(props.selectedTrendRow));
</script>

<style scoped src="./trendResearchPanel.css"></style>
