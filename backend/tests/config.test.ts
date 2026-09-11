import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readEnvironment } from '../src/config/environment.js';

test('arranca localmente sin archivo .env', () => {
  const config = readEnvironment({});
  assert.equal(config.environment, 'development');
  assert.equal(config.host, '127.0.0.1');
  assert.equal(config.port, 3001);
  assert.ok(config.allowedOrigins.includes('http://127.0.0.1:5173'));
});

test('rechaza puertos invalidos en lugar de usar valores parciales', () => {
  for (const port of ['', '0', '-1', '65536', '3.2', '3001abc', '3e3']) {
    assert.throws(() => readEnvironment({ PORT: port }), /PORT/);
  }
});

test('rechaza entornos y niveles de log no reconocidos', () => {
  assert.throws(() => readEnvironment({ NODE_ENV: 'prod' }), /NODE_ENV/);
  assert.throws(() => readEnvironment({ LOG_LEVEL: 'all' }), /LOG_LEVEL/);
});

test('rechaza un host que no sea IP o localhost', () => {
  assert.throws(() => readEnvironment({ HOST: 'https://example.com' }), /HOST/);
});

test('produccion exige un origen explicito', () => {
  assert.throws(() => readEnvironment({ NODE_ENV: 'production' }), /FRONTEND_ORIGIN/);
});

test('produccion exige HTTPS', () => {
  assert.throws(() => readEnvironment({ NODE_ENV: 'production', FRONTEND_ORIGIN: 'http://example.com' }));
});

test('no permite origen wildcard, credenciales ni rutas', () => {
  for (const origin of ['*', 'https://name:password@example.com', 'https://example.com/path',
    'https://example.com?token=secret', 'https://example.com#fragment']) {
    assert.throws(() => readEnvironment({ FRONTEND_ORIGIN: origin }));
  }
});

test('acepta configuracion de produccion sin depender del frontend local', () => {
  const config = readEnvironment({ NODE_ENV: 'production', PORT: '8080', FRONTEND_ORIGIN: 'https://example.com/' });
  assert.equal(config.host, '0.0.0.0');
  assert.equal(config.port, 8080);
  assert.deepEqual(config.allowedOrigins, ['https://example.com']);
});
