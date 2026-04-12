import {
  formatCompactNumber,
  formatDateTime,
  formatPercentValue,
} from '../../utils/formatting.js';

const STAGE_ORDER = Object.freeze([
  'queued',
  'collect_bars',
  'resolve_shared_features',
  'build_samples',
  'split_dataset',
  'train_epochs',
  'evaluate_validation',
  'save_bundle',
  'activate_model',
]);

const STAGE_META = Object.freeze({
  queued: { label: '排队', description: '等待启动本轮分析与训练运行。' },
  collect_bars: { label: '数据收集', description: '从本地特征条中筛选满足训练要求的永续合约。' },
  resolve_shared_features: { label: '共享因子解析', description: '求交集得到所有合约都可用的因子集合。' },
  build_samples: { label: '样本构建', description: '按窗口切片构造序列样本与顶底点目标。' },
  split_dataset: { label: '数据切分', description: '按时间顺序拆分训练、验证、测试集合。' },
  train_epochs: { label: 'Epoch 训练', description: '执行多轮训练并实时更新损失曲线。' },
  evaluate_validation: { label: '验证评估', description: '汇总验证指标，确认模型是否具备上线价值。' },
  save_bundle: { label: '模型保存', description: '把本轮训练得到的模型与配置写入持久化存储。' },
  activate_model: { label: '模型激活', description: '将新模型切换到实时推断链路。' },
});

const STATUS_LABELS = Object.freeze({
  pending: '等待中',
  running: '训练中',
  failed: '失败',
  completed: '已完成',
  queued: '排队',
});

const NUMBER_OPTIONS = Object.freeze({
  digits: 3,
  maxChars: 10,
  scientificDigits: 2,
});

const formatDuration = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)}s` : '--';
};

const formatTimestamp = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0
    ? formatDateTime(numeric * 1000)
    : '--';
};

const resolveStatusLabel = (status) => STATUS_LABELS[status] || '空闲';

const formatValue = (value) => {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return formatCompactNumber(numeric, NUMBER_OPTIONS);
  }
  return String(value ?? '--');
};

const buildStat = (key, label, value) => ({
  key,
  label,
  value,
});

const formatStageStats = (stage, stats = {}) => {
  if (stage === 'collect_bars') {
    return [
      buildStat(
        'eligible_inst_count',
        '合格合约',
        `${Number(stats.eligible_inst_count || 0)} / ${Number(stats.whitelist_count || 0)}`,
      ),
    ];
  }
  if (stage === 'resolve_shared_features') {
    return [buildStat('shared_feature_count', '共享因子', formatValue(stats.shared_feature_count))];
  }
  if (stage === 'build_samples') {
    return [buildStat('sample_count', '样本数', formatValue(stats.sample_count))];
  }
  if (stage === 'split_dataset') {
    return [
      buildStat('train_count', '训练集', formatValue(stats.train_count)),
      buildStat('validation_count', '验证集', formatValue(stats.validation_count)),
      buildStat('test_count', '测试集', formatValue(stats.test_count)),
    ];
  }
  if (stage === 'train_epochs') {
    return [
      buildStat(
        'current_epoch',
        '当前 Epoch',
        `${Number(stats.current_epoch || 0)} / ${Number(stats.total_epochs || 0)}`,
      ),
      buildStat('latest_train_loss', 'Train Loss', formatValue(stats.latest_train_loss)),
      buildStat('latest_validation_loss', 'Validation Loss', formatValue(stats.latest_validation_loss)),
    ];
  }
  if (stage === 'evaluate_validation') {
    return [
      buildStat('joint_hit_rate', '联合命中', formatPercentValue(Number(stats.joint_hit_rate || 0) * 100, 2)),
      buildStat('top_time_mae_minutes', '顶部时间 MAE', formatValue(stats.top_time_mae_minutes)),
      buildStat('bottom_time_mae_minutes', '底部时间 MAE', formatValue(stats.bottom_time_mae_minutes)),
    ];
  }
  if (stage === 'save_bundle' || stage === 'activate_model') {
    return [
      buildStat('selected_feature_count', '入模因子', formatValue(stats.selected_feature_count)),
    ];
  }
  return Object.entries(stats).map(([key, value]) => buildStat(key, key, formatValue(value)));
};

const buildCurveGroups = (history = []) => [
  {
    key: 'loss',
    label: '训练曲线',
    caption: 'Train / Validation Loss 按 epoch 更新。',
    hasLeftAxis: false,
    hasData: history.length > 0,
    series: [
      {
        factorName: 'train_loss',
        label: 'Train Loss',
        color: '#22C55E',
        axis: 'right',
        data: history.map((row) => ({ time: row.epoch, value: row.train_loss })),
      },
      {
        factorName: 'validation_loss',
        label: 'Validation Loss',
        color: '#F97316',
        axis: 'right',
        data: history.map((row) => ({ time: row.epoch, value: row.validation_loss })),
      },
    ],
  },
];

const buildStageRows = (run = {}) => {
  const stages = Array.isArray(run.stages) ? run.stages : [];
  return stages.map((stage) => {
    const meta = STAGE_META[stage.stage] || { label: stage.stage, description: '' };
    return {
      key: stage.stage,
      label: meta.label,
      description: meta.description,
      status: stage.status,
      statusLabel: resolveStatusLabel(stage.status),
      isCurrent: stage.stage === run.current_stage,
      durationLabel: formatDuration(stage.duration_seconds),
      startedAtLabel: formatTimestamp(stage.started_at),
      finishedAtLabel: formatTimestamp(stage.finished_at),
      message: stage.message || '',
      stats: formatStageStats(stage.stage, stage.stats || {}),
    };
  });
};

const resolveCurrentStageCard = (run, stageRows) => {
  const currentStage = stageRows.find((row) => row.isCurrent)
    || stageRows.find((row) => row.status === 'running')
    || stageRows.findLast((row) => row.status === 'completed')
    || null;
  if (!currentStage) {
    return {
      label: '等待启动',
      description: '尚未开始新的分析与训练运行。',
      statusLabel: resolveStatusLabel(run.status || ''),
      message: run.message || '点击“开始重训”后即可观察整个分析链路。',
      startedAtLabel: '--',
      finishedAtLabel: '--',
      durationLabel: '--',
      stats: [],
    };
  }
  return {
    label: currentStage.label,
    description: currentStage.description,
    statusLabel: currentStage.statusLabel,
    message: currentStage.message || currentStage.description,
    startedAtLabel: currentStage.startedAtLabel,
    finishedAtLabel: currentStage.finishedAtLabel,
    durationLabel: currentStage.durationLabel,
    stats: currentStage.stats,
  };
};

const buildSummaryCards = (run, stageRows, currentStageCard, progressLabel) => {
  const completedStageCount = stageRows.filter((row) => row.status === 'completed').length;
  return [
    buildStat('status', '运行状态', resolveStatusLabel(String(run.status || ''))),
    buildStat('current_stage', '当前阶段', currentStageCard.label),
    buildStat('progress', '总进度', progressLabel),
    buildStat(
      'stage_coverage',
      '阶段完成',
      `${completedStageCount} / ${stageRows.length || STAGE_ORDER.length}`,
    ),
  ];
};

const buildMetricCards = (modelStatus, run) => {
  if (Array.isArray(modelStatus?.validationCards) && modelStatus.validationCards.length > 0) {
    return modelStatus.validationCards;
  }
  const validationStage = (run.stages || []).find((stage) => stage.stage === 'evaluate_validation');
  if (!validationStage || !validationStage.stats || Object.keys(validationStage.stats).length === 0) {
    return [];
  }
  return formatStageStats('evaluate_validation', validationStage?.stats || {}).filter((item) => item.value !== '--');
};

export const buildTrendTrainingRunPanelModel = ({
  trainingRun = null,
  modelStatus = null,
} = {}) => {
  const run = trainingRun || {};
  const history = Array.isArray(run.epoch_history) ? run.epoch_history : [];
  const progressLabel = `${Math.round(Number(run.progress_pct || 0))}%`;
  const stageRows = buildStageRows(run);
  const currentStageCard = resolveCurrentStageCard(run, stageRows);
  return {
    statusLabel: resolveStatusLabel(String(run.status || '')),
    progressLabel,
    runIdLabel: run.run_id || '--',
    message: run.message || '暂无训练任务',
    disableStart: run.status === 'queued' || run.status === 'running',
    startedAtLabel: formatTimestamp(run.started_at),
    finishedAtLabel: formatTimestamp(run.finished_at),
    durationLabel: formatDuration(run.duration_seconds),
    errorMessage: run.error_message || '',
    summaryCards: buildSummaryCards(run, stageRows, currentStageCard, progressLabel),
    currentStageCard,
    stageRows,
    metricCards: buildMetricCards(modelStatus, run),
    curveGroups: buildCurveGroups(history),
  };
};
