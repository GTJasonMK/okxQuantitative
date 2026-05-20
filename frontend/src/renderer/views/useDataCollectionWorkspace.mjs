import { ref } from 'vue';

import { api } from '../services/api.js';
import { formatApiErrorDetail } from '../utils/apiErrorDetail.mjs';
import { bindRealtimeConnection } from '../utils/realtimeConnection.mjs';
import marketWS from '../services/websocket.js';

const DEFAULT_CHARTS = Object.freeze({ price: [], trade: [], book: [] });
const DEFAULT_COVERAGE = Object.freeze({
  coverageRatio: 0,
  validSecondCount: 0,
  missingSecondCount: 0,
  bookStaleSecondCount: 0,
  stateStaleSecondCount: 0,
  inferenceReadyCount: 0,
  trainingReadyCount: 0,
  stratumCoverage: [],
});
const DEFAULT_PROGRESS = Object.freeze({
  writtenSeconds: 0,
  remainingSeconds: 0,
  secondsToFullWindow: 7200,
  secondsToNextBoundary: 900,
});
const DETAIL_REFRESH_EVENTS = new Set(['second_flushed', 'session_quality_updated']);
const SESSION_EVENTS = new Set([
  'session_started',
  'session_running',
  'session_stopping',
  'session_stopped',
  'session_finished',
  'session_failed',
  'session_deleted',
  'session_updated',
]);

export function useDataCollectionWorkspace(deps = {}) {
  const apiClient = deps.api ?? api;
  const realtime = deps.realtime ?? marketWS;
  const sessions = ref([]);
  const activeSession = ref(null);
  const selectedSessionId = ref('');
  const sessionCharts = ref({ ...DEFAULT_CHARTS });
  const sessionCoverage = ref({ ...DEFAULT_COVERAGE });
  const sessionProgress = ref({ ...DEFAULT_PROGRESS });
  const censusStatus = ref(null);
  const sessionActionPending = ref(false);
  const sessionActionError = ref('');
  const realtimeError = ref('');

  const { attachRealtimeConnection, detachRealtimeConnection } = bindRealtimeConnection({
    realtime,
    errorRef: realtimeError,
    connectMessage: '秒级采集实时连接失败',
    disconnectMessage: '秒级采集实时连接已断开',
  });

  const loadSessions = async () => {
    const response = await apiClient.getDataCenterCollectionSessions({ limit: 50 });
    sessions.value = response.sessions || [];
    selectedSessionId.value = resolveSelectedSessionId(selectedSessionId.value, sessions.value);
  };

  const loadSessionDetail = async (sessionId) => {
    if (!sessionId) {
      resetSelectedSession(activeSession, sessionCharts, sessionCoverage, sessionProgress);
      return;
    }
    const response = await apiClient.getDataCenterCollectionSessionDetail(sessionId);
    hydrateSessionDetail(
      response.session || null,
      activeSession,
      sessionCharts,
      sessionCoverage,
      sessionProgress,
      sessions
    );
  };

  const loadCensusStatus = async () => {
    const response = await apiClient.getDataCenterCollectionCensusStatus();
    censusStatus.value = response.status || null;
  };

  const startCollectionSession = async (payload) => {
    sessionActionError.value = '';
    sessionActionPending.value = true;
    try {
      const response = await apiClient.createDataCenterCollectionSession(payload);
      const sessionId = response.session?.session_id || '';
      await loadSessions();
      if (sessionId) {
        selectedSessionId.value = sessionId;
        await loadSessionDetail(sessionId);
      }
    } catch (error) {
      sessionActionError.value = formatApiErrorDetail(error, '启动采集失败');
    } finally {
      sessionActionPending.value = false;
    }
  };

  const stopCollectionSession = async (sessionId = selectedSessionId.value) => {
    if (!sessionId) {
      return;
    }
    sessionActionError.value = '';
    sessionActionPending.value = true;
    try {
      await apiClient.stopDataCenterCollectionSession(sessionId);
      await loadSessions();
      await loadSessionDetail(sessionId);
    } catch (error) {
      sessionActionError.value = formatApiErrorDetail(error, '停止采集失败');
    } finally {
      sessionActionPending.value = false;
    }
  };

  const deleteCollectionSession = async (sessionId = selectedSessionId.value) => {
    if (!sessionId) {
      return;
    }
    sessionActionError.value = '';
    sessionActionPending.value = true;
    try {
      await apiClient.deleteDataCenterCollectionSession(sessionId);
      await loadSessions();
      pruneDeletedSessionState({
        sessionId,
        sessions,
        selectedSessionId,
        activeSession,
        sessionCharts,
        sessionCoverage,
        sessionProgress,
      });
      await loadSessionDetail(selectedSessionId.value);
    } catch (error) {
      sessionActionError.value = formatApiErrorDetail(error, '删除会话失败');
    } finally {
      sessionActionPending.value = false;
    }
  };

  const handleCollectionEvent = async (payload = {}) => {
    const eventName = String(payload.event || '');
    if (eventName === 'census_updated') {
      await loadCensusStatus();
      return;
    }
    if (!payload.session_id) {
      return;
    }
    if (DETAIL_REFRESH_EVENTS.has(eventName)) {
      if (payload.session_id === selectedSessionId.value) {
        await loadSessionDetail(payload.session_id);
      }
      return;
    }
    if (SESSION_EVENTS.has(eventName)) {
      await refreshSessionSelection({
        payload,
        eventName,
        sessions,
        activeSession,
        selectedSessionId,
        sessionCharts,
        sessionCoverage,
        sessionProgress,
        loadSessions,
        loadSessionDetail,
      });
    }
  };

  const attachRealtime = () => {
    attachRealtimeConnection();
    realtime.subscribeDataCenterCollection(handleCollectionEvent);
  };

  const detachRealtime = () => {
    detachRealtimeConnection();
    realtime.unsubscribeDataCenterCollection(handleCollectionEvent);
  };

  return {
    sessions,
    activeSession,
    selectedSessionId,
    sessionCharts,
    sessionCoverage,
    sessionProgress,
    censusStatus,
    sessionActionPending,
    sessionActionError,
    realtimeError,
    loadSessions,
    loadSessionDetail,
    loadCensusStatus,
    startCollectionSession,
    stopCollectionSession,
    deleteCollectionSession,
    handleCollectionEvent,
    attachRealtime,
    detachRealtime,
  };
}

function hydrateSessionDetail(session, activeSession, sessionCharts, sessionCoverage, sessionProgress, sessions) {
  activeSession.value = session;
  sessionCharts.value = normalizeCharts(session?.charts);
  sessionCoverage.value = normalizeCoverage(session?.coverage);
  sessionProgress.value = normalizeProgress(session?.progress);
  if (!session?.session_id) {
    return;
  }
  sessions.value = syncSessionSummary(sessions.value, session);
}

function resetSelectedSession(activeSession, sessionCharts, sessionCoverage, sessionProgress) {
  activeSession.value = null;
  sessionCharts.value = { ...DEFAULT_CHARTS };
  sessionCoverage.value = { ...DEFAULT_COVERAGE };
  sessionProgress.value = { ...DEFAULT_PROGRESS };
}

async function refreshSessionSelection({
  payload,
  eventName,
  sessions,
  activeSession,
  selectedSessionId,
  sessionCharts,
  sessionCoverage,
  sessionProgress,
  loadSessions,
  loadSessionDetail,
}) {
  await loadSessions();
  if (eventName === 'session_deleted') {
    pruneDeletedSessionState({
      sessionId: payload.session_id,
      sessions,
      selectedSessionId,
      activeSession,
      sessionCharts,
      sessionCoverage,
      sessionProgress,
    });
    await loadSessionDetail(selectedSessionId.value);
    return;
  }
  if (!payload.session_id) {
    return;
  }
  if (!selectedSessionId.value) {
    selectedSessionId.value = payload.session_id;
  }
  if (payload.session_id === selectedSessionId.value) {
    await loadSessionDetail(payload.session_id);
  }
}

function pruneDeletedSessionState({
  sessionId,
  sessions,
  selectedSessionId,
  activeSession,
  sessionCharts,
  sessionCoverage,
  sessionProgress,
}) {
  sessions.value = sessions.value.filter(session => session.session_id !== sessionId);
  const nextSelectedSessionId = resolveSelectedSessionId(selectedSessionId.value, sessions.value);
  if (selectedSessionId.value !== nextSelectedSessionId) {
    selectedSessionId.value = nextSelectedSessionId;
  }
  if (activeSession.value?.session_id === sessionId) {
    resetSelectedSession(activeSession, sessionCharts, sessionCoverage, sessionProgress);
  }
}

function resolveSelectedSessionId(currentSessionId, sessions) {
  if (currentSessionId && sessions.some(session => session.session_id === currentSessionId)) {
    return currentSessionId;
  }
  return sessions[0]?.session_id || '';
}

function syncSessionSummary(sessions, session) {
  const nextSessions = [...sessions];
  const nextSummary = {
    ...nextSessions.find(item => item.session_id === session.session_id),
    ...session,
    coverage_ratio: session.coverage?.coverage_ratio ?? session.coverage_ratio,
  };
  const index = nextSessions.findIndex(item => item.session_id === session.session_id);
  if (index >= 0) {
    nextSessions[index] = nextSummary;
    return nextSessions;
  }
  return [nextSummary, ...nextSessions];
}

function normalizeCharts(charts = {}) {
  return {
    price: Array.isArray(charts.price) ? charts.price : [],
    trade: Array.isArray(charts.trade) ? charts.trade : [],
    book: Array.isArray(charts.book) ? charts.book : [],
  };
}

function normalizeCoverage(coverage = {}) {
  return {
    coverageRatio: Number(coverage.coverage_ratio ?? coverage.coverageRatio ?? 0),
    validSecondCount: Number(coverage.valid_second_count ?? coverage.validSecondCount ?? 0),
    missingSecondCount: Number(coverage.missing_second_count ?? coverage.missingSecondCount ?? 0),
    bookStaleSecondCount: Number(coverage.book_stale_second_count ?? coverage.bookStaleSecondCount ?? 0),
    stateStaleSecondCount: Number(coverage.state_stale_second_count ?? coverage.stateStaleSecondCount ?? 0),
    inferenceReadyCount: Number(coverage.inference_ready_count ?? coverage.inferenceReadyCount ?? 0),
    trainingReadyCount: Number(coverage.training_ready_count ?? coverage.trainingReadyCount ?? 0),
    stratumCoverage: Array.isArray(coverage.stratum_coverage ?? coverage.stratumCoverage)
      ? (coverage.stratum_coverage ?? coverage.stratumCoverage)
      : [],
  };
}

function normalizeProgress(progress = {}) {
  return {
    writtenSeconds: Number(progress.written_seconds ?? progress.writtenSeconds ?? 0),
    remainingSeconds: Number(progress.remaining_seconds ?? progress.remainingSeconds ?? 0),
    secondsToFullWindow: Number(progress.seconds_to_full_window ?? progress.secondsToFullWindow ?? 7200),
    secondsToNextBoundary: Number(progress.seconds_to_next_boundary ?? progress.secondsToNextBoundary ?? 900),
  };
}
