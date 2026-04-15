<template>
  <section class="trend-diagnostics-card trend-diagnostics-conclusion">
    <header class="trend-diagnostics-block-header">
      <div>
        <p class="trend-diagnostics-eyebrow">当前结论</p>
        <h4>{{ conclusion.title || '暂无运行进度结论' }}</h4>
        <p class="trend-diagnostics-block-desc">{{ conclusion.message || '等待新的运行数据...' }}</p>
      </div>
      <span v-if="loading" class="trend-diagnostics-inline-tag">同步中</span>
    </header>

    <div class="trend-diagnostics-conclusion-meta">
      <article v-for="item in conclusion.metaItems || []" :key="item.label" class="trend-diagnostics-metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  conclusion: {
    type: Object,
    default: () => ({
      title: '',
      message: '',
      metaItems: [],
    }),
  },
  loading: {
    type: Boolean,
    default: false,
  },
});
</script>

<style scoped src="./trendDiagnostics.css"></style>
