<template>
  <section class="trend-model-card" :class="`tone-${modelStatus.tone || 'neutral'}`">
    <div class="trend-model-header">
      <div>
        <h4>模型状态</h4>
        <p>{{ modelStatus.description }}</p>
      </div>
      <span class="trend-model-badge" :class="`tone-${modelStatus.ready ? 'ok' : (modelStatus.tone || 'neutral')}`">
        {{ modelStatus.title }}
      </span>
    </div>
    <div class="trend-model-grid">
      <div class="trend-model-metric">
        <span class="trend-model-label">预测来源</span>
        <strong class="trend-model-value">{{ modelStatus.probabilitySourceLabel }}</strong>
      </div>
      <div class="trend-model-metric">
        <span class="trend-model-label">预测周期</span>
        <strong class="trend-model-value">{{ modelStatus.horizonLabel }}</strong>
      </div>
      <div class="trend-model-metric">
        <span class="trend-model-label">训练时间</span>
        <strong class="trend-model-value trend-model-value-wrap">{{ modelStatus.trainedAtLabel }}</strong>
      </div>
      <div class="trend-model-metric">
        <span class="trend-model-label">入模特征</span>
        <strong class="trend-model-value">{{ modelStatus.selectedFeatureCountLabel }}</strong>
      </div>
    </div>
    <div class="trend-model-validation-grid">
      <div v-for="card in modelStatus.validationCards || []" :key="card.label" class="trend-model-validation-card">
        <span class="trend-model-label">{{ card.label }}</span>
        <strong class="trend-model-value trend-model-value-wrap">{{ card.value }}</strong>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  modelStatus: {
    type: Object,
    default: () => ({
      ready: false,
      title: '模型未训练',
      tone: 'warning',
      description: '',
      probabilitySourceLabel: '--',
      horizonLabel: '--',
      trainedAtLabel: '--',
      selectedFeatureCountLabel: '--',
      validationCards: [],
    }),
  },
});
</script>

<style scoped src="./trendResearchModelStatus.css"></style>
