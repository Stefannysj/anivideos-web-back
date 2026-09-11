import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import rateLimit from '@fastify/rate-limit';
import type { FastifyInstance } from 'fastify';
import type { AppConfig } from '../config/environment.js';
import { PublicHttpError } from '../shared/errors.js';

/** Protege las respuestas de la API. La CSP del frontend se configurara en su hosting. */
export async function registerSecurity(app: FastifyInstance, config: AppConfig): Promise<void> {
  await app.register(helmet, {
    global: true,
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'none'"],
        baseUri: ["'none'"],
        frameAncestors: ["'none'"],
        formAction: ["'none'"],
      },
    },
    hsts: config.environment === 'production' ? { maxAge: 31_536_000 } : false,
  });

  await app.register(cors, {
    origin(origin, callback) {
      if (origin === undefined || config.allowedOrigins.includes(origin)) {
        callback(null, true);
        return;
      }
      callback(new PublicHttpError(403, 'ORIGIN_NOT_ALLOWED', 'Origen no permitido.'), false);
    },
    methods: ['GET', 'HEAD', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    credentials: false,
    maxAge: 600,
    strictPreflight: true,
  });

  // Limite local por IP. No sustituye proteccion DDoS ni un almacen distribuido.
  await app.register(rateLimit, {
    global: true,
    max: 60,
    timeWindow: '1 minute',
  });
}
