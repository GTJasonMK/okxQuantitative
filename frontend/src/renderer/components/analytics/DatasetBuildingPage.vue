<template>
  <section class="trend-research-layout">
    <ResearchDatasetBuilder
      :sessions="collectionSessions"
      :selected-session-ids="selectedSessionIds"
      :create-pending="datasetCreatePending"
      :create-error="datasetCreateError"
      @update:selected-session-ids="$emit('update:selectedSessionIds', $event)"
      @create-dataset="$emit('createDataset')"
      @refresh-sessions="$emit('refreshCollectionSessions')"
    />
    <ResearchDatasetList
      :datasets="datasets"
      :selected-dataset-id="selectedDatasetId"
      @update:selected-dataset-id="$emit('update:selectedDatasetId', $event)"
    />
    <ResearchDatasetManifestCard
      :manifest="selectedDatasetManifest"
      :preview="selectedDatasetPreview"
      :action-pending="datasetActionPending"
      :action-error="datasetActionError"
      @delete-dataset="$emit('deleteDataset', $event)"
    />
  </section>
</template>

<script setup>
import ResearchDatasetBuilder from './ResearchDatasetBuilder.vue';
import ResearchDatasetList from './ResearchDatasetList.vue';
import ResearchDatasetManifestCard from './ResearchDatasetManifestCard.vue';

defineProps({
  datasets: {
    type: Array,
    default: () => [],
  },
  collectionSessions: {
    type: Array,
    default: () => [],
  },
  selectedSessionIds: {
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
  datasetActionPending: {
    type: Boolean,
    default: false,
  },
  datasetActionError: {
    type: String,
    default: '',
  },
  datasetCreatePending: {
    type: Boolean,
    default: false,
  },
  datasetCreateError: {
    type: String,
    default: '',
  },
});

defineEmits([
  'update:selectedDatasetId',
  'update:selectedSessionIds',
  'createDataset',
  'deleteDataset',
  'refreshCollectionSessions',
]);
</script>

<style scoped src="./trendResearchPanel.css"></style>
