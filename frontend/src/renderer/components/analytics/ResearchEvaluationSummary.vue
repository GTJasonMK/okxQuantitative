<template>
  <section class="card trend-research-card">
    <div class="research-panel-header">
      <div>
        <h4>评估摘要</h4>
        <p class="research-panel-desc">按冻结协议展示 rolling-origin、weighted diagnostics 与 regime 结果。</p>
      </div>
      <span class="research-note-pill" :class="{ 'is-active': mode === 'weighted' }">
        当前视图: {{ mode }}
      </span>
    </div>
    <div v-if="!artifacts" class="trend-subpage-placeholder empty-state trend-empty-info">
      <strong>尚未选择训练运行</strong>
      <p>选择一个 training run 后，这里会展开 across-origin 统计、by_origin 序列与诊断结果。</p>
    </div>
    <div v-else class="research-panel-stack">
      <div class="research-note-row">
        <span class="research-note-pill" :class="{ 'is-active': mode === 'weighted' }">
          weighted = 目标总体口径
        </span>
        <span class="research-note-pill" :class="{ 'is-active': mode === 'unweighted' }">
          unweighted = 当前验证集经验分布口径
        </span>
      </div>

      <section class="research-panel-section">
        <h5>Forecast Layer</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>metric</th>
                <th>mean</th>
                <th>median</th>
                <th>dispersion</th>
                <th>worst_origin_ts</th>
                <th>worst_value</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in forecastMetricRows" :key="row.label">
                <td>{{ row.label }}</td>
                <td>{{ row.mean }}</td>
                <td>{{ row.median }}</td>
                <td>{{ row.dispersion }}</td>
                <td>{{ row.worst_origin_ts }}</td>
                <td>{{ row.worst_value }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>Decision Layer</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>metric</th>
                <th>mean</th>
                <th>median</th>
                <th>dispersion</th>
                <th>worst_origin_ts</th>
                <th>worst_value</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in decisionMetricRows" :key="row.label">
                <td>{{ row.label }}</td>
                <td>{{ row.mean }}</td>
                <td>{{ row.median }}</td>
                <td>{{ row.dispersion }}</td>
                <td>{{ row.worst_origin_ts }}</td>
                <td>{{ row.worst_value }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="research-panel-section" v-if="originOverviewRows.length">
        <h5>Outer Origins</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>origin_ts</th>
                <th>joint_nll</th>
                <th>mean_utility</th>
                <th>net_return</th>
                <th>forecast_score_sequence</th>
                <th>test_block_sample_count</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in originOverviewRows" :key="row.origin_ts">
                <td>{{ row.origin_ts }}</td>
                <td>{{ row.joint_nll }}</td>
                <td>{{ row.mean_utility }}</td>
                <td>{{ row.net_return }}</td>
                <td>{{ row.forecast_score_sequence }}</td>
                <td>{{ row.test_block_sample_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>Diagnostics</h5>
        <p class="research-panel-desc">
          multivariate_rank_histogram / band_depth_rank_v1 / marginal_coverage / weighted_pit /
          prerank_diagnostics / price_reconstruction_diagnostics / weight_normalization / sequence_definitions
        </p>
        <div class="research-kv-grid">
          <article v-for="item in diagnosticCards" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
            <p class="research-kv-meta">{{ item.meta }}</p>
          </article>
        </div>
        <div v-if="diagnosticOriginRows.length" class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>origin_ts</th>
                <th>rank_scheme</th>
                <th>marginal_coverage</th>
                <th>weighted_pit</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in diagnosticOriginRows" :key="row.origin_ts">
                <td>{{ row.origin_ts }}</td>
                <td>{{ row.rank_scheme }}</td>
                <td>{{ row.marginal_coverage }}</td>
                <td>{{ row.weighted_pit }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="research-panel-section" v-if="nEffRows.length">
        <h5>n_eff_summary</h5>
        <div class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>origin_ts</th>
                <th>primary_validation_score_sequence</th>
                <th>label_r_close_sequence</th>
                <th>model_comparison_delta_sequence</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in nEffRows" :key="row.origin_ts">
                <td>{{ row.origin_ts }}</td>
                <td>{{ row.primary_validation_score_sequence }}</td>
                <td>{{ row.label_r_close_sequence }}</td>
                <td>{{ row.model_comparison_delta_sequence }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="research-panel-section" v-if="regimeSchema || regimeRows.length">
        <h5>Regime View</h5>
        <div class="research-kv-grid">
          <article class="research-kv-card">
            <span class="research-kv-label">regime_schema</span>
            <strong class="research-kv-value">{{ regimeDefinition }}</strong>
            <p class="research-kv-meta">{{ regimeFieldSummary }}</p>
          </article>
          <article class="research-kv-card">
            <span class="research-kv-label">regime_rows</span>
            <strong class="research-kv-value">{{ regimeRows.length }}</strong>
            <p class="research-kv-meta">当前表按全部 outer origin 展开，固定展示 weighted regime 汇总。</p>
          </article>
        </div>
        <div v-if="regimeRows.length" class="research-table-wrap">
          <table class="research-table">
            <thead>
              <tr>
                <th>origin_ts</th>
                <th>regime_key</th>
                <th>sample_count</th>
                <th>joint_nll_mean</th>
                <th>calibration_error</th>
                <th>sharpness_mean</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in regimeRows.slice(0, 12)" :key="`${row.origin_ts}:${row.regime_key}`">
                <td>{{ row.origin_ts }}</td>
                <td>{{ row.regime_key }}</td>
                <td>{{ row.sample_count }}</td>
                <td>{{ row.joint_nll_mean }}</td>
                <td>{{ row.calibration_error }}</td>
                <td>{{ row.sharpness_mean }}</td>
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

import {
  buildAggregateMetricRows,
  buildDiagnosticCards,
  buildDiagnosticOriginRows,
  buildNEffRows,
  buildOriginOverviewRows,
  buildRegimeRows,
  summarizeRegimeDefinition,
  summarizeRegimeFields,
} from './researchEvaluationSummaryModel.mjs';

const props = defineProps({
  artifacts: { type: Object, default: null },
  mode: { type: String, default: 'weighted' },
  regimeSchema: { type: Object, default: null },
});

const diagnosticArtifactKey = computed(() => (props.mode === 'unweighted' ? 'unweighted_diagnostics' : 'weighted_diagnostics'));
const diagnosticBundle = computed(() => props.artifacts?.[diagnosticArtifactKey.value] || null);
const forecastMetricRows = computed(() => buildAggregateMetricRows(props.artifacts?.forecast_metrics, ['joint_nll', 'energy_score', 'variogram_score']));
const decisionMetricRows = computed(() => buildAggregateMetricRows(props.artifacts?.decision_metrics, ['mean_utility', 'net_return', 'max_drawdown']));
const originOverviewRows = computed(() => buildOriginOverviewRows(props.artifacts));
const diagnosticCards = computed(() => buildDiagnosticCards(diagnosticBundle.value, diagnosticArtifactKey.value, props.artifacts?.n_eff_summary));
const diagnosticOriginRows = computed(() => buildDiagnosticOriginRows(diagnosticBundle.value, diagnosticArtifactKey.value));
const nEffRows = computed(() => buildNEffRows(props.artifacts?.n_eff_summary));
const regimeRows = computed(() => buildRegimeRows(props.artifacts?.regime_metrics));
const regimeDefinition = computed(() => summarizeRegimeDefinition(props.regimeSchema, props.artifacts?.regime_metrics));
const regimeFieldSummary = computed(() => summarizeRegimeFields(props.regimeSchema, props.artifacts?.regime_metrics));
</script>

<style scoped src="./trendResearchPanel.css"></style>
