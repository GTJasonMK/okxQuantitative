<template>
  <section class="card trend-training-panel">
    <div class="trend-training-header">
      <div>
        <h4>分析链路与训练进度</h4>
        <p>{{ model.errorMessage || model.message }}</p>
      </div>
      <div class="trend-training-actions">
        <button
          class="btn btn-secondary btn-sm"
          :disabled="requesting || model.disableStart"
          @click="emit('start-retrain')"
        >
          {{ requesting || model.disableStart ? '训练中...' : '开始重训' }}
        </button>
        <span class="trend-training-status">{{ model.statusLabel }}</span>
      </div>
    </div>

    <div v-if="errorMessage" class="error-message">{{ errorMessage }}</div>

    <div class="trend-training-meta">
      <span>Run ID {{ model.runIdLabel }}</span>
      <span>开始 {{ model.startedAtLabel }}</span>
      <span>结束 {{ model.finishedAtLabel }}</span>
      <span>累计耗时 {{ model.durationLabel }}</span>
    </div>

    <section class="trend-training-summary">
      <article
        v-for="card in model.summaryCards"
        :key="card.key"
        class="trend-training-summary-card"
      >
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </article>
    </section>

    <div class="trend-training-main">
      <section class="trend-training-stage-focus">
        <div class="trend-training-section-head">
          <h5>当前阶段</h5>
          <span>{{ model.currentStageCard.statusLabel }}</span>
        </div>
        <strong class="trend-training-stage-focus-title">{{ model.currentStageCard.label }}</strong>
        <p class="trend-training-stage-focus-desc">{{ model.currentStageCard.description }}</p>
        <p class="trend-training-stage-focus-message">{{ model.currentStageCard.message }}</p>
        <div class="trend-training-stage-focus-meta">
          <span>开始 {{ model.currentStageCard.startedAtLabel }}</span>
          <span>结束 {{ model.currentStageCard.finishedAtLabel }}</span>
          <span>耗时 {{ model.currentStageCard.durationLabel }}</span>
        </div>
        <div
          v-if="model.currentStageCard.stats.length > 0"
          class="trend-training-stage-focus-stats"
        >
          <article
            v-for="stat in model.currentStageCard.stats"
            :key="stat.key"
            class="trend-training-stage-focus-stat"
          >
            <span>{{ stat.label }}</span>
            <strong>{{ stat.value }}</strong>
          </article>
        </div>
        <div v-else class="empty-state">当前阶段暂无额外统计</div>
      </section>

      <section class="trend-training-stage-timeline">
        <div class="trend-training-section-head">
          <h5>阶段时间线</h5>
          <span>按后端实际链路实时更新</span>
        </div>
        <TrendResearchTrainingTimeline :rows="model.stageRows" />
      </section>
    </div>

    <div class="trend-training-bottom">
      <section class="trend-training-curves-section">
        <div class="trend-training-section-head">
          <h5>训练曲线</h5>
          <span>仅在 Epoch 训练开始后出现</span>
        </div>
        <TrendResearchTrainingCurves :groups="model.curveGroups" />
      </section>

      <section class="trend-training-metrics">
        <div class="trend-training-section-head">
          <h5>验证结果</h5>
          <span>来自当前模型或最近一次评估</span>
        </div>
        <div v-if="model.metricCards.length === 0" class="empty-state">等待评估结果</div>
        <div v-else class="trend-training-metric-grid">
          <article
            v-for="card in model.metricCards"
            :key="card.label"
            class="trend-training-metric-card"
          >
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import TrendResearchTrainingTimeline from './TrendResearchTrainingTimeline.vue';
import TrendResearchTrainingCurves from './TrendResearchTrainingCurves.vue';

defineProps({
  model: {
    type: Object,
    default: () => ({}),
  },
  errorMessage: {
    type: String,
    default: '',
  },
  requesting: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['start-retrain']);
</script>

<style scoped src="./trendResearchTrainingRunPanel.css"></style>
