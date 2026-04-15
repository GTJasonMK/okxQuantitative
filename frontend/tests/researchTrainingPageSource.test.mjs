import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

test('DatasetBuildingPage renders dataset build controls and manifest panels', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/DatasetBuildingPage.vue', import.meta.url), 'utf8');
  assert.match(source, /ResearchDatasetBuilder/);
  assert.match(source, /ResearchDatasetList/);
  assert.match(source, /ResearchDatasetManifestCard/);
  assert.match(source, /create-dataset/);
  assert.match(source, /delete-dataset/);
});

test('ModelTrainingPage renders run detail and evaluation panels', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ModelTrainingPage.vue', import.meta.url), 'utf8');
  assert.match(source, /ResearchTrainingControlCard/);
  assert.match(source, /ResearchDatasetList/);
  assert.match(source, /ResearchDatasetManifestCard/);
  assert.match(source, /ResearchTrainingRunList/);
  assert.match(source, /ResearchTrainingRunDetail/);
  assert.match(source, /ResearchEvaluationSummary/);
  assert.match(source, /ResearchDiagnosticsToggle/);
  assert.match(source, /ResearchBootstrapPanel/);
  assert.match(source, /ResearchBaselineComparison/);
  assert.match(source, /冻结协议/);
});

test('ResearchEvaluationSummary exposes joint calibration and reconstruction diagnostics', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchEvaluationSummary.vue', import.meta.url), 'utf8');
  assert.match(source, /joint_nll/);
  assert.match(source, /energy_score/);
  assert.match(source, /variogram_score/);
  assert.match(source, /median/);
  assert.match(source, /dispersion/);
  assert.match(source, /worst_origin_ts/);
  assert.match(source, /mean_utility/);
  assert.match(source, /net_return/);
  assert.match(source, /max_drawdown/);
  assert.match(source, /multivariate_rank_histogram/);
  assert.match(source, /band_depth_rank_v1/);
  assert.match(source, /marginal_coverage/);
  assert.match(source, /weighted_pit/);
  assert.match(source, /prerank_diagnostics/);
  assert.match(source, /price_reconstruction_diagnostics/);
  assert.match(source, /weight_normalization/);
  assert.match(source, /n_eff_summary/);
  assert.match(source, /calibration_error/);
  assert.match(source, /sharpness_mean/);
  assert.match(source, /by_origin/);
  assert.match(source, /sequence_definitions/);
  assert.match(source, /weighted = 目标总体口径/);
  assert.match(source, /unweighted = 当前验证集经验分布口径/);
});

test('ResearchDatasetManifestCard exposes frozen manifest fields', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchDatasetManifestCard.vue', import.meta.url), 'utf8');
  assert.match(source, /删除数据集/);
  assert.match(source, /included_session_ids/);
  assert.match(source, /feature_recipe_version/);
  assert.match(source, /label_definition_version/);
  assert.match(source, /integrity_policy_version/);
  assert.match(source, /integrity_policy/);
  assert.match(source, /deployment_target_version/);
  assert.match(source, /target_window_policy_version/);
  assert.match(source, /split_definition_version/);
  assert.match(source, /embargo_sec/);
  assert.match(source, /weighting_version/);
  assert.match(source, /shift_state_definition_version/);
  assert.match(source, /weight_fit_ref/);
  assert.match(source, /domain_classifier_fit_ref/);
  assert.match(source, /score_definition_version/);
  assert.match(source, /policy_definition_version/);
  assert.match(source, /decision_utility_version/);
  assert.match(source, /execution_assumption_version/);
  assert.match(source, /multiple_comparison_version/);
  assert.match(source, /outer_origin_selection_policy/);
  assert.match(source, /support_overlap_result/);
  assert.match(source, /target_census_count/);
  assert.match(source, /train_sample_count/);
  assert.match(source, /val_sample_count/);
  assert.match(source, /test_sample_count/);
  assert.match(source, /train_effective_sample_size/);
  assert.match(source, /regime_schema/);
  assert.match(source, /protocol_validation_status/);
  assert.match(source, /strata_fit_bundle/);
  assert.match(source, /weight_fit_bundle/);
  assert.match(source, /domain_classifier_fit_bundle/);
});

test('ResearchTrainingRunDetail exposes frozen training protocol fields', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchTrainingRunDetail.vue', import.meta.url), 'utf8');
  assert.match(source, /outer_origin_selection_policy/);
  assert.match(source, /split_definition_version/);
  assert.match(source, /evaluation_protocol_version/);
  assert.match(source, /refit_policy_version/);
});

test('ResearchBaselineComparison exposes retained model set and candidate ranking', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchBaselineComparison.vue', import.meta.url), 'utf8');
  assert.match(source, /retained_model_set/);
  assert.match(source, /candidate_ranking/);
  assert.match(source, /pairwise_results/);
  assert.match(source, /best_candidate_id/);
  assert.match(source, /candidate_set_ref/);
});

test('ResearchBootstrapPanel exposes joint_nll and mean_utility block bootstrap summaries', async () => {
  const source = await fs.readFile(new URL('../src/renderer/components/analytics/ResearchBootstrapPanel.vue', import.meta.url), 'utf8');
  assert.match(source, /joint_nll/);
  assert.match(source, /mean_utility/);
  assert.match(source, /ci_95/);
});
