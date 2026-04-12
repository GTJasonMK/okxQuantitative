<template>
  <div v-if="instId" class="trend-factor-section">
    <TrendResearchFactorSummary
      class="trend-factor-summary-section"
      :error="factorError"
      :loading="factorLoading"
      :lookback-label="lookbackLabel"
      :rows="factorLegendRows"
      :selected-row="selectedRow"
      :selected-factor-name="selectedFactorName"
      @select-factor="handleSelectFactor"
    />
    <TrendResearchFactorCharts
      class="trend-factor-chart-section"
      :error="factorError"
      :loading="factorLoading"
      :lookback-label="lookbackLabel"
      :groups="factorChartModel.groups"
      :selected-factor-name="selectedFactorName"
    />
  </div>
  <div v-else class="empty-state trend-empty-info">
    <strong>请选择一个合约</strong>
    <p>选择目标合约后，这里会展示全部因子的时间变化。</p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { api } from '../../services/api';
import { createLatestOnly } from '../../utils/async';
import TrendResearchFactorCharts from './TrendResearchFactorCharts.vue';
import TrendResearchFactorSummary from './TrendResearchFactorSummary.vue';
import { buildTrendFactorChartModel, buildTrendFactorLegendRows } from './trendResearchFactorChartsViewModel.mjs';
import { normalizeTrendLookbackSeconds } from './trendResearchLookback.mjs';

const props = defineProps({
  instId: {
    type: String,
    default: '',
  },
  isActive: {
    type: Boolean,
    default: false,
  },
  lookbackLabel: {
    type: String,
    default: '',
  },
  lookbackSeconds: {
    type: Number,
    default: 0,
  },
  refreshToken: {
    type: Number,
    default: 0,
  },
  selectedRow: {
    type: Object,
    default: null,
  },
});

const factorLoader = createLatestOnly();
let requestVersion = 0;

const factorSeriesPayload = ref(null);
const factorLoading = ref(false);
const factorError = ref('');
const selectedFactorName = ref('');

const factorChartModel = computed(() => buildTrendFactorChartModel(factorSeriesPayload.value || {}));
const factorLegendRows = computed(() => factorChartModel.value.legendRows || buildTrendFactorLegendRows([]));

const resetFactorState = () => {
  factorLoader.abort();
  requestVersion += 1;
  factorSeriesPayload.value = null;
  factorLoading.value = false;
  factorError.value = '';
  selectedFactorName.value = '';
};

const loadFactorSeries = async () => {
  if (!props.instId) {
    resetFactorState();
    return;
  }
  if (!props.isActive) {
    return;
  }

  const currentVersion = ++requestVersion;
  factorLoading.value = true;
  factorError.value = '';
  try {
    const response = await factorLoader.run((signal) => {
      return api.getTrendResearchFactorSeries(
        props.instId,
        { lookback: normalizeTrendLookbackSeconds(props.lookbackSeconds) },
        { signal },
      );
    });
    if (!response || currentVersion !== requestVersion) {
      return;
    }
    factorSeriesPayload.value = response;
    if (selectedFactorName.value && !factorChartModel.value.factorMetaMap?.has(selectedFactorName.value)) {
      selectedFactorName.value = '';
    }
  } catch (loadError) {
    if (currentVersion !== requestVersion) {
      return;
    }
    factorSeriesPayload.value = null;
    selectedFactorName.value = '';
    factorError.value = loadError.response?.data?.detail || loadError.message || '加载趋势研究因子失败';
  } finally {
    if (currentVersion === requestVersion) {
      factorLoading.value = false;
    }
  }
};

const handleSelectFactor = (factorName) => {
  if (!factorName) {
    selectedFactorName.value = '';
    return;
  }
  selectedFactorName.value = selectedFactorName.value === factorName ? '' : factorName;
};

watch(() => props.instId, () => {
  selectedFactorName.value = '';
});

watch(
  () => [props.instId, props.isActive, props.lookbackSeconds, props.refreshToken],
  () => {
    void loadFactorSeries();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  factorLoader.abort();
});
</script>

<style scoped src="./trendResearchPanel.css"></style>
