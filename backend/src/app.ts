import { randomUUID } from 'node:crypto';
import Fastify from 'fastify';
import type { FastifyInstance } from 'fastify';
import type { AppConfig } from './config/environment.js';
import { registerSecurity } from './plugins/security.js';
import { healthRoutes } from './modules/health/health.route.js';
import { normalizeError } from './shared/errors.js';

/** Construye una API testeable sin abrir puertos ni depender de Supabase. */
export async function buildApp(config: AppConfig): Promise<FastifyInstance> {
  const app = Fastify({
    logger: config.environment === 'test' ? false : {
      level: config.logLevel,
      redact: {
        paths: ['req.headers.authorization', 'req.headers.cookie', 'req.headers["x-api-key"]', 'res.headers["set-cookie"]'],
        censor: '[REDACTED]',
      },
    },
    trustProxy: false,
    requestIdHeader: false,
    genReqId: () => randomUUID(),
    bodyLimit: 16 * 1024,
    requestTimeout: 10_000,
    connectionTimeout: 10_000,
    keepAliveTimeout: 5_000,
    ajv: { customOptions: { removeAdditional: false, coerceTypes: false, useDefaults: false } },
  });

  app.addHook('onSend', async (request, reply, payload) => {
    reply.header('Cache-Control', 'no-store');
    reply.header('X-Request-Id', request.id);
    return payload;
  });

  app.setErrorHandler((error, request, reply) => {
    const failure = normalizeError(error, request.id);
    if (failure.statusCode >= 500) request.log.error({ err: error }, 'Fallo interno de la API');
    void reply.code(failure.statusCode).send(failure.body);
  });

  app.setNotFoundHandler((request, reply) => {
    void reply.code(404).send({
      error: { code: 'NOT_FOUND', message: 'Recurso no encontrado.', requestId: request.id },
    });
  });

  await registerSecurity(app, config);
  await app.register(healthRoutes, { prefix: '/api' });
  return app;
}
