<template>
  <section class="card trend-research-card">
    <h4>覆盖分布</h4>
    <p>stratumCoverage: {{ coverage.stratumCoverage?.length || 0 }}</p>
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
