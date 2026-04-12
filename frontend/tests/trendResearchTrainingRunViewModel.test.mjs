import test from 'node:test';
import assert from 'node:assert/strict';

import { buildTrendTrainingRunPanelModel } from '../src/renderer/components/analytics/trendResearchTrainingRunViewModel.mjs';

test('buildTrendTrainingRunPanelModel maps running training snapshots', () => {
  const model = buildTrendTrainingRunPanelModel({
    trainingRun: {
      status: 'running',
      current_stage: 'train_epochs',
      progress_pct: 52,
      run_id: 'run-1',
      message: 'Epoch 8 / 20',
      started_at: 1712365200,
      stages: [
        { stage: 'queued', status: 'completed', duration_seconds: 0.1, started_at: 1712365200, finished_at: 1712365200.1, stats: {} },
        { stage: 'collect_bars', status: 'completed', duration_seconds: 1.4, started_at: 1712365200.2, finished_at: 1712365201.6, stats: { eligible_inst_count: 3, whitelist_count: 5 } },
        { stage: 'train_epochs', status: 'running', duration_seconds: null, started_at: 1712365202, stats: { current_epoch: 2, total_epochs: 20, latest_train_loss: 0.77, latest_validation_loss: 0.86 } },
      ],
      epoch_history: [
        { epoch: 1, total_epochs: 20, train_loss: 0.84, validation_loss: 0.91 },
        { epoch: 2, total_epochs: 20, train_loss: 0.77, validation_loss: 0.86 },
      ],
    },
    modelStatus: {
      validationCards: [{ label: '联合命中', value: '42.0%' }],
    },
  });

  assert.equal(model.statusLabel, '训练中');
  assert.equal(model.progressLabel, '52%');
  assert.equal(model.runIdLabel, 'run-1');
  assert.equal(model.disableStart, true);
  assert.equal(model.stageRows[1].stats[0].value, '3 / 5');
  assert.equal(model.summaryCards.length > 0, true);
  assert.equal(model.currentStageCard.label, 'Epoch 训练');
  assert.equal(model.currentStageCard.stats[0].value, '2 / 20');
  assert.equal(model.stageRows[2].isCurrent, true);
  assert.equal(model.stageRows[2].statusLabel, '训练中');
  assert.notEqual(model.stageRows[1].startedAtLabel, '--');
  assert.equal(model.metricCards[0].value, '42.0%');
  assert.equal(model.curveGroups[0].series[0].data.length, 2);
});

test('buildTrendTrainingRunPanelModel keeps idle state actionable', () => {
  const model = buildTrendTrainingRunPanelModel();

  assert.equal(model.statusLabel, '空闲');
  assert.equal(model.disableStart, false);
  assert.equal(model.currentStageCard.label, '等待启动');
  assert.equal(model.metricCards.length, 0);
});
