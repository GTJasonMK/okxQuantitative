import { onBeforeUnmount, onMounted, ref } from 'vue';

import { api } from '../../services/api';
import marketWS from '../../services/websocket';
import { createLatestOnly } from '../../utils/async';
import { bindRealtimeConnection } from '../../utils/realtimeConnection.mjs';
import { applyTrendDiagnosticsEvent, buildTrendDiagnosticsState } from './trendDiagnosticsState.mjs';

const DEFAULT_TIMELINE_LIMIT = 40;

export function useTrendDiagnosticsWorkspace(options = {}) {
  const state = ref(buildTrendDiagnosticsState());
  const loading = ref(false);
  const error = ref('');
  const latestRequest = createLatestOnly();
  const { attachRealtimeConnection, detachRealtimeConnection } = bindRealtimeConnection({
    realtime: marketWS,
    errorRef: error,
    connectMessage: '趋势诊断实时连接失败',
    disconnectMessage: '趋势诊断实时连接已断开',
  });

  const handleDiagnosticsEvent = (payload) => {
    state.value = applyTrendDiagnosticsEvent(state.value, payload);
    error.value = '';
  };

  const subscribeDiagnostics = (instId) => {
    marketWS.subscribeTrendDiagnostics(
      {
        instId: instId || '',
        timelineLimit: DEFAULT_TIMELINE_LIMIT,
      },
      handleDiagnosticsEvent,
    );
  };

  const unsubscribeDiagnostics = () => {
    marketWS.unsubscribeTrendDiagnostics(handleDiagnosticsEvent);
  };

  const loadSnapshot = async (instId = '') => {
    loading.value = true;
    error.value = '';
    try {
      const payload = await latestRequest.run((signal) => {
        return api.getTrendDiagnostics(
          {
            inst_id: instId || '',
            timeline_limit: DEFAULT_TIMELINE_LIMIT,
          },
          { signal },
        );
      });
      if (payload) {
        state.value = buildTrendDiagnosticsState(payload);
      }
    } catch (loadError) {
      error.value = loadError.response?.data?.detail || loadError.message || '加载趋势诊断失败';
    } finally {
      loading.value = false;
    }
  };

  const selectInstrument = async (instId) => {
    unsubscribeDiagnostics();
    await loadSnapshot(instId);
    subscribeDiagnostics(instId);
  };

  onMounted(() => {
    const initialInstId = options.initialInstId || '';
    void loadSnapshot(initialInstId);
    attachRealtimeConnection();
    subscribeDiagnostics(initialInstId);
  });

  onBeforeUnmount(() => {
    latestRequest.abort();
    detachRealtimeConnection();
    unsubscribeDiagnostics();
  });

  return {
    error,
    handleDiagnosticsEvent,
    loadSnapshot,
    loading,
    selectInstrument,
    state,
  };
}
