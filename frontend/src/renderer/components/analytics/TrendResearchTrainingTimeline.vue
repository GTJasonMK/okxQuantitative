<template>
  <ol class="trend-training-timeline">
    <li
      v-for="row in rows"
      :key="row.key"
      class="trend-training-stage"
      :data-status="row.status"
      :data-current="row.isCurrent"
    >
      <div class="trend-training-stage-head">
        <div class="trend-training-stage-title">
          <strong>{{ row.label }}</strong>
          <span class="trend-training-stage-status">{{ row.statusLabel }}</span>
          <span v-if="row.isCurrent" class="trend-training-stage-current">当前</span>
        </div>
        <span>{{ row.durationLabel }}</span>
      </div>
      <p>{{ row.message || row.description || '等待执行' }}</p>
      <div class="trend-training-stage-times">
        <span>开始 {{ row.startedAtLabel }}</span>
        <span>结束 {{ row.finishedAtLabel }}</span>
      </div>
      <div class="trend-training-stage-stats">
        <span v-for="stat in row.stats" :key="stat.key">
          {{ stat.label }} {{ stat.value }}
        </span>
      </div>
    </li>
  </ol>
</template>

<script setup>
defineProps({
  rows: {
    type: Array,
    default: () => [],
  },
});
</script>

<style scoped src="./trendResearchTrainingTimeline.css"></style>
