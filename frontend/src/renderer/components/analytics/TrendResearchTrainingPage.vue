<template>
  <TrendResearchTrainingRunPanel
    :error-message="errorMessage"
    :model="trainingRunModel"
    :requesting="requesting"
    @start-retrain="startRetrain"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue';

import { api } from '../../services/api';
import TrendResearchTrainingRunPanel from './TrendResearchTrainingRunPanel.vue';
import { buildTrendTrainingRunPanelModel } from './trendResearchTrainingRunViewModel.mjs';
import { normalizeTrendLookbackSeconds } from './trendResearchLookback.mjs';

const props = defineProps({
  isActive: {
    type: Boolean,
    default: false,
  },
  lookbackSeconds: {
    type: Number,
    default: 0,
  },
  modelStatus: {
    type: Object,
    default: () => ({}),
  },
  trainingRunPayload: {
    type: Object,
    default: null,
  },
});

const requesting = ref(false);
const errorMessage = ref('');
const hasBootstrapped = ref(false);
const localTrainingRun = ref(null);

const resolvedTrainingRun = computed(() => props.trainingRunPayload || localTrainingRun.value);

const trainingRunModel = computed(() => {
  return buildTrendTrainingRunPanelModel({
    trainingRun: resolvedTrainingRun.value,
    modelStatus: props.modelStatus,
  });
});

const loadTrainingRun = async () => {
  if (!props.isActive || hasBootstrapped.value) {
    return;
  }
  requesting.value = true;
  errorMessage.value = '';
  try {
    const response = await api.getTrendResearchTrainingRun();
    localTrainingRun.value = response.training_run || null;
    hasBootstrapped.value = true;
  } catch (loadError) {
    errorMessage.value = loadError.response?.data?.detail || loadError.message || '加载训练状态失败';
  } finally {
    requesting.value = false;
  }
};

const startRetrain = async () => {
  requesting.value = true;
  errorMessage.value = '';
  try {
    const response = await api.retrainTrendResearchModel({
      lookback: normalizeTrendLookbackSeconds(props.lookbackSeconds),
    });
    localTrainingRun.value = response.training_run || null;
    hasBootstrapped.value = true;
  } catch (loadError) {
    errorMessage.value = loadError.response?.data?.detail || loadError.message || '启动训练失败';
  } finally {
    requesting.value = false;
  }
};

watch(
  () => props.isActive,
  () => {
    void loadTrainingRun();
  },
  { immediate: true },
);
</script>
