<template>
  <section class="card trend-research-card">
    <div class="section-header">
      <div>
        <h3 class="card-title">数据集平台</h3>
        <p class="section-desc">把秒级原始数据组织成数据集，并基于数据集发起训练。</p>
      </div>
    </div>
    <ResearchPlatformSubnav v-model="activePage" />
    <div class="trend-subpage-host">
      <DatasetBuildingPage
        v-if="activePage === 'dataset-building'"
        :collection-sessions="collectionSessions"
        :datasets="datasets"
        :selected-session-ids="selectedSessionIds"
        :selected-dataset-id="selectedDatasetId"
        :selected-dataset-manifest="selectedDatasetManifest"
        :selected-dataset-preview="selectedDatasetPreview"
        :dataset-action-pending="datasetActionPending"
        :dataset-action-error="datasetDisplayError"
        :dataset-create-pending="datasetCreatePending"
        :dataset-create-error="datasetCreateError"
        @update:selected-session-ids="selectedSessionIds = $event"
        @update:selected-dataset-id="selectedDatasetId = $event"
        @create-dataset="createDatasetManifest()"
        @refresh-collection-sessions="loadCollectionSessions()"
        @delete-dataset="requestDeleteDataset"
      />
      <ModelTrainingPage
        v-else-if="activePage === 'model-training'"
        :datasets="datasets"
        :training-action-pending="trainingActionPending"
        :training-action-error="trainingDisplayError"
        :training-runs="trainingRuns"
        :selected-dataset-id="selectedDatasetId"
        :selected-dataset-manifest="selectedDatasetManifest"
        :selected-dataset-preview="selectedDatasetPreview"
        :selected-run-id="selectedRunId"
        :selected-run-detail="selectedRunDetail"
        :selected-run-artifacts="selectedRunArtifacts"
        :selected-split-artifact="selectedSplitArtifact"
        :selected-regime-schema="selectedRegimeSchema"
        :comparison-result="comparisonResult"
        :baseline-result="baselineResult"
        :diagnostics-mode="diagnosticsMode"
        @update:selected-dataset-id="selectedDatasetId = $event"
        @update:selected-run-id="selectedRunId = $event"
        @update:diagnostics-mode="diagnosticsMode = $event"
        @start-training="startTrainingRun($event)"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import DatasetBuildingPage from './DatasetBuildingPage.vue';
import ModelTrainingPage from './ModelTrainingPage.vue';
import ResearchPlatformSubnav from './ResearchPlatformSubnav.vue';
import { useResearchTrainingWorkspace } from './useResearchTrainingWorkspace.mjs';

const activePage = ref('dataset-building');

const {
  attachRealtime,
  baselineResult,
  comparisonResult,
  collectionSessions,
  datasets,
  datasetActionError,
  datasetActionPending,
  datasetCreateError,
  datasetCreatePending,
  detachRealtime,
  diagnosticsMode,
  createDatasetManifest,
  deleteDatasetManifest,
  loadCollectionSessions,
  loadDatasetDetail,
  loadDatasets,
  loadTrainingRun,
  loadTrainingRuns,
  selectedDatasetId,
  selectedDatasetManifest,
  selectedDatasetPreview,
  selectedRegimeSchema,
  selectedRunArtifacts,
  selectedRunDetail,
  selectedRunId,
  selectedSessionIds,
  selectedSplitArtifact,
  startTrainingRun,
  trainingActionError,
  trainingActionPending,
  trainingRuns,
  realtimeError,
} = useResearchTrainingWorkspace();

const datasetDisplayError = computed(() => {
  return realtimeError.value || datasetActionError.value;
});

const trainingDisplayError = computed(() => {
  return realtimeError.value || trainingActionError.value;
});

watch(selectedDatasetId, (datasetId) => {
  void loadDatasetDetail(datasetId);
  void loadTrainingRuns(datasetId);
});

watch(selectedRunId, (runId) => {
  void loadTrainingRun(runId);
});

onMounted(() => {
  void loadCollectionSessions();
  void loadDatasets();
  attachRealtime();
});

onBeforeUnmount(() => {
  detachRealtime();
});

function requestDeleteDataset(datasetId) {
  if (!datasetId) {
    return;
  }
  if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
    const confirmed = window.confirm('确认删除该数据集 manifest 吗？若该数据集仍被训练运行引用，将被阻止删除。');
    if (!confirmed) {
      return;
    }
  }
  void deleteDatasetManifest(datasetId);
}
</script>

<style scoped src="./trendResearchPanel.css"></style>
