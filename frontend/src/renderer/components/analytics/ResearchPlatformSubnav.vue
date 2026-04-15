<template>
  <nav class="trend-subnav" aria-label="研究平台子页面">
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
    default: 'dataset-building',
  },
});

defineEmits(['update:modelValue']);

const items = Object.freeze([
  { value: 'dataset-building', label: '数据集构建' },
  { value: 'model-training', label: '模型训练' },
]);
</script>

<style scoped src="./trendResearchPanel.css"></style>
