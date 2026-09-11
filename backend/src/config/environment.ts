import { isIP } from 'node:net';

export type RuntimeEnvironment = 'development' | 'test' | 'production';
export type LogLevel = 'fatal' | 'error' | 'warn' | 'info' | 'debug' | 'trace' | 'silent';

export interface AppConfig {
  readonly environment: RuntimeEnvironment;
  readonly host: string;
  readonly port: number;
  readonly allowedOrigins: readonly string[];
  readonly logLevel: LogLevel;
}

const localOrigins = [
  'http://127.0.0.1:5173', 'http://localhost:5173',
  'http://127.0.0.1:4173', 'http://localhost:4173',
];

function parseOrigin(value: string, production: boolean): string {
  const url = new URL(value);
  const allowedProtocol = url.protocol === 'https:' || (!production && url.protocol === 'http:');
  if (!allowedProtocol || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('FRONTEND_ORIGIN debe ser un origen HTTP(S), sin rutas ni credenciales.');
  }
  return url.origin;
}

/** Falla al arrancar si la configuracion es insegura; no carga archivos .env. */
export function readEnvironment(source: Record<string, string | undefined> = process.env): AppConfig {
  const environment = source['NODE_ENV'] ?? 'development';
  if (environment !== 'development' && environment !== 'test' && environment !== 'production') {
    throw new Error('NODE_ENV debe ser development, test o production.');
  }
  const production = environment === 'production';
  const portText = source['PORT'] ?? '3001';
  const port = Number(portText);
  if (!/^\d+$/.test(portText) || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('PORT debe ser un entero entre 1 y 65535.');
  }
  const host = source['HOST'] ?? (production ? '0.0.0.0' : '127.0.0.1');
  if (host !== 'localhost' && isIP(host) === 0) throw new Error('HOST debe ser localhost o una IP valida.');

  const logLevel = source['LOG_LEVEL'] ?? (environment === 'test' ? 'silent' : 'info');
  if (logLevel !== 'fatal' && logLevel !== 'error' && logLevel !== 'warn' &&
      logLevel !== 'info' && logLevel !== 'debug' && logLevel !== 'trace' && logLevel !== 'silent') {
    throw new Error('LOG_LEVEL no es valido.');
  }

  const frontendOrigin = source['FRONTEND_ORIGIN']?.trim();
  if (production && !frontendOrigin) throw new Error('FRONTEND_ORIGIN es obligatorio en produccion.');
  const allowedOrigins = frontendOrigin
    ? [parseOrigin(frontendOrigin, production)]
    : [...localOrigins];

  return { environment, host, port, allowedOrigins, logLevel };
}
