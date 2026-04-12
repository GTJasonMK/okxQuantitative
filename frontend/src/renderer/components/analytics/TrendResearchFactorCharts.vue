<template>
  <section class="trend-factor-chart-grid">
    <article
      v-for="group in groups"
      :key="group.key"
      class="trend-factor-chart-panel"
      :class="{ 'is-empty': !group.hasData }"
    >
      <div class="trend-factor-chart-header">
        <div>
          <h5>{{ group.label }}</h5>
          <p>{{ group.caption }}</p>
        </div>
        <span class="trend-factor-chart-meta">{{ lookbackLabel }}</span>
      </div>
      <div v-if="error" class="error-message">{{ error }}</div>
      <div v-else-if="loading && !group.hasData" class="empty-state">加载图表中...</div>
      <div v-else-if="!group.hasData" class="empty-state">当前窗口没有该分类的可绘制因子。</div>
      <div v-else class="trend-factor-chart-host-wrap">
        <div :ref="setChartHost(group.key)" class="trend-factor-chart-host"></div>
        <div
          v-if="resolveHoverLineStyle(group.key)"
          class="trend-factor-hover-line"
          :style="resolveHoverLineStyle(group.key)"
        ></div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { createTimeSeriesChartManager } from '../../utils/lwcTimeSeriesChart.mjs';

const FOCUSED_LINE_WIDTH = 3;
const DEFAULT_LINE_WIDTH = 2;
const DIMMED_ALPHA = '47';

const props = defineProps({
  groups: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  lookbackLabel: {
    type: String,
    default: '',
  },
  selectedFactorName: {
    type: String,
    default: '',
  },
});

const chartHosts = new Map();
const chartManagers = new Map();
const activeHoverTime = ref(null);

const setChartHost = (key) => (element) => {
  if (element) {
    chartHosts.set(key, element);
    return;
  }
  chartHosts.delete(key);
};

const applyDimmedColor = (color, isDimmed) => {
  if (!isDimmed || typeof color !== 'string' || !color.startsWith('#') || color.length !== 7) {
    return color;
  }
  return `${color}${DIMMED_ALPHA}`;
};

const resolveSeriesConfig = (series) => {
  const isFocused = props.selectedFactorName === series.factorName;
  const isDimmed = Boolean(props.selectedFactorName) && !isFocused;
  return {
    ...series,
    color: applyDimmedColor(series.color, isDimmed), // is-dimmed state
    lineWidth: isFocused ? FOCUSED_LINE_WIDTH : DEFAULT_LINE_WIDTH,
    priceScaleId: series.axis === 'left' ? 'left' : 'right',
  };
};

const ensureManager = (group) => {
  const host = chartHosts.get(group.key);
  if (!host) {
    return null;
  }
  const manager = chartManagers.get(group.key) || createTimeSeriesChartManager();
  chartManagers.set(group.key, manager);
  manager.init(host, {
    leftPriceScale: { visible: group.hasLeftAxis },
    rightPriceScale: { visible: true },
  });
  return manager;
};

const syncCharts = async () => {
  await nextTick();
  props.groups.forEach((group) => {
    const manager = ensureManager(group);
    if (!manager) {
      return;
    }
    if (!group.hasData) {
      manager.clear();
      return;
    }
    manager.setSeries(group.series.map(resolveSeriesConfig), {
      fitContent: true,
      onHoverTimeChange: (time) => {
        activeHoverTime.value = time == null ? null : Number(time);
      },
    });
  });
};

const resolveHoverLineStyle = (groupKey) => {
  const manager = chartManagers.get(groupKey);
  const coordinate = manager?.getTimeCoordinate(activeHoverTime.value);
  if (!Number.isFinite(coordinate)) {
    return null;
  }
  return {
    transform: `translateX(${coordinate}px)`,
  };
};

const resizeCharts = () => {
  chartManagers.forEach((manager) => manager.resize());
};

watch(() => props.groups, () => {
  void syncCharts();
}, { deep: true, immediate: true });

watch(() => props.selectedFactorName, () => {
  void syncCharts();
});

onMounted(() => {
  window.addEventListener('resize', resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts);
  chartManagers.forEach((manager) => manager.dispose());
  chartManagers.clear();
});
</script>

<style scoped src="./trendResearchFactorCharts.css"></style>
