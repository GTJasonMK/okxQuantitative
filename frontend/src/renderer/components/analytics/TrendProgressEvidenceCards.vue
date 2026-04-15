<template>
  <section class="trend-diagnostics-evidence-grid">
    <article v-for="card in cards" :key="card.label" class="trend-diagnostics-card trend-diagnostics-evidence-card">
      <header class="trend-diagnostics-block-header">
        <div>
          <p class="trend-diagnostics-eyebrow">解释与证据</p>
          <h4>{{ card.label }}</h4>
        </div>
      </header>

      <div class="trend-diagnostics-detail-grid">
        <article v-for="item in card.items || []" :key="item.label" class="trend-diagnostics-detail-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </article>
  </section>
</template>

<script setup>
defineProps({
  cards: {
    type: Array,
    default: () => [],
  },
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
