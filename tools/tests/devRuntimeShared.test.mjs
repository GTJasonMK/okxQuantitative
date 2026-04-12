import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';

import {
  findAvailablePort,
  buildRuntimeEnv,
  createOutputPump,
  resolveCommand,
  resolveSpawnOptions,
} from '../devRuntimeShared.cjs';

const listen = (server, port, host) => new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(port, host, () => {
    server.removeListener('error', reject);
    resolve();
  });
});

const close = (server) => new Promise((resolve, reject) => {
  server.close((error) => (error ? reject(error) : resolve()));
});

test('findAvailablePort returns the preferred port when it is free', async () => {
  const probe = net.createServer();
  await listen(probe, 0, '127.0.0.1');
  const address = probe.address();
  const preferredPort = address.port;
  await close(probe);

  const resolvedPort = await findAvailablePort({
    host: '127.0.0.1',
    preferredPort,
  });

  assert.equal(resolvedPort, preferredPort);
});

test('findAvailablePort falls back when the preferred port is occupied', async () => {
  const occupied = net.createServer();
  await listen(occupied, 0, '127.0.0.1');
  const address = occupied.address();

  const resolvedPort = await findAvailablePort({
    host: '127.0.0.1',
    preferredPort: address.port,
  });

  await close(occupied);

  assert.notEqual(resolvedPort, address.port);
  assert.ok(resolvedPort > 0);
});

test('buildRuntimeEnv injects runtime backend and dev server urls', () => {
  const env = buildRuntimeEnv({
    sourceEnv: { BASE: '1' },
    backendPort: 18000,
    devServerPort: 15173,
  });

  assert.equal(env.BASE, '1');
  assert.equal(env.OKX_BACKEND_URL, 'http://127.0.0.1:18000');
  assert.equal(env.OKX_DEV_SERVER_URL, 'http://127.0.0.1:15173');
  assert.equal(env.PYTHONIOENCODING, 'utf-8');
  assert.equal(env.PYTHONUTF8, '1');
});

test('resolveCommand only rewrites npm-style wrappers on Windows', () => {
  assert.equal(resolveCommand('npx', 'win32'), 'npx.cmd');
  assert.equal(resolveCommand('npm', 'win32'), 'npm.cmd');
  assert.equal(resolveCommand('uv', 'win32'), 'uv');
  assert.equal(resolveCommand('npx', 'linux'), 'npx');
});

test('resolveSpawnOptions enables shell for Windows cmd wrappers only', () => {
  assert.deepEqual(resolveSpawnOptions('npx', 'win32'), {
    command: 'npx',
    shell: true,
  });
  assert.deepEqual(resolveSpawnOptions('npm', 'win32'), {
    command: 'npm',
    shell: true,
  });
  assert.deepEqual(resolveSpawnOptions('uv', 'win32'), {
    command: 'uv',
    shell: false,
  });
  assert.deepEqual(resolveSpawnOptions('npx', 'linux'), {
    command: 'npx',
    shell: false,
  });
});

test('createOutputPump decodes Windows GBK output without mojibake', () => {
  const writes = [];
  const writer = {
    write(chunk) {
      writes.push(chunk);
    },
  };
  const pump = createOutputPump(writer, 'backend', { encoding: 'gbk' });
  const buffer = Buffer.from(
    'b2dfc2d4d2d1d1d3b3d9b3f5cabcbbafa3acbdabd4dacad7b4cecab9d3c3cab1cab5c0fdbbaf0a',
    'hex',
  );

  pump.push(buffer.subarray(0, 5));
  pump.push(buffer.subarray(5, 19));
  pump.push(buffer.subarray(19));
  pump.end();

  assert.deepEqual(writes, [
    '[backend] 策略已延迟初始化，将在首次使用时实例化\n',
  ]);
});
