import test from 'node:test';
import assert from 'node:assert/strict';

import { useDataCollectionWorkspace } from '../src/renderer/views/useDataCollectionWorkspace.mjs';

test('useDataCollectionWorkspace exposes collection actions and progress state', () => {
  const workspace = useDataCollectionWorkspace();
  assert.ok('sessions' in workspace);
  assert.ok('activeSession' in workspace);
  assert.ok('sessionCharts' in workspace);
  assert.ok('sessionCoverage' in workspace);
  assert.ok('sessionProgress' in workspace);
  assert.ok('censusStatus' in workspace);
  assert.equal(typeof workspace.startCollectionSession, 'function');
  assert.equal(typeof workspace.stopCollectionSession, 'function');
  assert.equal(typeof workspace.handleCollectionEvent, 'function');
});

test('workspace starts and stops a collection session through the data center api', async () => {
  const calls = [];
  const workspace = useDataCollectionWorkspace({
    api: {
      async getDataCenterCollectionSessions() {
        calls.push('list');
        return {
          sessions: [
            {
              session_id: 'sess-2',
              status: 'running',
            },
          ],
        };
      },
      async getDataCenterCollectionSessionDetail(sessionId) {
        calls.push(`detail:${sessionId}`);
        return {
          session: {
            session_id: sessionId,
            status: 'running',
            progress: {
              written_seconds: 60,
              remaining_seconds: 1740,
              seconds_to_full_window: 7140,
              seconds_to_next_boundary: 840,
            },
            coverage: {
              coverage_ratio: 1,
            },
            charts: {
              price: [],
              trade: [],
              book: [],
            },
          },
        };
      },
      async createDataCenterCollectionSession(payload) {
        calls.push(`create:${payload.inst_id}`);
        return {
          session: {
            session_id: 'sess-2',
          },
        };
      },
      async stopDataCenterCollectionSession(sessionId) {
        calls.push(`stop:${sessionId}`);
        return {
          session: {
            session_id: sessionId,
            status: 'stopped',
          },
        };
      },
    },
  });

  await workspace.startCollectionSession({
    inst_id: 'BTC-USDT-SWAP',
    planned_duration_sec: 1800,
  });
  await workspace.stopCollectionSession('sess-2');

  assert.equal(workspace.selectedSessionId.value, 'sess-2');
  assert.equal(workspace.sessionProgress.value.writtenSeconds, 60);
  assert.deepEqual(calls, [
    'create:BTC-USDT-SWAP',
    'list',
    'detail:sess-2',
    'stop:sess-2',
    'list',
    'detail:sess-2',
  ]);
});

test('workspace refreshes active session on second_flushed and session_quality_updated', async () => {
  const calls = [];
  const workspace = useDataCollectionWorkspace({
    api: {
      async getDataCenterCollectionSessions() {
        calls.push('list');
        return { sessions: [] };
      },
      async getDataCenterCollectionSessionDetail(sessionId) {
        calls.push(`detail:${sessionId}`);
        return {
          session: {
            session_id: sessionId,
            progress: {
              written_seconds: 12,
              remaining_seconds: 1788,
              seconds_to_full_window: 7188,
              seconds_to_next_boundary: 543,
            },
            coverage: {
              coverage_ratio: 0.98,
            },
            charts: {
              price: [],
              trade: [],
              book: [],
            },
          },
        };
      },
      async getDataCenterCollectionCensusStatus() {
        calls.push('census');
        return { status: { enabled: true } };
      },
    },
  });

  workspace.selectedSessionId.value = 'sess-1';
  await workspace.handleCollectionEvent({
    event: 'second_flushed',
    session_id: 'sess-1',
    second_bucket: 1713000000,
  });
  await workspace.handleCollectionEvent({
    event: 'session_quality_updated',
    session_id: 'sess-1',
  });
  await workspace.handleCollectionEvent({
    event: 'census_updated',
  });

  assert.deepEqual(calls, [
    'detail:sess-1',
    'detail:sess-1',
    'census',
  ]);
});

test('workspace stores api detail when collection session start fails', async () => {
  const workspace = useDataCollectionWorkspace({
    api: {
      async createDataCenterCollectionSession() {
        const error = new Error('request failed');
        error.response = {
          data: {
            detail: 'market feed unavailable',
          },
        };
        throw error;
      },
    },
  });

  await workspace.startCollectionSession({
    inst_id: 'BTC-USDT-SWAP',
    planned_duration_sec: 1800,
  });

  assert.equal(workspace.sessionActionPending.value, false);
  assert.equal(workspace.sessionActionError.value, 'market feed unavailable');
});

test('workspace deletes selected collection session and clears stale detail', async () => {
  const calls = [];
  const workspace = useDataCollectionWorkspace({
    api: {
      async deleteDataCenterCollectionSession(sessionId) {
        calls.push(`delete:${sessionId}`);
        return {
          deleted_session: {
            session_id: sessionId,
            deleted_second_state_count: 1,
            deleted_sample_index_count: 1,
            deleted_boundary_target_count: 1,
            deleted_session_count: 1,
          },
        };
      },
      async getDataCenterCollectionSessions() {
        calls.push('list');
        return { sessions: [] };
      },
    },
  });

  workspace.selectedSessionId.value = 'sess-2';
  workspace.activeSession.value = {
    session_id: 'sess-2',
    status: 'stopped',
  };

  await workspace.deleteCollectionSession('sess-2');

  assert.equal(workspace.selectedSessionId.value, '');
  assert.equal(workspace.activeSession.value, null);
  assert.deepEqual(calls, ['delete:sess-2', 'list']);
});

test('workspace prunes deleted session before loading detail when list response is stale', async () => {
  const calls = [];
  const workspace = useDataCollectionWorkspace({
    api: {
      async deleteDataCenterCollectionSession(sessionId) {
        calls.push(`delete:${sessionId}`);
        return {
          deleted_session: {
            session_id: sessionId,
          },
        };
      },
      async getDataCenterCollectionSessions() {
        calls.push('list');
        return {
          sessions: [
            { session_id: 'sess-2', status: 'stopped' },
            { session_id: 'sess-3', status: 'stopped' },
          ],
        };
      },
      async getDataCenterCollectionSessionDetail(sessionId) {
        calls.push(`detail:${sessionId}`);
        if (sessionId === 'sess-2') {
          const error = new Error('request failed');
          error.response = { status: 404 };
          throw error;
        }
        return {
          session: {
            session_id: sessionId,
            status: 'stopped',
            progress: {},
            coverage: {},
            charts: {},
          },
        };
      },
    },
  });

  workspace.selectedSessionId.value = 'sess-2';
  workspace.activeSession.value = {
    session_id: 'sess-2',
    status: 'stopped',
  };

  await workspace.deleteCollectionSession('sess-2');

  assert.equal(workspace.selectedSessionId.value, 'sess-3');
  assert.equal(workspace.activeSession.value?.session_id, 'sess-3');
  assert.deepEqual(calls, ['delete:sess-2', 'list', 'detail:sess-3']);
});

test('workspace ignores deleted session id during realtime refresh even if list response is stale', async () => {
  const calls = [];
  const workspace = useDataCollectionWorkspace({
    api: {
      async getDataCenterCollectionSessions() {
        calls.push('list');
        return {
          sessions: [
            { session_id: 'sess-2', status: 'stopped' },
            { session_id: 'sess-3', status: 'stopped' },
          ],
        };
      },
      async getDataCenterCollectionSessionDetail(sessionId) {
        calls.push(`detail:${sessionId}`);
        if (sessionId === 'sess-2') {
          const error = new Error('request failed');
          error.response = { status: 404 };
          throw error;
        }
        return {
          session: {
            session_id: sessionId,
            status: 'stopped',
            progress: {},
            coverage: {},
            charts: {},
          },
        };
      },
    },
  });

  workspace.selectedSessionId.value = 'sess-2';
  workspace.activeSession.value = {
    session_id: 'sess-2',
    status: 'stopped',
  };

  await workspace.handleCollectionEvent({
    event: 'session_deleted',
    session_id: 'sess-2',
  });

  assert.equal(workspace.selectedSessionId.value, 'sess-3');
  assert.equal(workspace.activeSession.value?.session_id, 'sess-3');
  assert.deepEqual(calls, ['list', 'detail:sess-3']);
});

test('workspace surfaces blocking dataset ids when collection deletion is rejected', async () => {
  const workspace = useDataCollectionWorkspace({
    api: {
      async deleteDataCenterCollectionSession() {
        const error = new Error('request failed');
        error.response = {
          data: {
            detail: {
              message: 'delete referenced datasets first',
              blocking_dataset_ids: ['dataset-1', 'dataset-2'],
            },
          },
        };
        throw error;
      },
    },
  });

  await workspace.deleteCollectionSession('sess-1');

  assert.equal(
    workspace.sessionActionError.value,
    'delete referenced datasets first：dataset-1、dataset-2',
  );
});
