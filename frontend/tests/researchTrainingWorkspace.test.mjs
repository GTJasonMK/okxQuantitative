import test from 'node:test';
import assert from 'node:assert/strict';

import { useResearchTrainingWorkspace } from '../src/renderer/components/analytics/useResearchTrainingWorkspace.mjs';
import { buildTrainingCreatePayload } from '../src/renderer/components/analytics/researchPlatformDefaults.mjs';

test('useResearchTrainingWorkspace exposes weighted toggle and baseline data', () => {
  const workspace = useResearchTrainingWorkspace();
  assert.ok('collectionSessions' in workspace);
  assert.ok('selectedSessionIds' in workspace);
  assert.ok('datasets' in workspace);
  assert.ok('trainingRuns' in workspace);
  assert.ok('selectedDatasetManifest' in workspace);
  assert.ok('selectedRunDetail' in workspace);
  assert.ok('selectedRunArtifacts' in workspace);
  assert.ok('selectedSplitArtifact' in workspace);
  assert.ok('selectedRegimeSchema' in workspace);
  assert.ok('selectedDatasetPreview' in workspace);
  assert.ok('diagnosticsMode' in workspace);
  assert.ok('comparisonResult' in workspace);
  assert.ok('baselineResult' in workspace);
  assert.ok('datasetActionPending' in workspace);
  assert.ok('datasetActionError' in workspace);
  assert.ok('datasetCreatePending' in workspace);
  assert.ok('datasetCreateError' in workspace);
  assert.ok('trainingActionPending' in workspace);
  assert.ok('trainingActionError' in workspace);
  assert.ok('realtimeError' in workspace);
  assert.equal(typeof workspace.loadCollectionSessions, 'function');
  assert.equal(typeof workspace.createDatasetManifest, 'function');
  assert.equal(typeof workspace.startTrainingRun, 'function');
  assert.equal(typeof workspace.deleteDatasetManifest, 'function');
});

test('buildTrainingCreatePayload defaults to an allowed joint challenger family', () => {
  const payload = buildTrainingCreatePayload('dataset-1');

  assert.equal(payload.model_family, 'joint_density_model_v1');
  assert.equal(payload.model_spec_ref, 'model://joint_density_model_v1/default-v1');
});

test('workspace creates dataset manifest from selected data-center sessions and refreshes selection', async () => {
  const calls = [];
  const workspace = useResearchTrainingWorkspace({
    api: {
      async getDataCenterCollectionSessions() {
        calls.push('sessions');
        return {
          sessions: [
            { session_id: 'sess-1', inst_id: 'BTC-USDT-SWAP', status: 'finished' },
            { session_id: 'sess-2', inst_id: 'BTC-USDT-SWAP', status: 'stopped' },
          ],
        };
      },
      async createResearchPlatformDataset(payload) {
        calls.push(`create:${payload.included_session_ids.join(',')}`);
        return {
          dataset: {
            dataset_id: 'dataset-1',
          },
        };
      },
      async getResearchPlatformDatasets() {
        calls.push('datasets');
        return {
          datasets: [{ dataset_id: 'dataset-1' }],
        };
      },
      async getResearchPlatformDatasetDetail(datasetId) {
        calls.push(`detail:${datasetId}`);
        return {
          dataset: { dataset_id: datasetId },
        };
      },
      async getResearchPlatformDatasetPreview(datasetId) {
        calls.push(`preview:${datasetId}`);
        return {
          preview: { manifest: { dataset_id: datasetId } },
        };
      },
      async getResearchPlatformTrainingRuns(params = {}) {
        calls.push(`runs:${params.dataset_id || ''}`);
        return { training_runs: [] };
      },
    },
  });

  await workspace.loadCollectionSessions();
  workspace.selectedSessionIds.value = ['sess-1', 'sess-2'];
  await workspace.createDatasetManifest();

  assert.deepEqual(workspace.collectionSessions.value.map(item => item.session_id), ['sess-1', 'sess-2']);
  assert.equal(workspace.selectedDatasetId.value, 'dataset-1');
  assert.equal(workspace.selectedDatasetManifest.value.dataset_id, 'dataset-1');
  assert.deepEqual(calls, [
    'sessions',
    'create:sess-1,sess-2',
    'datasets',
    'detail:dataset-1',
    'preview:dataset-1',
    'runs:dataset-1',
  ]);
});

test('workspace starts a training run and selects the created run', async () => {
  const calls = [];
  const workspace = useResearchTrainingWorkspace({
    api: {
      async createResearchPlatformTrainingRun(payload) {
        calls.push(`create-run:${payload.dataset_id}:${payload.model_family}`);
        return {
          training_run: {
            run_id: 'run-1',
          },
        };
      },
      async getResearchPlatformTrainingRuns(params = {}) {
        calls.push(`runs:${params.dataset_id || ''}`);
        return {
          training_runs: [{ run_id: 'run-1', dataset_id: params.dataset_id || 'dataset-1' }],
        };
      },
      async getResearchPlatformTrainingRun(runId) {
        calls.push(`run:${runId}`);
        return {
          training_run: {
            run_id: runId,
            status: 'queued',
            artifacts: {
              split_artifact: { origins: [] },
              baseline_result: { baselines: [{ baseline_id: 'unconditional_distribution_baseline' }] },
              comparison_result: { best_candidate_id: 'joint_density_model_v1' },
            },
          },
        };
      },
    },
  });

  workspace.selectedDatasetId.value = 'dataset-1';
  await workspace.startTrainingRun({
    dataset_id: 'dataset-1',
    candidate_set_ref: 'candidate://locked/default-v1',
    model_family: 'joint_density_model_v1',
    model_spec_ref: 'model://joint_density_model_v1/default-v1',
    training_seed: 7,
  });

  assert.equal(workspace.selectedRunId.value, 'run-1');
  assert.equal(workspace.selectedRunDetail.value.run_id, 'run-1');
  assert.equal(workspace.comparisonResult.value.best_candidate_id, 'joint_density_model_v1');
  assert.equal(workspace.baselineResult.value.baselines[0].baseline_id, 'unconditional_distribution_baseline');
  assert.deepEqual(calls, [
    'create-run:dataset-1:joint_density_model_v1',
    'runs:dataset-1',
    'run:run-1',
  ]);
});

test('workspace deletes dataset manifest and refreshes selection', async () => {
  const calls = [];
  const workspace = useResearchTrainingWorkspace({
    api: {
      async deleteResearchPlatformDataset(datasetId) {
        calls.push(`delete:${datasetId}`);
        return {
          deleted_dataset: {
            dataset_id: datasetId,
            deleted_dataset_count: 1,
          },
        };
      },
      async getResearchPlatformDatasets() {
        calls.push('datasets');
        return {
          datasets: [
            { dataset_id: 'dataset-2' },
          ],
        };
      },
      async getResearchPlatformDatasetDetail(datasetId) {
        calls.push(`detail:${datasetId}`);
        return {
          dataset: {
            dataset_id: datasetId,
          },
        };
      },
      async getResearchPlatformDatasetPreview(datasetId) {
        calls.push(`preview:${datasetId}`);
        return {
          preview: {
            manifest: {
              dataset_id: datasetId,
            },
          },
        };
      },
      async getResearchPlatformTrainingRuns(params = {}) {
        calls.push(`runs:${params.dataset_id || ''}`);
        return { training_runs: [] };
      },
    },
  });

  workspace.selectedDatasetId.value = 'dataset-1';
  await workspace.deleteDatasetManifest('dataset-1');

  assert.equal(workspace.selectedDatasetId.value, 'dataset-2');
  assert.equal(workspace.selectedDatasetManifest.value.dataset_id, 'dataset-2');
  assert.deepEqual(calls, [
    'delete:dataset-1',
    'datasets',
    'detail:dataset-2',
    'preview:dataset-2',
    'runs:dataset-2',
  ]);
});

test('workspace surfaces blocking training runs when dataset deletion is rejected', async () => {
  const workspace = useResearchTrainingWorkspace({
    api: {
      async deleteResearchPlatformDataset() {
        const error = new Error('request failed');
        error.response = {
          data: {
            detail: {
              message: 'delete referenced training runs first',
              blocking_training_run_ids: ['run-1'],
            },
          },
        };
        throw error;
      },
    },
  });

  await workspace.deleteDatasetManifest('dataset-1');

  assert.equal(
    workspace.datasetActionError.value,
    'delete referenced training runs first：run-1',
  );
});

test('workspace exposes realtime connection errors to UI state', async () => {
  const workspace = useResearchTrainingWorkspace({
    realtime: {
      async connect() {
        throw new Error('research ws failed');
      },
      subscribeResearchPlatform() {},
      unsubscribeResearchPlatform() {},
      addConnectionListener() {},
      removeConnectionListener() {},
    },
  });

  workspace.attachRealtime();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(workspace.realtimeError.value, 'research ws failed');
});
