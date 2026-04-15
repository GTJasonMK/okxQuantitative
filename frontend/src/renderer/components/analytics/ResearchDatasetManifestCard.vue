<template>
  <section class="card trend-research-card">
    <div class="research-panel-header">
      <div>
        <h4>dataset_manifest</h4>
        <p class="research-panel-desc">冻结数据定义、split、weighting、evaluation 与 decision 协议。</p>
      </div>
      <div v-if="showActions" class="dataset-manifest-actions">
        <button
          type="button"
          class="trend-subnav-tab"
          :disabled="actionPending || !manifest?.dataset_id"
          @click="$emit('deleteDataset', manifest?.dataset_id || '')"
        >
          删除数据集
        </button>
      </div>
    </div>
    <p v-if="actionError" class="dataset-manifest-error">
      {{ actionError }}
    </p>
    <div v-if="!manifest" class="trend-subpage-placeholder empty-state trend-empty-info">
      <strong>尚未选择数据集</strong>
      <p>这里会展示 included_session_ids、integrity_policy 与整套冻结协议版本。</p>
    </div>
    <div v-else class="research-panel-stack">
      <section class="research-panel-section">
        <h5>身份与状态</h5>
        <div class="research-kv-grid">
          <article v-for="item in identityRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
        <div class="research-pill-row">
          <span
            v-for="sessionId in includedSessionIds"
            :key="sessionId"
            class="research-note-pill is-active"
          >
            {{ sessionId }}
          </span>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>数据与抽样协议</h5>
        <div class="research-kv-grid">
          <article v-for="item in dataProtocolRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>权重与 shift 诊断</h5>
        <div class="research-kv-grid">
          <article v-for="item in weightingRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>评估与决策协议</h5>
        <div class="research-kv-grid">
          <article v-for="item in evaluationRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>样本规模</h5>
        <div class="research-kv-grid">
          <article v-for="item in sampleRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>冻结对象</h5>
        <div class="research-json-grid">
          <article class="research-json-card">
            <span class="research-kv-label">integrity_policy</span>
            <pre class="research-json-block">{{ integrityPolicyText }}</pre>
          </article>
          <article class="research-json-card">
            <span class="research-kv-label">support_overlap_result / shift_diagnostic_result</span>
            <pre class="research-json-block">{{ shiftDiagnosticText }}</pre>
          </article>
          <article class="research-json-card">
            <span class="research-kv-label">sequence_definitions</span>
            <pre class="research-json-block">{{ sequenceDefinitionsText }}</pre>
          </article>
          <article class="research-json-card">
            <span class="research-kv-label">regime_schema</span>
            <pre class="research-json-block">{{ regimeSchemaText }}</pre>
          </article>
          <article class="research-json-card">
            <span class="research-kv-label">strata_fit_bundle</span>
            <pre class="research-json-block">{{ strataFitBundleText }}</pre>
          </article>
          <article class="research-json-card">
            <span class="research-kv-label">weight_fit_bundle</span>
            <pre class="research-json-block">{{ weightFitBundleText }}</pre>
          </article>
          <article class="research-json-card">
            <span class="research-kv-label">domain_classifier_fit_bundle</span>
            <pre class="research-json-block">{{ domainClassifierFitBundleText }}</pre>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import { formatCompactNumber } from '../../utils/formatting.js';

const props = defineProps({
  manifest: {
    type: Object,
    default: null,
  },
  preview: {
    type: Object,
    default: null,
  },
  actionPending: {
    type: Boolean,
    default: false,
  },
  actionError: {
    type: String,
    default: '',
  },
  showActions: {
    type: Boolean,
    default: true,
  },
});

defineEmits(['deleteDataset']);

const includedSessionIds = computed(() => props.manifest?.included_session_ids || []);
const identityRows = computed(() => ([
  { label: 'dataset_id', value: props.manifest?.dataset_id || '--' },
  { label: 'dataset_status', value: props.manifest?.dataset_status || '--' },
  { label: 'included_session_ids', value: includedSessionIds.value.join(' / ') || '--' },
  { label: 'protocol_validation_status', value: props.preview?.protocol_validation_status || '--' },
  { label: 'regime_schema', value: props.preview?.regime_schema?.definition_version || '--' },
]));
const dataProtocolRows = computed(() => buildRows([
  'feature_recipe_version',
  'label_definition_version',
  'integrity_policy_version',
  'deployment_target_version',
  'target_census_policy_version',
  'target_window_policy_version',
  'sampling_stride_sec',
  'split_definition_version',
  'outer_origin_selection_policy',
  'embargo_sec',
]));
const weightingRows = computed(() => buildRows([
  'weighting_version',
  'weight_definition',
  'weight_estimator_version',
  'shift_state_definition_version',
  'shift_diagnostic_version',
  'strata_definition_version',
  'strata_fit_ref',
  'weight_fit_ref',
  'domain_classifier_version',
  'domain_classifier_fit_ref',
  'support_overlap_result',
]));
const evaluationRows = computed(() => buildRows([
  'evaluation_protocol_version',
  'score_definition_version',
  'prerank_definition_version',
  'policy_definition_version',
  'policy_parameter_ref',
  'decision_utility_version',
  'utility_parameter_ref',
  'execution_assumption_version',
  'refit_policy_version',
  'multiple_comparison_version',
]));
const sampleRows = computed(() => ([
  { label: 'target_census_count', value: formatValue(props.manifest?.target_census_count) },
  { label: 'train_sample_count', value: formatValue(props.manifest?.train_sample_count) },
  { label: 'val_sample_count', value: formatValue(props.manifest?.val_sample_count) },
  { label: 'test_sample_count', value: formatValue(props.manifest?.test_sample_count) },
  { label: 'train_effective_sample_size', value: formatValue(props.manifest?.train_effective_sample_size) },
  { label: 'val_effective_sample_size', value: formatValue(props.manifest?.val_effective_sample_size) },
  { label: 'test_effective_sample_size', value: formatValue(props.manifest?.test_effective_sample_size) },
]));
const integrityPolicyText = computed(() => serializeValue(props.manifest?.integrity_policy));
const shiftDiagnosticText = computed(() => serializeValue(props.manifest?.shift_diagnostic_result));
const sequenceDefinitionsText = computed(() => serializeValue(props.preview?.n_eff_summary?.sequence_definitions));
const regimeSchemaText = computed(() => serializeValue(props.preview?.regime_schema));
const strataFitBundleText = computed(() => serializeValue(props.preview?.strata_fit_bundle));
const weightFitBundleText = computed(() => serializeValue(props.preview?.weight_fit_bundle));
const domainClassifierFitBundleText = computed(() => serializeValue(props.preview?.domain_classifier_fit_bundle));

function buildRows(fields) {
  return fields.map(field => ({
    label: field,
    value: formatValue(props.manifest?.[field]),
  }));
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') {
    return '--';
  }
  if (Array.isArray(value)) {
    return value.join(' / ') || '--';
  }
  if (typeof value === 'number') {
    return formatCompactNumber(value, { digits: 6, scientificDigits: 3, maxChars: 12 });
  }
  if (typeof value === 'object') {
    return serializeValue(value);
  }
  return String(value);
}

function serializeValue(value) {
  if (!value || (typeof value === 'object' && !Object.keys(value).length)) {
    return '--';
  }
  return JSON.stringify(value, null, 2);
}
</script>

<style scoped src="./trendResearchPanel.css"></style>

<style scoped>
.dataset-manifest-actions {
  margin-bottom: 12px;
}

.dataset-manifest-error {
  margin: 0 0 12px;
  color: #fecaca;
}
</style>
