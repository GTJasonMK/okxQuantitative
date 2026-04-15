<template>
  <TrendDiagnosticsShell
    v-if="showShell"
    :error="error"
    :loading="loading"
    :process-summary="processSummary"
    :selected-process-instrument="selectedProcessInstrument"
    :state="viewState"
  />
  <div v-else class="empty-state trend-empty-info">
    <strong>暂无运行进度数据</strong>
    <p>{{ emptyDescription }}</p>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue';

import TrendDiagnosticsShell from './TrendDiagnosticsShell.vue';
import { useTrendDiagnosticsWorkspace } from './useTrendDiagnosticsWorkspace.mjs';

const props = defineProps({
  instId: {
    type: String,
    default: '',
  },
  processSummary: {
    type: Object,
    default: () => ({}),
  },
  selectedProcessInstrument: {
    type: Object,
    default: () => ({}),
  },
});
const emit = defineEmits(['select-inst']);

const workspace = useTrendDiagnosticsWorkspace({ initialInstId: props.instId });
const {
  error,
  loading,
  selectInstrument,
  state,
} = workspace;

const showShell = computed(() => {
  return loading.value
    || state.value.instruments.length > 0
    || !!state.value.selectedInstId
    || !!props.selectedProcessInstrument?.instId;
});
const viewState = computed(() => {
  return {
    ...state.value,
    selectedInstId: props.instId || state.value.selectedInstId,
  };
});

const emptyDescription = computed(() => {
  if (error.value) {
    return error.value;
  }
  return '后端尚未返回任何白名单合约，运行进度页面暂时没有可展示内容。';
});

watch(() => props.instId, (nextInstId) => {
  if (nextInstId === state.value.selectedInstId) {
    return;
  }
  void selectInstrument(nextInstId || '');
});

watch(() => state.value.selectedInstId, (nextInstId) => {
  if (!nextInstId || nextInstId === props.instId) {
    return;
  }
  emit('select-inst', nextInstId);
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
