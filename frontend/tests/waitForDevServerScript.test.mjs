import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { spawn } from 'node:child_process';

const runScript = (args) => new Promise((resolve) => {
  const child = spawn(process.execPath, ['frontend/scripts/waitForDevServer.js', ...args], {
    cwd: process.cwd(),
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (chunk) => {
    stdout += chunk.toString();
  });
  child.stderr.on('data', (chunk) => {
    stderr += chunk.toString();
  });
  child.on('close', (code) => {
    resolve({ code, stdout, stderr });
  });
});

test('waitForDevServer script exits 0 when target is reachable', async () => {
  const server = http.createServer((request, response) => {
    response.writeHead(200, { 'content-type': 'text/plain' });
    response.end('ok');
  });

  server.listen(0, '127.0.0.1');
  await once(server, 'listening');

  const address = server.address();
  const targetUrl = `http://127.0.0.1:${address.port}`;
  const result = await runScript([targetUrl, '2', '10']);

  server.close();
  await once(server, 'close');

  assert.equal(result.code, 0);
  assert.equal(result.stderr, '');
});

test('waitForDevServer script exits 1 without a target url', async () => {
  const result = await runScript([]);

  assert.equal(result.code, 1);
  assert.match(result.stderr, /Usage: node waitForDevServer\.js <url>/);
});
