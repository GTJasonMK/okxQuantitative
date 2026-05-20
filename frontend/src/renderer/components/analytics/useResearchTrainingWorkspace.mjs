import { computed, ref } from 'vue';

import { api } from '../../services/api.js';
import { formatApiErrorDetail } from '../../utils/apiErrorDetail.mjs';
import { bindRealtimeConnection } from '../../utils/realtimeConnection.mjs';
import marketWS from '../../services/websocket.js';
import {
  buildDatasetCreatePayload,
  buildTrainingCreatePayload,
} from './researchPlatformDefaults.mjs';

export function useResearchTrainingWorkspace(deps = {}) {
  const apiClient = deps.api ?? api;
  const realtime = deps.realtime ?? marketWS;
  const collectionSessions = ref([]);
  const selectedSessionIds = ref([]);
  const datasets = ref([]);
  const trainingRuns = ref([]);
  const selectedDatasetId = ref('');
  const selectedRunId = ref('');
  const selectedDatasetManifest = ref(null);
  const selectedDatasetPreview = ref(null);
  const selectedRunDetail = ref(null);
  const selectedRunArtifacts = ref(null);
  const diagnosticsMode = ref('weighted');
  const comparisonResult = ref(null);
  const baselineResult = ref(null);
  const datasetActionPending = ref(false);
  const datasetActionError = ref('');
  const datasetCreatePending = ref(false);
  const datasetCreateError = ref('');
  const trainingActionPending = ref(false);
  const trainingActionError = ref('');
  const realtimeError = ref('');

  const { attachRealtimeConnection, detachRealtimeConnection } = bindRealtimeConnection({
    realtime,
    errorRef: realtimeError,
    connectMessage: '研究平台实时连接失败',
    disconnectMessage: '研究平台实时连接已断开',
  });

  const selectedSplitArtifact = computed(() => selectedRunArtifacts.value?.split_artifact || null);
  const selectedRegimeSchema = computed(() => selectedDatasetPreview.value?.regime_schema || null);

  const loadCollectionSessions = async () => {
    const response = await apiClient.getDataCenterCollectionSessions({ limit: 50 });
    collectionSessions.value = response.sessions || [];
    selectedSessionIds.value = reconcileSelectedSessionIds(selectedSessionIds.value, collectionSessions.value);
  };

  const loadDatasets = async () => {
    const response = await apiClient.getResearchPlatformDatasets({ limit: 50 });
    datasets.value = response.datasets || [];
    selectedDatasetId.value = resolveDatasetId(selectedDatasetId.value, datasets.value);
  };

  const loadDatasetDetail = async (datasetId) => {
    if (!datasetId) {
      selectedDatasetManifest.value = null;
      selectedDatasetPreview.value = null;
      return;
    }
    const [datasetResponse, previewResponse] = await Promise.all([
      apiClient.getResearchPlatformDatasetDetail(datasetId),
      apiClient.getResearchPlatformDatasetPreview(datasetId),
    ]);
    selectedDatasetManifest.value = datasetResponse.dataset || null;
    selectedDatasetPreview.value = previewResponse.preview || null;
  };

  const loadTrainingRuns = async (datasetId = '') => {
    const response = await apiClient.getResearchPlatformTrainingRuns({ dataset_id: datasetId, limit: 50 });
    trainingRuns.value = response.training_runs || [];
    selectedRunId.value = resolveRunId(selectedRunId.value, trainingRuns.value);
  };

  const loadTrainingRun = async (runId) => {
    if (!runId) {
      selectedRunDetail.value = null;
      selectedRunArtifacts.value = null;
      comparisonResult.value = null;
      baselineResult.value = null;
      return;
    }
    const response = await apiClient.getResearchPlatformTrainingRun(runId);
    selectedRunDetail.value = response.training_run || null;
    selectedRunArtifacts.value = response.training_run?.artifacts || null;
    comparisonResult.value = response.training_run?.artifacts?.comparison_result || null;
    baselineResult.value = response.training_run?.artifacts?.baseline_result || null;
  };

  const deleteDatasetManifest = async (datasetId = selectedDatasetId.value) => {
    if (!datasetId) {
      return;
    }
    datasetActionError.value = '';
    datasetActionPending.value = true;
    try {
      await apiClient.deleteResearchPlatformDataset(datasetId);
      await loadDatasets();
      await loadDatasetDetail(selectedDatasetId.value);
      if (selectedDatasetId.value) {
        await loadTrainingRuns(selectedDatasetId.value);
        return;
      }
      resetTrainingSelection(trainingRuns, selectedRunId, selectedRunDetail, selectedRunArtifacts, comparisonResult, baselineResult);
    } catch (error) {
      datasetActionError.value = formatApiErrorDetail(error, '删除数据集失败');
    } finally {
      datasetActionPending.value = false;
    }
  };

  const createDatasetManifest = async (payload = {}) => {
    const includedSessionIds = payload.included_session_ids || selectedSessionIds.value;
    if (!includedSessionIds.length) {
      datasetCreateError.value = '请先选择至少一个已完成采集会话';
      return;
    }
    datasetCreateError.value = '';
    datasetCreatePending.value = true;
    try {
      const response = await apiClient.createResearchPlatformDataset({
        ...buildDatasetCreatePayload(includedSessionIds),
        ...payload,
        included_session_ids: includedSessionIds,
      });
      const datasetId = response.dataset?.dataset_id || '';
      await loadDatasets();
      if (datasetId) {
        selectedDatasetId.value = datasetId;
        await loadDatasetDetail(datasetId);
        await loadTrainingRuns(datasetId);
      }
    } catch (error) {
      datasetCreateError.value = formatApiErrorDetail(error, '创建数据集失败');
    } finally {
      datasetCreatePending.value = false;
    }
  };

  const startTrainingRun = async (payload = {}) => {
    const datasetId = payload.dataset_id || selectedDatasetId.value;
    if (!datasetId) {
      trainingActionError.value = '请先选择一个数据集';
      return;
    }
    trainingActionError.value = '';
    trainingActionPending.value = true;
    try {
      const response = await apiClient.createResearchPlatformTrainingRun({
        ...buildTrainingCreatePayload(datasetId),
        ...payload,
        dataset_id: datasetId,
      });
      const runId = response.training_run?.run_id || '';
      await loadTrainingRuns(datasetId);
      if (runId) {
        selectedRunId.value = runId;
        await loadTrainingRun(runId);
      }
    } catch (error) {
      trainingActionError.value = formatApiErrorDetail(error, '启动训练失败');
    } finally {
      trainingActionPending.value = false;
    }
  };

  const attachRealtime = () => {
    attachRealtimeConnection();
    realtime.subscribeResearchPlatform(handleResearchPlatformEvent);
  };

  const detachRealtime = () => {
    detachRealtimeConnection();
    realtime.unsubscribeResearchPlatform(handleResearchPlatformEvent);
  };

  const handleResearchPlatformEvent = async (payload = {}) => {
    if (String(payload.event || '').startsWith('session_')) {
      await loadCollectionSessions();
    }
    if (payload.event === 'dataset_manifest_created') {
      await loadDatasets();
      if (payload.dataset_id) {
        selectedDatasetId.value = payload.dataset_id;
        await loadDatasetDetail(payload.dataset_id);
        await loadTrainingRuns(payload.dataset_id);
      }
    }
    if (payload.event === 'dataset_manifest_deleted') {
      await loadDatasets();
      await loadDatasetDetail(selectedDatasetId.value);
      if (selectedDatasetId.value) {
        await loadTrainingRuns(selectedDatasetId.value);
      } else {
        resetTrainingSelection(trainingRuns, selectedRunId, selectedRunDetail, selectedRunArtifacts, comparisonResult, baselineResult);
      }
    }
    if (payload.event === 'training_run_updated') {
      await loadTrainingRuns(selectedDatasetId.value);
      if (payload.run_id) {
        selectedRunId.value = payload.run_id;
        await loadTrainingRun(payload.run_id);
      }
    }
  };

  return {
    collectionSessions,
    selectedSessionIds,
    datasets,
    trainingRuns,
    selectedDatasetId,
    selectedRunId,
    selectedDatasetManifest,
    selectedDatasetPreview,
    selectedRunDetail,
    selectedRunArtifacts,
    selectedSplitArtifact,
    selectedRegimeSchema,
    diagnosticsMode,
    comparisonResult,
    baselineResult,
    datasetActionPending,
    datasetActionError,
    datasetCreatePending,
    datasetCreateError,
    trainingActionPending,
    trainingActionError,
    realtimeError,
    loadCollectionSessions,
    loadDatasets,
    loadDatasetDetail,
    loadTrainingRuns,
    loadTrainingRun,
    createDatasetManifest,
    startTrainingRun,
    deleteDatasetManifest,
    attachRealtime,
    detachRealtime,
  };
}

function resolveDatasetId(currentDatasetId, datasets) {
  if (currentDatasetId && datasets.some(dataset => dataset.dataset_id === currentDatasetId)) {
    return currentDatasetId;
  }
  return datasets[0]?.dataset_id || '';
}

function resolveRunId(currentRunId, trainingRuns) {
  if (currentRunId && trainingRuns.some(run => run.run_id === currentRunId)) {
    return currentRunId;
  }
  return trainingRuns[0]?.run_id || '';
}

function reconcileSelectedSessionIds(currentIds, sessions) {
  const sessionIdSet = new Set(sessions.map(session => session.session_id));
  return currentIds.filter(sessionId => sessionIdSet.has(sessionId));
}

function resetTrainingSelection(
  trainingRuns,
  selectedRunId,
  selectedRunDetail,
  selectedRunArtifacts,
  comparisonResult,
  baselineResult,
) {
  trainingRuns.value = [];
  selectedRunId.value = '';
  selectedRunDetail.value = null;
  selectedRunArtifacts.value = null;
  comparisonResult.value = null;
  baselineResult.value = null;
}
