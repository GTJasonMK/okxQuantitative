<template>
  <section class="card trend-research-card">
    <button type="button" class="trend-subnav-tab" :class="{ 'is-active': modelValue === 'weighted' }" @click="$emit('update:modelValue', 'weighted')">
      weighted
    </button>
    <button type="button" class="trend-subnav-tab" :class="{ 'is-active': modelValue === 'unweighted' }" @click="$emit('update:modelValue', 'unweighted')">
      unweighted
    </button>
  </section>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    default: 'weighted',
  },
});

defineEmits(['update:modelValue']);
</script>

<style scoped src="./trendResearchPanel.css"></style>
