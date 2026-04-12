<template>
  <section class="trend-distribution-grid">
    <article
      v-for="group in model.groups"
      :key="group.key"
      class="trend-distribution-card"
      :class="{ 'is-empty': !group.hasData }"
    >
      <div class="trend-distribution-header">
        <div>
          <h5>{{ group.label }}</h5>
          <p>{{ group.caption }}</p>
        </div>
      </div>
      <div v-if="!group.hasData" class="empty-state">{{ group.emptyLabel }}</div>
      <div v-else :ref="setChartHost(group.key)" class="trend-distribution-host"></div>
    </article>
  </section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, watch } from 'vue';
import { createTimeSeriesChartManager } from '../../utils/lwcTimeSeriesChart.mjs';

const props = defineProps({
  model: {
    type: Object,
    default: () => ({ groups: [] }),
  },
});

const chartHosts = new Map();
const chartManagers = new Map();

const setChartHost = (key) => (element) => {
  if (element) {
    chartHosts.set(key, element);
    return;
  }
  chartHosts.delete(key);
};

const ensureManager = (group) => {
  const host = chartHosts.get(group.key);
  if (!host) {
    return null;
  }
  const manager = chartManagers.get(group.key) || createTimeSeriesChartManager();
  chartManagers.set(group.key, manager);
  manager.init(host, {
    rightPriceScale: { visible: true },
  });
  return manager;
};

const syncCharts = async () => {
  await nextTick();
  props.model.groups.forEach((group) => {
    const manager = ensureManager(group);
    if (!manager) {
      return;
    }
    if (!group.hasData) {
      manager.clear();
      return;
    }
    manager.setSeries(group.series, {
      fitContent: true,
      timeFormatter: (time) => `+${Math.round(Number(time) / 60)} 分钟`,
    });
  });
};

watch(() => props.model, () => {
  void syncCharts();
}, { deep: true, immediate: true });

onBeforeUnmount(() => {
  chartManagers.forEach((manager) => manager.dispose());
  chartManagers.clear();
});
</script>

<style scoped src="./trendResearchTimeDistributions.css"></style>
