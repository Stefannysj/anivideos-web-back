import type { FastifyInstance } from 'fastify';
import { healthResponseSchema } from './health.model.js';
import type { HealthResponse } from './health.model.js';

/** Liveness sin acceso a BD ni divulgacion de versiones o configuracion interna. */
export async function healthRoutes(app: FastifyInstance): Promise<void> {
  app.get<{ Reply: HealthResponse }>('/health', {
    schema: { response: { 200: healthResponseSchema } },
  }, async () => ({ status: 'ok', service: 'anivideos-api' }));
}
