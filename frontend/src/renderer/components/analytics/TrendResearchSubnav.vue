<template>
  <nav class="trend-subnav" aria-label="趋势研究子页面">
    <button
      v-for="item in items"
      :key="item.value"
      type="button"
      class="trend-subnav-tab"
      :class="{ 'is-active': item.value === modelValue }"
      @click="$emit('update:modelValue', item.value)"
    >
      {{ item.label }}
    </button>
  </nav>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    default: 'overview',
  },
});

defineEmits(['update:modelValue']);

const items = Object.freeze([
  { value: 'overview', label: '结论总览' },
  { value: 'factors', label: '因子分析' },
  { value: 'training', label: '训练模型' },
  { value: 'diagnostics', label: '过程诊断' },
]);
</script>

<style scoped src="./trendResearchPanel.css"></style>
