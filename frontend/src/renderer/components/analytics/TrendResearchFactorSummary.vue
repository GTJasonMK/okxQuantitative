<template>
  <section class="trend-factor-strip">
    <div class="trend-factor-strip-header">
      <div>
        <h4>因子筛选</h4>
        <p class="trend-factor-strip-caption">{{ summaryCaption }}</p>
      </div>
      <span class="trend-factor-strip-lookback">{{ lookbackLabel }}</span>
    </div>

    <div v-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="loading && rows.length === 0" class="empty-state">加载因子筛选...</div>
    <div v-else-if="rows.length === 0" class="empty-state">当前窗口内暂无可展示的因子。</div>
    <div v-else class="trend-factor-strip-body">
      <div class="trend-factor-primary-row">
        <button
          v-for="factor in primaryRows"
          :key="factor.factorName"
          type="button"
          class="trend-factor-pill"
          :class="{
            'is-selected': factor.factorName === selectedFactorName,
            'is-unavailable': !factor.available,
          }"
          :disabled="!factor.selectable"
          :title="buildFactorTitle(factor)"
          @click="emit('select-factor', factor.factorName)"
        >
          <strong class="trend-factor-pill-title">{{ factor.factorLabel }}</strong>
        </button>
        <button
          v-if="hiddenCount > 0"
          type="button"
          class="trend-factor-expand-button"
          :class="{ 'is-open': expanded }"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收起' : `展开全部 (${hiddenCount})` }}
        </button>
      </div>

      <div v-if="selectedFactorDetail" class="trend-factor-current-meta">
        <strong>{{ selectedFactorDetail.factorLabel }}</strong>
        <span>稳 {{ selectedFactorDetail.stabilityScore }}</span>
        <span>IC {{ selectedFactorDetail.spearmanIc }}</span>
      </div>

      <div v-if="expanded" class="trend-factor-all-row">
        <button
          v-for="factor in secondaryRows"
          :key="factor.factorName"
          type="button"
          class="trend-factor-pill is-compact"
          :class="{
            'is-selected': factor.factorName === selectedFactorName,
            'is-unavailable': !factor.available,
          }"
          :disabled="!factor.selectable"
          :title="buildFactorTitle(factor)"
          @click="emit('select-factor', factor.factorName)"
        >
          <strong class="trend-factor-pill-title">{{ factor.factorLabel }}</strong>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

const DEFAULT_VISIBLE_COUNT = 6;

const emit = defineEmits(['select-factor']);

const props = defineProps({
  error: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  lookbackLabel: {
    type: String,
    default: '',
  },
  rows: {
    type: Array,
    default: () => [],
  },
  selectedRow: {
    type: Object,
    default: null,
  },
  selectedFactorName: {
    type: String,
    default: '',
  },
});

const expanded = ref(false);

const summaryCaption = computed(() => {
  if (!props.selectedRow) {
    return '选择一个合约后，在这里聚焦单个因子。';
  }
  return `${props.selectedRow.instId} · 点击因子可在图表中高亮`;
});

const selectedFactorDetail = computed(() => {
  if (!props.selectedFactorName) {
    return null;
  }
  return props.rows.find((row) => row.factorName === props.selectedFactorName) || null;
});

const primaryRows = computed(() => {
  if (selectedFactorDetail.value) {
    return [selectedFactorDetail.value];
  }
  return props.rows.slice(0, DEFAULT_VISIBLE_COUNT);
});

const secondaryRows = computed(() => {
  const primaryNames = new Set(primaryRows.value.map((row) => row.factorName));
  return props.rows.filter((row) => !primaryNames.has(row.factorName));
});

const hiddenCount = computed(() => secondaryRows.value.length);

const buildFactorTitle = (factor) => {
  return `${factor.factorLabel} | 稳 ${factor.stabilityScore} | IC ${factor.spearmanIc}`;
};

watch(() => props.selectedFactorName, (value) => {
  if (value) {
    expanded.value = false;
  }
});
</script>

<style scoped src="./trendResearchFactorSummary.css"></style>
