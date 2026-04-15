<template>
  <section class="card trend-research-card">
    <h4>会话内 1s 曲线</h4>
    <p>price: {{ series.price?.length || 0 }}</p>
    <p>trade: {{ series.trade?.length || 0 }}</p>
    <p>book: {{ series.book?.length || 0 }}</p>
  </section>
</template>

<script setup>
defineProps({
  series: {
    type: Object,
    default: () => ({ price: [], trade: [], book: [] }),
  },
});
</script>

<style scoped src="./trendResearchPanel.css"></style>
