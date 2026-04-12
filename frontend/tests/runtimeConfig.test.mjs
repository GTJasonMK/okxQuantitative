import test from 'node:test';
import assert from 'node:assert/strict';

import {
  resolveRuntimeBackendUrl,
} from '../src/renderer/utils/runtimeConfig.mjs';

test('resolveRuntimeBackendUrl prefers Electron runtime config over saved config', () => {
  const resolved = resolveRuntimeBackendUrl({
    defaultUrl: 'http://127.0.0.1:8000',
    savedUrl: 'http://127.0.0.1:9000',
    windowLike: {
      electronAPI: {
        getRuntimeConfig: () => ({ backendUrl: 'http://127.0.0.1:18000' }),
      },
    },
  });

  assert.equal(resolved, 'http://127.0.0.1:18000');
});

test('resolveRuntimeBackendUrl falls back to saved config and then default', () => {
  const fromSaved = resolveRuntimeBackendUrl({
    defaultUrl: 'http://127.0.0.1:8000',
    savedUrl: 'http://127.0.0.1:9000',
    windowLike: {},
  });
  const fromDefault = resolveRuntimeBackendUrl({
    defaultUrl: 'http://127.0.0.1:8000',
    savedUrl: '',
    windowLike: {},
  });

  assert.equal(fromSaved, 'http://127.0.0.1:9000');
  assert.equal(fromDefault, 'http://127.0.0.1:8000');
});
