<template>
  <section class="trend-prediction-summary">
    <div class="trend-summary-main">
      <span class="trend-summary-eyebrow">当前结论</span>
      <h4>{{ row?.instId || '--' }}</h4>
      <div class="trend-summary-score-row">
        <strong class="trend-summary-score" :class="row?.scoreSignClass">{{ row?.trendScore || '--' }}</strong>
        <span
          v-if="row"
          class="trend-state-badge"
          :class="`tone-${row.trendStateTone}`"
        >{{ row.trendStateLabel }}</span>
      </div>
      <p class="trend-summary-caption">{{ model.caption }}</p>
    </div>
    <div class="trend-summary-grid">
      <article v-for="card in model.cards" :key="card.label" class="trend-summary-stat">
        <span class="trend-summary-stat-label">{{ card.label }}</span>
        <strong class="trend-summary-stat-value">{{ card.value }}</strong>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  row: {
    type: Object,
    default: null,
  },
  model: {
    type: Object,
    default: () => ({
      caption: '',
      cards: [],
    }),
  },
});
</script>

<style scoped src="./trendResearchPredictionSummary.css"></style>
