<template>
  <section class="trend-training-curves">
    <div v-if="!props.groups.length || !props.groups[0].hasData" class="empty-state">
      等待 epoch 曲线
    </div>
    <div v-else ref="chartHost" class="trend-training-curve-host"></div>
  </section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { createTimeSeriesChartManager } from '../../utils/lwcTimeSeriesChart.mjs';

const props = defineProps({
  groups: {
    type: Array,
    default: () => [],
  },
});

const chartHost = ref(null);
const chartManager = createTimeSeriesChartManager();

const syncChart = async () => {
  await nextTick();
  if (!chartHost.value) {
    return;
  }
  chartManager.init(chartHost.value, {
    leftPriceScale: { visible: false },
    rightPriceScale: { visible: true },
  });
  const group = props.groups[0];
  if (!group || !group.hasData) {
    chartManager.clear();
    return;
  }
  chartManager.setSeries(group.series, { fitContent: true });
};

watch(() => props.groups, () => {
  void syncChart();
}, { deep: true, immediate: true });

onBeforeUnmount(() => {
  chartManager.dispose();
});
</script>

<style scoped src="./trendResearchTrainingCurves.css"></style>
