<template>
  <section class="card trend-research-card">
    <h4>质量概览</h4>
    <p>coverage_ratio: {{ coverage.coverageRatio }}</p>
    <p>valid_second_count: {{ coverage.validSecondCount }}</p>
    <p>missing_second_count: {{ coverage.missingSecondCount }}</p>
    <p>book_stale_second_count: {{ coverage.bookStaleSecondCount }}</p>
    <p>state_stale_second_count: {{ coverage.stateStaleSecondCount }}</p>
    <p>inference-ready: {{ coverage.inferenceReadyCount }}</p>
    <p>training-ready: {{ coverage.trainingReadyCount }}</p>
  </section>
</template>

<script setup>
defineProps({
  coverage: {
    type: Object,
    default: () => ({}),
  },
});
</script>

<style scoped src="./trendResearchPanel.css"></style>
