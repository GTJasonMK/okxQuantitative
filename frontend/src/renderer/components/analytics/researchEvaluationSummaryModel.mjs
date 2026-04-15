import { formatCompactNumber, formatDateTime } from '../../utils/formatting.js';

const NUMBER_FORMAT = Object.freeze({
  digits: 6,
  scientificDigits: 3,
  maxChars: 12,
});

const PRIMARY_DIAGNOSTIC_DIMENSION = 'r_close';
const PREVIEW_COUNT = 4;
const EMPTY_VALUE = '--';

export const buildAggregateMetricRows = (bundle, fields = []) => {
  return fields.map((field) => buildAggregateMetricRow(bundle, field));
};

export const buildOriginOverviewRows = (artifacts = {}) => {
  const origins = artifacts?.rolling_origin_evaluation?.origins || [];
  return origins.map((origin) => ({
    origin_ts: formatOriginTs(origin?.origin_ts),
    joint_nll: formatMetric(origin?.forecast_metrics?.joint_nll),
    mean_utility: formatMetric(origin?.decision_metrics?.mean_utility),
    net_return: formatMetric(origin?.decision_metrics?.net_return),
    forecast_score_sequence: formatSequenceLength(origin?.forecast_score_sequence),
    test_block_sample_count: formatCount(origin?.split?.test_block_sample_count),
  }));
};

export const buildDiagnosticCards = (bundle, artifactKey, nEffSummary) => {
  const firstOrigin = getOriginArtifacts(bundle, artifactKey)[0] || null;
  const diagnostics = firstOrigin?.artifact || {};
  return [
    {
      label: 'multivariate_rank_histogram',
      value: diagnostics?.multivariate_rank_histogram?.rank_scheme || 'band_depth_rank_v1',
      meta: summarizeRankHistogram(bundle, artifactKey),
    },
    {
      label: 'marginal_coverage',
      value: summarizeDiagnosticField(bundle, artifactKey, 'marginal_coverage', 'coverage_rate'),
      meta: '按 across-origin 平均展示 coverage_rate',
    },
    {
      label: 'weighted_pit',
      value: summarizeDiagnosticField(bundle, artifactKey, 'weighted_pit', 'weighted_mean'),
      meta: '按 across-origin 平均展示 weighted_mean',
    },
    {
      label: 'prerank_diagnostics',
      value: diagnostics?.prerank_diagnostics?.definition_version || EMPTY_VALUE,
      meta: listObjectKeys(diagnostics?.prerank_diagnostics?.stats),
    },
    {
      label: 'price_reconstruction_diagnostics',
      value: formatCount(diagnostics?.price_reconstruction_diagnostics?.targets?.length),
      meta: listArrayItems(diagnostics?.price_reconstruction_diagnostics?.targets),
    },
    {
      label: 'weight_normalization',
      value: diagnostics?.weight_normalization?.formula || EMPTY_VALUE,
      meta: listArrayItems(diagnostics?.weight_normalization?.applies_to),
    },
    {
      label: 'n_eff_summary',
      value: listObjectKeys(getFirstOriginSequenceDefinitions(nEffSummary)),
      meta: '按 by_origin 展示每个 outer origin 的 n_eff',
    },
    {
      label: 'sequence_definitions',
      value: summarizeSequenceDefinitions(nEffSummary),
      meta: '来自第一条 outer origin 的 sequence_definitions',
    },
  ];
};

export const buildDiagnosticOriginRows = (bundle, artifactKey) => {
  return getOriginArtifacts(bundle, artifactKey).map(({ originTs, artifact }) => ({
    origin_ts: formatOriginTs(originTs),
    rank_scheme: artifact?.multivariate_rank_histogram?.rank_scheme || 'band_depth_rank_v1',
    marginal_coverage: formatMetric(
      artifact?.marginal_coverage?.stats?.[PRIMARY_DIAGNOSTIC_DIMENSION]?.coverage_rate,
    ),
    weighted_pit: formatMetric(
      artifact?.weighted_pit?.stats?.[PRIMARY_DIAGNOSTIC_DIMENSION]?.weighted_mean,
    ),
  }));
};

export const buildNEffRows = (bundle) => {
  return getOriginArtifacts(bundle, 'n_eff_summary').map(({ originTs, artifact }) => ({
    origin_ts: formatOriginTs(originTs),
    primary_validation_score_sequence: formatEstimate(
      artifact?.sequences?.primary_validation_score_sequence?.estimate,
    ),
    label_r_close_sequence: formatEstimate(
      artifact?.sequences?.label_r_close_sequence?.estimate,
    ),
    model_comparison_delta_sequence: formatEstimate(
      artifact?.sequences?.model_comparison_delta_sequence?.estimate,
    ),
  }));
};

export const buildRegimeRows = (bundle) => {
  return getOriginArtifacts(bundle, 'regime_metrics').flatMap(({ originTs, artifact }) => {
    const rows = artifact?.rows || [];
    return rows.map((row) => ({
      origin_ts: formatOriginTs(originTs),
      regime_key: String(row?.regime_key || EMPTY_VALUE),
      sample_count: formatCount(row?.sample_count),
      joint_nll_mean: formatMetric(row?.joint_nll_mean),
      calibration_error: formatMetric(row?.calibration_error),
      sharpness_mean: formatMetric(row?.sharpness_mean),
    }));
  });
};

export const summarizeRegimeDefinition = (regimeSchema, bundle) => {
  return regimeSchema?.definition_version
    || getOriginArtifacts(bundle, 'regime_metrics')[0]?.artifact?.schema?.definition_version
    || EMPTY_VALUE;
};

export const summarizeRegimeFields = (regimeSchema, bundle) => {
  const fields = regimeSchema?.required_fields
    || getOriginArtifacts(bundle, 'regime_metrics')[0]?.artifact?.schema?.required_fields;
  return listArrayItems(fields);
};

function buildAggregateMetricRow(bundle, field) {
  const metric = bundle?.[field] || {};
  return {
    label: field,
    mean: formatMetric(metric?.mean),
    median: formatMetric(metric?.median),
    dispersion: formatMetric(metric?.dispersion),
    worst_origin_ts: formatOriginTs(metric?.worst_origin_ts),
    worst_value: formatMetric(metric?.worst_value),
  };
}

function summarizeRankHistogram(bundle, artifactKey) {
  const firstOrigin = getOriginArtifacts(bundle, artifactKey)[0];
  if (!firstOrigin) {
    return EMPTY_VALUE;
  }
  const bins = firstOrigin.artifact?.multivariate_rank_histogram?.bin_counts || [];
  const preview = bins
    .slice(0, PREVIEW_COUNT)
    .map((value, index) => `${index}:${formatMetric(value)}`)
    .join(' | ');
  return preview || EMPTY_VALUE;
}

function summarizeDiagnosticField(bundle, artifactKey, sectionName, metricField) {
  const aggregates = new Map();
  getOriginArtifacts(bundle, artifactKey).forEach(({ artifact }) => {
    const stats = artifact?.[sectionName]?.stats || {};
    Object.entries(stats).forEach(([dimension, row]) => {
      const current = aggregates.get(dimension) || [];
      current.push(Number(row?.[metricField]));
      aggregates.set(dimension, current);
    });
  });
  const preview = [...aggregates.entries()]
    .slice(0, PREVIEW_COUNT)
    .map(([dimension, values]) => `${dimension}:${formatMetric(mean(values))}`)
    .join(' | ');
  return preview || EMPTY_VALUE;
}

function summarizeSequenceDefinitions(bundle) {
  const sequences = getFirstOriginSequenceDefinitions(bundle);
  const preview = Object.entries(sequences)
    .slice(0, PREVIEW_COUNT)
    .map(([key, value]) => `${key}:${value?.sequence_role || value?.field_name || 'sequence'}`)
    .join(' | ');
  return preview || EMPTY_VALUE;
}

function getFirstOriginSequenceDefinitions(bundle) {
  return getOriginArtifacts(bundle, 'n_eff_summary')[0]?.artifact?.sequences || {};
}

function getOriginArtifacts(bundle, artifactKey) {
  const rows = bundle?.by_origin || [];
  return rows.map((row) => ({
    originTs: row?.origin_ts,
    artifact: row?.[artifactKey] || null,
  }));
}

function formatMetric(value) {
  return formatCompactNumber(value, NUMBER_FORMAT);
}

function formatEstimate(value) {
  return formatMetric(value);
}

function formatCount(value) {
  const count = Number(value);
  if (!Number.isFinite(count)) {
    return EMPTY_VALUE;
  }
  return String(Math.trunc(count));
}

function formatSequenceLength(sequence) {
  return Array.isArray(sequence) ? String(sequence.length) : EMPTY_VALUE;
}

function formatOriginTs(value) {
  const ts = Number(value);
  if (!Number.isFinite(ts) || ts <= 0) {
    return EMPTY_VALUE;
  }
  return formatDateTime(ts * 1000);
}

function listArrayItems(items) {
  return Array.isArray(items) && items.length ? items.join(' / ') : EMPTY_VALUE;
}

function listObjectKeys(value) {
  const keys = Object.keys(value || {});
  return keys.length ? keys.join(' / ') : EMPTY_VALUE;
}

function mean(values) {
  if (!values.length) {
    return Number.NaN;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
