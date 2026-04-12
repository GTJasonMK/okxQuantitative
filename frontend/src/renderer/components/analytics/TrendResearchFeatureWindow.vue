<template>
  <section class="trend-feature-window-section">
    <div v-if="error" class="error-message">{{ error }}</div>
    <div v-if="loading && model.timelineSegments.length === 0" class="empty-state">加载特征窗口...</div>
    <div v-else-if="model.timelineSegments.length === 0" class="empty-state">
      当前没有可展示的特征条窗口。
    </div>
    <div v-else class="trend-feature-window-body">
      <div class="trend-feature-window-strip">
        <div
          v-for="segment in model.timelineSegments"
          :key="segment.key"
          class="trend-feature-window-bar"
          :class="[segment.tone, segment.qualityTone]"
          :style="{ height: `${segment.height}%` }"
          :title="segment.title"
        ></div>
      </div>

      <div class="trend-feature-window-footer">
        <span>最近 {{ FEATURE_BAR_LIMIT }} 秒窗口</span>
        <span>数据质量 {{ model.qualityLabel }}</span>
        <span>共 {{ model.timelineSegments.length }} 个 1 秒桶</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { api } from '../../services/api';
import { createLatestOnly } from '../../utils/async';
import { buildTrendFeatureWindowModel, mergeTrendFeatureBars } from './trendResearchViewModel.mjs';

const FEATURE_BAR_LIMIT = 60;

const props = defineProps({
  instId: {
    type: String,
    default: '',
  },
  realtimeBars: {
    type: Array,
    default: () => [],
  },
});

const loader = createLatestOnly();
let requestVersion = 0;

const loading = ref(false);
const error = ref('');
const rows = ref([]);

const model = computed(() => buildTrendFeatureWindowModel(rows.value));

const resetState = () => {
  loader.abort();
  requestVersion += 1;
  loading.value = false;
  error.value = '';
  rows.value = [];
};

const loadRows = async (instId) => {
  if (!instId) {
    resetState();
    return;
  }

  const currentVersion = ++requestVersion;
  loading.value = true;
  error.value = '';
  try {
    const response = await loader.run((signal) => {
      return api.getTrendResearchFeatureBars(instId, { limit: FEATURE_BAR_LIMIT }, { signal });
    });
    if (!response || currentVersion !== requestVersion) {
      return;
    }
    rows.value = mergeTrendFeatureBars(
      rows.value,
      Array.isArray(response.rows) ? response.rows : [],
      FEATURE_BAR_LIMIT,
    );
  } catch (loadError) {
    if (currentVersion !== requestVersion) {
      return;
    }
    error.value = loadError.response?.data?.detail || loadError.message || '加载特征窗口失败';
    if (rows.value.length === 0) {
      rows.value = [];
    }
  } finally {
    if (currentVersion === requestVersion) {
      loading.value = false;
    }
  }
};

watch(() => props.instId, (instId) => {
  void loadRows(instId);
}, { immediate: true });

watch(() => props.realtimeBars, (realtimeBars) => {
  if (!Array.isArray(realtimeBars) || realtimeBars.length === 0) {
    return;
  }
  rows.value = mergeTrendFeatureBars(rows.value, realtimeBars, FEATURE_BAR_LIMIT);
  loading.value = false;
  error.value = '';
}, { deep: true });

onBeforeUnmount(() => {
  loader.abort();
});
</script>

<style scoped src="./trendResearchFeatureWindow.css"></style>
