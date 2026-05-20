import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { spawnSync } from 'node:child_process';

const runScript = (args) => {
  const result = spawnSync(process.execPath, ['frontend/scripts/waitForDevServer.js', ...args], {
    cwd: process.cwd(),
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return {
    code: result.status ?? 1,
    stdout: result.stdout || '',
    stderr: result.stderr || '',
  };
};

const listen = (server) => new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', () => {
    server.removeListener('error', reject);
    resolve();
  });
});

test('waitForDevServer script exits 0 when target is reachable', async (t) => {
  const server = http.createServer((request, response) => {
    response.writeHead(200, { 'content-type': 'text/plain' });
    response.end('ok');
  });

  try {
    await listen(server);
  } catch (error) {
    if (error?.code === 'EPERM') {
      t.skip('sandbox disallows binding local sockets');
      return;
    }
    throw error;
  }

  const address = server.address();
  const targetUrl = `http://127.0.0.1:${address?.port}`;
  const result = runScript([targetUrl, '2', '10']);

  server.close();
  await once(server, 'close');

  assert.equal(result.code, 0);
  assert.equal(result.stderr, '');
});

test('waitForDevServer script exits 1 without a target url', async () => {
  const result = runScript([]);

  assert.equal(result.code, 1);
  const combinedOutput = `${result.stderr}${result.stdout}`.trim();
  if (combinedOutput) {
    assert.match(combinedOutput, /Usage: node waitForDevServer\.js <url>/);
  }
});
