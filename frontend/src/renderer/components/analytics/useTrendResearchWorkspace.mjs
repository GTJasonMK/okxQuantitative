import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { api } from '../../services/api';
import marketWS from '../../services/websocket';
import {
  DEFAULT_TREND_LOOKBACK_SECONDS,
  formatTrendLookbackLabel,
  normalizeTrendLookbackSeconds,
} from './trendResearchLookback.mjs';
import { buildTrendProcessPanelModel } from './trendResearchProcessViewModel.mjs';
import { buildTrendModelStatus, buildTrendPanelState, buildTrendRows } from './trendResearchViewModel.mjs';

const DEFAULT_ACTIVE_PAGE = 'overview';

const resolveInferenceRows = (payload = {}) => {
  return Array.isArray(payload.rows) ? payload.rows : [];
};

export function useTrendResearchWorkspace() {
  const activeTrendPage = ref(DEFAULT_ACTIVE_PAGE);
  const selectedInstId = ref('');
  const selectedLookbackSeconds = ref(DEFAULT_TREND_LOOKBACK_SECONDS);
  const rows = ref([]);
  const loading = ref(false);
  const error = ref('');
  const panelState = ref(buildTrendPanelState());
  const modelStatus = ref(buildTrendModelStatus());
  const recentProcess = ref(buildTrendProcessPanelModel());
  const refreshVersion = ref(0);
  const trainingRunPayload = ref(null);

  const selectedTrendRow = computed(() => {
    return rows.value.find((row) => row.instId === selectedInstId.value) || null;
  });
  const selectedProcessInstrument = computed(() => {
    return recentProcess.value.instruments.find((item) => item.instId === selectedInstId.value)
      || recentProcess.value.instruments[0]
      || null;
  });
  const lookbackLabel = computed(() => formatTrendLookbackLabel(selectedLookbackSeconds.value));

  const syncSelectedInstrument = () => {
    const availableInstIds = rows.value.length > 0
      ? rows.value.map((row) => row.instId)
      : recentProcess.value.instruments.map((item) => item.instId);
    if (availableInstIds.length === 0) {
      selectedInstId.value = '';
      return;
    }
    if (!availableInstIds.includes(selectedInstId.value)) {
      selectedInstId.value = availableInstIds[0];
    }
  };

  const applyRealtimePayload = (payload = {}) => {
    panelState.value = buildTrendPanelState(payload);
    modelStatus.value = buildTrendModelStatus(payload);
    recentProcess.value = buildTrendProcessPanelModel(payload);
    refreshVersion.value += 1;
    trainingRunPayload.value = payload.training_run || trainingRunPayload.value;
    rows.value = buildTrendRows(resolveInferenceRows(payload));
    error.value = '';
    loading.value = false;
    syncSelectedInstrument();
  };

  const loadSharedData = async () => {
    loading.value = true;
    error.value = '';
    try {
      const [inferenceResponse, processResponse] = await Promise.all([
        api.getTrendResearchInference({ limit: 50 }),
        api.getTrendResearchProcess({ bar_limit: 20 }),
      ]);
      applyRealtimePayload({
        ...processResponse,
        rows: resolveInferenceRows(inferenceResponse),
      });
    } catch (loadError) {
      error.value = loadError.response?.data?.detail || loadError.message || '加载趋势研究数据失败';
      loading.value = false;
    }
  };

  const handleTrendResearchUpdate = (payload) => {
    if (!payload || typeof payload !== 'object') {
      return;
    }
    applyRealtimePayload(payload);
  };

  const selectInstrument = (instId) => {
    if (!instId) {
      return;
    }
    selectedInstId.value = instId;
  };

  watch(selectedLookbackSeconds, (value) => {
    const normalized = normalizeTrendLookbackSeconds(value);
    if (normalized !== value) {
      selectedLookbackSeconds.value = normalized;
    }
  });

  onMounted(() => {
    void loadSharedData();
    marketWS.connect().catch((connectError) => {
      console.warn('[TrendResearch] 建立实时连接失败:', connectError);
    });
    marketWS.subscribeTrendResearch(handleTrendResearchUpdate);
  });

  onBeforeUnmount(() => {
    marketWS.unsubscribeTrendResearch(handleTrendResearchUpdate);
  });

  return {
    activeTrendPage,
    applyRealtimePayload,
    error,
    loading,
    loadSharedData,
    modelStatus,
    panelState,
    recentProcess,
    refreshVersion,
    rows,
    lookbackLabel,
    selectedInstId,
    selectedProcessInstrument,
    selectedLookbackSeconds,
    selectedTrendRow,
    selectInstrument,
    trainingRunPayload,
  };
}
