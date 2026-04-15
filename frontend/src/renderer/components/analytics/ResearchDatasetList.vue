<template>
  <section class="card trend-research-card">
    <h4>数据集列表</h4>
    <button
      v-for="dataset in datasets"
      :key="dataset.dataset_id"
      type="button"
      class="trend-subnav-tab"
      :class="{ 'is-active': dataset.dataset_id === selectedDatasetId }"
      @click="$emit('update:selectedDatasetId', dataset.dataset_id)"
    >
      {{ dataset.dataset_id }}
    </button>
  </section>
</template>

<script setup>
defineProps({
  datasets: {
    type: Array,
    default: () => [],
  },
  selectedDatasetId: {
    type: String,
    default: '',
  },
});

defineEmits(['update:selectedDatasetId']);
</script>

<style scoped src="./trendResearchPanel.css"></style>
