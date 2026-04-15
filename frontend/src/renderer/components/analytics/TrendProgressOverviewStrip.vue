<template>
  <section class="trend-diagnostics-overview-strip">
    <article v-for="item in items" :key="item.label" class="trend-diagnostics-overview-stat">
      <span>{{ item.label }}</span>
      <strong>{{ item.value }}</strong>
    </article>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
