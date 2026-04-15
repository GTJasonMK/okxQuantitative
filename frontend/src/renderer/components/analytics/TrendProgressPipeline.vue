<template>
  <section class="trend-diagnostics-card trend-diagnostics-pipeline">
    <header class="trend-diagnostics-block-header">
      <div>
        <p class="trend-diagnostics-eyebrow">流程主线</p>
        <h4>五阶段进度</h4>
      </div>
      <span class="trend-diagnostics-block-caption">先看当前走到哪一步，再判断为什么停在这里</span>
    </header>

    <div class="trend-diagnostics-pipeline-grid">
      <article
        v-for="step in steps"
        :key="step.key"
        class="trend-diagnostics-pipeline-step"
        :class="[`tone-${step.tone}`, { 'is-current': step.isCurrent }]"
      >
        <span class="trend-diagnostics-pipeline-label">{{ step.label }}</span>
        <strong>{{ step.statusLabel }}</strong>
        <span>{{ step.note }}</span>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  steps: {
    type: Array,
    default: () => [],
  },
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
