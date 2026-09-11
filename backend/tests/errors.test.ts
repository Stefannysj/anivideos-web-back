import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizeError, PublicHttpError } from '../src/shared/errors.js';

test('oculta mensajes internos y stacks', () => {
  const result = normalizeError(new Error('SQL password=secret'), 'request-123');
  assert.equal(result.statusCode, 500);
  assert.equal(result.body.error.code, 'INTERNAL_ERROR');
  assert.equal(result.body.error.requestId, 'request-123');
  assert.equal(JSON.stringify(result).includes('secret'), false);
  assert.equal(JSON.stringify(result).includes('stack'), false);
});

test('conserva un error publico intencional', () => {
  const result = normalizeError(new PublicHttpError(403, 'ORIGIN_NOT_ALLOWED', 'Origen no permitido.'), 'id');
  assert.equal(result.statusCode, 403);
  assert.equal(result.body.error.code, 'ORIGIN_NOT_ALLOWED');
});

test('normaliza errores HTTP externos sin divulgar su mensaje', () => {
  for (const statusCode of [400, 404, 413, 415, 429]) {
    const result = normalizeError({ statusCode, message: 'secret detail' }, 'id');
    assert.equal(result.statusCode, statusCode);
    assert.equal(JSON.stringify(result).includes('secret'), false);
  }
});

test('un error publico 500 no expone informacion', () => {
  const result = normalizeError(new PublicHttpError(500, 'SQL', 'secret'), 'id');
  assert.equal(result.body.error.code, 'INTERNAL_ERROR');
});

test('tolera valores de error inesperados', () => {
  for (const error of [null, undefined, 'error', { statusCode: 200 }, { statusCode: 999 }, { statusCode: 400.5 }]) {
    assert.equal(normalizeError(error, 'id').statusCode, 500);
  }
});
