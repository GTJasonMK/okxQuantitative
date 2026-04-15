<template>
  <section class="card trend-research-card">
    <div class="research-panel-header">
      <div>
        <h4>训练运行详情</h4>
        <p class="research-panel-desc">展示训练运行冻结下来的 split / evaluation / refit 协议字段。</p>
      </div>
    </div>
    <div v-if="!run" class="trend-subpage-placeholder empty-state trend-empty-info">
      <strong>尚未选择训练运行</strong>
      <p>选择一个 run 后，这里会展示 split_definition_version、evaluation_protocol_version 等冻结字段。</p>
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
      </section>

      <section class="research-panel-section">
        <h5>冻结训练协议</h5>
        <div class="research-kv-grid">
          <article v-for="item in protocolRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>Split Artifact</h5>
        <div class="research-kv-grid">
          <article v-for="item in splitRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="research-panel-section">
        <h5>Run 级决策参数（按 Origin 冻结）</h5>
        <div class="research-kv-grid">
          <article v-for="item in decisionParameterRows" :key="item.label" class="research-kv-card">
            <span class="research-kv-label">{{ item.label }}</span>
            <strong class="research-kv-value">{{ item.value }}</strong>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import { formatCompactNumber, formatDateTime } from '../../utils/formatting.js';

const props = defineProps({
  run: { type: Object, default: null },
  splitArtifact: { type: Object, default: null },
});

const identityRows = computed(() => ([
  { label: 'run_id', value: props.run?.run_id || '--' },
  { label: 'status', value: props.run?.status || '--' },
  { label: 'dataset_id', value: props.run?.dataset_id || '--' },
  { label: 'model_family', value: props.run?.model_family || '--' },
  { label: 'created_at', value: formatRunTime(props.run?.created_at) },
]));

const protocolRows = computed(() => ([
  { label: 'split_definition_version', value: props.run?.split_definition_version || '--' },
  { label: 'evaluation_protocol_version', value: props.run?.evaluation_protocol_version || '--' },
  { label: 'refit_policy_version', value: props.run?.refit_policy_version || '--' },
  { label: 'outer_origin_selection_policy', value: props.run?.outer_origin_selection_policy || '--' },
  { label: 'weighting_version', value: props.run?.weighting_version || '--' },
  { label: 'score_definition_version', value: props.run?.score_definition_version || '--' },
  { label: 'decision_utility_version', value: props.run?.decision_utility_version || '--' },
  { label: 'multiple_comparison_version', value: props.run?.multiple_comparison_version || '--' },
]));

const splitRows = computed(() => ([
  { label: 'split_artifact origins', value: formatCount(props.splitArtifact?.origins?.length) },
  { label: 'qualified_sample_count', value: formatCount(props.splitArtifact?.qualified_sample_count) },
  { label: 'outer_origin_selection_policy', value: props.splitArtifact?.outer_origin_selection_policy || '--' },
  { label: 'refit_policy_version', value: props.splitArtifact?.refit_policy_version || '--' },
]));

const decisionParameterRows = computed(() => {
  const artifacts = props.run?.artifacts;
  const policyBundle = artifacts?.policy_parameter_bundle;
  const utilityBundle = artifacts?.utility_parameter_bundle;
  const execBundle = artifacts?.execution_assumption_bundle;
  const originCount = policyBundle?.by_origin?.length;
  return [
    { label: 'policy_parameter_ref', value: props.run?.policy_parameter_ref || '--' },
    { label: 'utility_parameter_ref', value: props.run?.utility_parameter_ref || '--' },
    { label: 'execution_assumption_version', value: execBundle?.execution_assumption_version || props.run?.execution_assumption_version || '--' },
    { label: 'origin_count', value: originCount != null ? String(originCount) : '--' },
    { label: 'policy_definition_version', value: props.run?.policy_definition_version || '--' },
    { label: 'decision_utility_version', value: props.run?.decision_utility_version || '--' },
  ];
});

function formatCount(value) {
  return formatCompactNumber(value, { digits: 0, scientificDigits: 0, maxChars: 8 });
}

function formatRunTime(value) {
  const ts = Number(value);
  if (!Number.isFinite(ts) || ts <= 0) {
    return '--';
  }
  return formatDateTime(ts * 1000);
}
</script>

<style scoped src="./trendResearchPanel.css"></style>
