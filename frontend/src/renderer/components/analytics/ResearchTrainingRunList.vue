<template>
  <section class="card trend-research-card">
    <h4>训练运行列表</h4>
    <button
      v-for="run in runs"
      :key="run.run_id"
      type="button"
      class="trend-subnav-tab"
      :class="{ 'is-active': run.run_id === selectedRunId }"
      @click="$emit('update:selectedRunId', run.run_id)"
    >
      {{ run.run_id }}
    </button>
  </section>
</template>

<script setup>
defineProps({
  runs: {
    type: Array,
    default: () => [],
  },
  selectedRunId: {
    type: String,
    default: '',
  },
});

defineEmits(['update:selectedRunId']);
</script>

<style scoped src="./trendResearchPanel.css"></style>
