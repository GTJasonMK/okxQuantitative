<template>
  <section class="trend-research-layout">
    <section class="card trend-research-card">
      <h4>冻结协议训练视图</h4>
      <p>围绕 dataset_manifest、rolling-origin、weighted diagnostics 与多模型比较结果展示当前训练状态。</p>
    </section>
    <ResearchTrainingControlCard
      :selected-dataset-id="selectedDatasetId"
      :action-pending="trainingActionPending"
      :action-error="trainingActionError"
      @start-training="$emit('startTraining', $event)"
    />
    <ResearchDatasetList
      :datasets="datasets"
      :selected-dataset-id="selectedDatasetId"
      @update:selected-dataset-id="$emit('update:selectedDatasetId', $event)"
    />
    <ResearchDatasetManifestCard
      :manifest="selectedDatasetManifest"
      :preview="selectedDatasetPreview"
      :show-actions="false"
    />
    <ResearchTrainingRunList
      :runs="trainingRuns"
      :selected-run-id="selectedRunId"
      @update:selected-run-id="$emit('update:selectedRunId', $event)"
    />
    <ResearchTrainingRunDetail :run="selectedRunDetail" :split-artifact="selectedSplitArtifact" />
    <ResearchDiagnosticsToggle
      :model-value="diagnosticsMode"
      @update:model-value="$emit('update:diagnosticsMode', $event)"
    />
    <ResearchEvaluationSummary
      :artifacts="selectedRunArtifacts"
      :mode="diagnosticsMode"
      :regime-schema="selectedRegimeSchema"
    />
    <ResearchBootstrapPanel :bootstrap="selectedRunArtifacts?.bootstrap_result" />
    <ResearchBaselineComparison
      :comparison="comparisonResult"
      :baseline-result="baselineResult"
    />
  </section>
</template>

<script setup>
import ResearchBaselineComparison from './ResearchBaselineComparison.vue';
import ResearchBootstrapPanel from './ResearchBootstrapPanel.vue';
import ResearchDatasetList from './ResearchDatasetList.vue';
import ResearchDatasetManifestCard from './ResearchDatasetManifestCard.vue';
import ResearchDiagnosticsToggle from './ResearchDiagnosticsToggle.vue';
import ResearchEvaluationSummary from './ResearchEvaluationSummary.vue';
import ResearchTrainingControlCard from './ResearchTrainingControlCard.vue';
import ResearchTrainingRunDetail from './ResearchTrainingRunDetail.vue';
import ResearchTrainingRunList from './ResearchTrainingRunList.vue';

defineProps({
  datasets: {
    type: Array,
    default: () => [],
  },
  trainingRuns: {
    type: Array,
    default: () => [],
  },
  selectedDatasetId: {
    type: String,
    default: '',
  },
  selectedDatasetManifest: {
    type: Object,
    default: null,
  },
  selectedDatasetPreview: {
    type: Object,
    default: null,
  },
  selectedRunId: {
    type: String,
    default: '',
  },
  trainingActionPending: {
    type: Boolean,
    default: false,
  },
  trainingActionError: {
    type: String,
    default: '',
  },
  selectedRunDetail: {
    type: Object,
    default: null,
  },
  selectedRunArtifacts: {
    type: Object,
    default: null,
  },
  selectedSplitArtifact: {
    type: Object,
    default: null,
  },
  selectedRegimeSchema: {
    type: Object,
    default: null,
  },
  comparisonResult: {
    type: Object,
    default: null,
  },
  baselineResult: {
    type: Object,
    default: null,
  },
  diagnosticsMode: {
    type: String,
    default: 'weighted',
  },
});

defineEmits([
  'update:selectedDatasetId',
  'update:selectedRunId',
  'update:diagnosticsMode',
  'startTraining',
]);
</script>

<style scoped src="./trendResearchPanel.css"></style>
