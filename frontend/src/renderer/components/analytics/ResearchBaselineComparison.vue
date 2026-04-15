<template>
  <section class="card trend-research-card">
    <div class="research-panel-header">
      <div>
        <h4>Baseline 与多模型比较</h4>
        <p class="research-panel-desc">区分 reference baseline 汇总与 locked candidate set 的 outer test 比较结果。</p>
      </div>
    </div>
    <div v-if="!comparison && !baselineRows.length" class="trend-subpage-placeholder empty-state trend-empty-info">
      <strong>尚无 comparison_result</strong>
      <p>训练完成后，这里会展示 candidate_set_ref、retained_model_set 与各 baseline 的聚合指标。</p>
    </div>
    <div v-else class="research-panel-stack">
      <section v-if="comparison" class="research-panel-section">
        <h5>Locked Candidate Set</h5>
        <div class="research-kv-grid">
          <article v-for="item in comparisonSummaryRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section v-if="candidateRanking.length" class="research-panel-section">
        <h5>candidate_ranking</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>rank</th>
                <th>candidate_id</th>
                <th>candidate_kind</th>
                <th>joint_nll_mean</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in candidateRanking" :key="row.candidate_id">
                <td>{{ row.rank }}</td>
                <td>{{ row.candidate_id }}</td>
                <td>{{ row.candidate_kind }}</td>
                <td>{{ formatMetricNumber(row.joint_nll_mean) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="pairwiseResults.length" class="research-panel-section">
        <h5>pairwise_results</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>candidate_id</th>
                <th>reference_candidate_id</th>
                <th>delta_mean</th>
                <th>ci_95</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in pairwiseResults" :key="row.candidate_id">
                <td>{{ row.candidate_id }}</td>
                <td>{{ row.reference_candidate_id }}</td>
                <td>{{ formatMetricNumber(row.delta_mean) }}</td>
                <td>{{ formatConfidenceInterval(row.paired_block_bootstrap_result?.ci_95) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="baselineRows.length" class="research-panel-section">
        <h5>baseline_result</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>baseline_id</th>
                <th>joint_nll</th>
                <th>mean_utility</th>
                <th>net_return</th>
                <th>max_drawdown</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in baselineRows" :key="row.baseline_id">
                <td>{{ row.baseline_id }}</td>
                <td>{{ row.joint_nll }}</td>
                <td>{{ row.mean_utility }}</td>
                <td>{{ row.net_return }}</td>
                <td>{{ row.max_drawdown }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import { formatCompactNumber } from '../../utils/formatting.js';

const props = defineProps({
  comparison: {
    type: Object,
    default: null,
  },
  baselineResult: {
    type: Object,
    default: null,
  },
});

const candidateRanking = computed(() => props.comparison?.candidate_ranking || []);
const pairwiseResults = computed(() => props.comparison?.pairwise_results || []);
const comparisonSummaryRows = computed(() => ([
  { label: 'candidate_set_ref', value: props.comparison?.candidate_set_ref || '--' },
  { label: 'best_candidate_id', value: props.comparison?.best_candidate_id || '--' },
  { label: 'reference_candidate_id', value: props.comparison?.reference_candidate_id || '--' },
  { label: 'retained_model_set', value: listItems(props.comparison?.retained_model_set) },
  { label: 'multiple_comparison_version', value: props.comparison?.multiple_comparison_version || '--' },
  { label: 'retained_model_rule', value: props.comparison?.data_snooping_control?.retention_rule || '--' },
]));
const baselineRows = computed(() => (props.baselineResult?.baselines || []).map(baseline => ({
  baseline_id: baseline.baseline_id,
  joint_nll: formatMetricBundle(baseline.aggregate?.forecast_metrics?.joint_nll),
  mean_utility: formatMetricBundle(baseline.aggregate?.decision_metrics?.mean_utility),
  net_return: formatMetricBundle(baseline.aggregate?.decision_metrics?.net_return),
  max_drawdown: formatMetricBundle(baseline.aggregate?.decision_metrics?.max_drawdown),
})));

function listItems(value) {
  return Array.isArray(value) && value.length ? value.join(' / ') : '--';
}

function formatMetricBundle(metric) {
  if (metric && typeof metric === 'object' && Number.isFinite(Number(metric.mean))) {
    return formatMetricNumber(metric.mean);
  }
  return formatMetricNumber(metric);
}

function formatMetricNumber(value) {
  return formatCompactNumber(value, { digits: 6, scientificDigits: 3, maxChars: 12 });
}

function formatConfidenceInterval(value) {
  if (!Array.isArray(value) || value.length !== 2) {
    return '--';
  }
  return `[${formatMetricNumber(value[0])}, ${formatMetricNumber(value[1])}]`;
}
</script>

<style scoped src="./trendResearchPanel.css"></style>
