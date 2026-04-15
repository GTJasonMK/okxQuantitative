import test from 'node:test';
import assert from 'node:assert/strict';

import { buildTrendProgressDashboardModel } from '../src/renderer/components/analytics/trendProgressDashboardViewModel.mjs';

test('buildTrendProgressDashboardModel builds the progress dashboard around the current bottleneck', () => {
  const model = buildTrendProgressDashboardModel({
    processSummary: {
      whitelist_count: 3,
      inference_ready_count: 1,
    },
    processInstrument: {
      instId: 'BTC-USDT-SWAP',
      pipelineState: 'waiting_book',
      displayState: '等待盘口',
      stages: [
        { key: 'trade', ready: true, label: '逐笔成交已到达' },
        { key: 'book', ready: false, label: '等待盘口' },
        { key: 'state', ready: false, label: '等待合约状态同步' },
        { key: 'feature', ready: false, label: '等待生成 1 秒特征条' },
        { key: 'inference', ready: false, label: '等待推断输出' },
      ],
    },
    diagnosticsState: {
      selectedInstId: 'BTC-USDT-SWAP',
      globalHealth: {
        whitelist_count: 3,
        active_count: 1,
        stale_count: 1,
        error_count: 1,
      },
      instrumentHealth: {
        pipeline_stage: 'waiting_book',
        trade_age_seconds: 0.2,
        book_age_seconds: 18.4,
        state_age_seconds: 30.5,
        last_feature_at: 1712365200,
        last_inference_at: 1712365190,
        last_event_at: 1712365300,
        is_stale: true,
        is_error: false,
        current_error: '',
      },
      details: {
        subscription_state: 'subscribed',
        pending_trade_count: 3,
        last_feature_bucket: 1712365200,
        last_inference_bucket: 1712365190,
        last_error_at: null,
      },
      timeline: Array.from({ length: 10 }, (_, index) => ({
        sequence: index + 1,
        kind: index % 2 === 0 ? 'trade' : 'book',
        label: `事件 ${index + 1}`,
        emitted_at: 1712365200 + index,
      })),
    },
  });

  assert.deepEqual(
    model.overviewItems.map((item) => item.label),
    ['白名单', '推断完成', '处理中', '停滞', '异常'],
  );
  assert.equal(model.overviewItems[1].value, '1');
  assert.equal(model.overviewItems[2].value, '0');
  assert.match(model.conclusion.title, /当前停在 Book/);
  assert.match(model.conclusion.message, /18\.4s/);
  assert.equal(model.pipelineSteps[0].statusLabel, '已完成');
  assert.equal(model.pipelineSteps[1].statusLabel, '当前阻塞');
  assert.equal(model.pipelineSteps[1].isCurrent, true);
  assert.equal(model.pipelineSteps[2].statusLabel, '未到达');
  assert.equal(model.evidenceCards[0].label, '当前阻塞原因');
  assert.equal(model.evidenceCards[1].items[1].label, '最近 Book');
  assert.equal(model.evidenceCards[2].items[1].label, '最近 Inference');
  assert.equal(model.timelineItems.length, 8);
});

test('buildTrendProgressDashboardModel explains a healthy feature-ready pipeline without warning language', () => {
  const model = buildTrendProgressDashboardModel({
    processSummary: {
      whitelist_count: 2,
      inference_ready_count: 0,
    },
    processInstrument: {
      instId: 'ETH-USDT-SWAP',
      pipelineState: 'feature_ready',
      displayState: '特征已生成',
      stages: [
        { key: 'trade', ready: true, label: '逐笔成交已到达' },
        { key: 'book', ready: true, label: '盘口已到达' },
        { key: 'state', ready: true, label: '合约状态已同步' },
        { key: 'feature', ready: true, label: '最近 1 秒特征条已生成' },
        { key: 'inference', ready: false, label: '等待推断输出' },
      ],
    },
    diagnosticsState: {
      selectedInstId: 'ETH-USDT-SWAP',
      globalHealth: {
        whitelist_count: 2,
        active_count: 2,
        stale_count: 0,
        error_count: 0,
      },
      instrumentHealth: {
        pipeline_stage: 'feature_ready',
        trade_age_seconds: 0.4,
        book_age_seconds: 0.4,
        state_age_seconds: 1.2,
        last_feature_at: 1712366200,
        last_inference_at: null,
        last_event_at: 1712366201,
        is_stale: false,
        is_error: false,
        current_error: '',
      },
      details: {
        subscription_state: 'subscribed',
        pending_trade_count: 0,
      },
      timeline: [],
    },
  });

  assert.match(model.conclusion.title, /已完成 Feature/);
  assert.match(model.conclusion.message, /等待下一次 Inference/);
  assert.equal(model.pipelineSteps[3].statusLabel, '已完成');
  assert.equal(model.pipelineSteps[4].isCurrent, true);
  assert.equal(model.pipelineSteps[4].statusLabel, '未到达');
  assert.equal(model.evidenceCards[0].items[0].value, '当前没有异常，流程仍在推进。');
});
