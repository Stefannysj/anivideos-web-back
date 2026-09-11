import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildApp } from '../src/app.js';
import { readEnvironment } from '../src/config/environment.js';

test('GET /api/health cumple el contrato publico y envia cabeceras', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  const response = await app.inject({ method: 'GET', url: '/api/health' });
  assert.equal(response.statusCode, 200);
  assert.deepEqual(response.json(), { status: 'ok', service: 'anivideos-api' });
  assert.equal(response.headers['x-content-type-options'], 'nosniff');
  assert.equal(response.headers['cache-control'], 'no-store');
  assert.ok(response.headers['x-request-id']);
  assert.equal(response.headers['x-powered-by'], undefined);
});

test('permite el origen local configurado', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  const response = await app.inject({ method: 'GET', url: '/api/health', headers: { origin: 'http://127.0.0.1:5173' } });
  assert.equal(response.statusCode, 200);
  assert.equal(response.headers['access-control-allow-origin'], 'http://127.0.0.1:5173');
});

test('rechaza origen ajeno incluso si imita el inicio de un dominio permitido', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  const response = await app.inject({ method: 'GET', url: '/api/health', headers: { origin: 'http://localhost:5173.evil.example' } });
  assert.equal(response.statusCode, 403);
  assert.equal(response.json<{ error: { code: string } }>().error.code, 'ORIGIN_NOT_ALLOWED');
  assert.equal(response.headers['access-control-allow-origin'], undefined);
});

test('resuelve preflight sin habilitar cookies', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  const response = await app.inject({ method: 'OPTIONS', url: '/api/health', headers: {
    origin: 'http://127.0.0.1:5173', 'access-control-request-method': 'GET',
  } });
  assert.equal(response.statusCode, 204);
  assert.equal(response.headers['access-control-allow-credentials'], undefined);
});

test('una ruta desconocida devuelve un 404 controlado', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  const response = await app.inject('/missing');
  assert.equal(response.statusCode, 404);
  assert.equal(response.json<{ error: { code: string } }>().error.code, 'NOT_FOUND');
});

test('limita solicitudes repetidas por IP', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  for (let index = 0; index < 60; index += 1) {
    assert.equal((await app.inject('/api/health')).statusCode, 200);
  }
  const response = await app.inject('/api/health');
  assert.equal(response.statusCode, 429);
  assert.equal(response.json<{ error: { code: string } }>().error.code, 'RATE_LIMITED');
});

test('no confia en X-Forwarded-For para eludir el limite local', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  for (let index = 0; index < 60; index += 1) {
    await app.inject({ url: '/api/health', headers: { 'x-forwarded-for': `10.0.0.${index + 1}` } });
  }
  assert.equal((await app.inject({ url: '/api/health', headers: { 'x-forwarded-for': '192.0.2.1' } })).statusCode, 429);
});

test('oculta errores imprevistos de una ruta', async (context) => {
  const app = await buildApp(readEnvironment({ NODE_ENV: 'test' }));
  context.after(async () => { await app.close(); });
  app.get('/test-error', async () => { throw new Error('SQL password=secret'); });
  const response = await app.inject('/test-error');
  assert.equal(response.statusCode, 500);
  assert.equal(response.body.includes('secret'), false);
});
