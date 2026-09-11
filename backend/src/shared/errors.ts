export interface ApiErrorBody {
  error: { code: string; message: string; requestId: string };
}

/** Distingue errores publicos deliberados de fallos internos que no deben filtrarse. */
export class PublicHttpError extends Error {
  readonly statusCode: number;
  readonly code: string;

  constructor(statusCode: number, code: string, message: string) {
    super(message);
    this.name = 'PublicHttpError';
    this.statusCode = statusCode;
    this.code = code;
  }
}

const clientErrors: Record<number, { code: string; message: string }> = {
  400: { code: 'BAD_REQUEST', message: 'Solicitud no valida.' },
  403: { code: 'FORBIDDEN', message: 'Solicitud no permitida.' },
  404: { code: 'NOT_FOUND', message: 'Recurso no encontrado.' },
  413: { code: 'PAYLOAD_TOO_LARGE', message: 'La solicitud supera el limite permitido.' },
  415: { code: 'UNSUPPORTED_MEDIA_TYPE', message: 'Formato de solicitud no permitido.' },
  429: { code: 'RATE_LIMITED', message: 'Demasiadas solicitudes. Intenta nuevamente mas tarde.' },
};

/** Nunca devuelve stacks, consultas SQL ni mensajes internos de otras librerias. */
export function normalizeError(error: unknown, requestId: string): { statusCode: number; body: ApiErrorBody } {
  let statusCode = 500;
  let code = 'INTERNAL_ERROR';
  let message = 'Ocurrio un error interno.';

  if (error instanceof PublicHttpError && error.statusCode >= 400 && error.statusCode < 500) {
    ({ statusCode, code, message } = error);
  } else if (typeof error === 'object' && error !== null && 'statusCode' in error &&
             typeof error.statusCode === 'number' && Number.isInteger(error.statusCode) &&
             error.statusCode >= 400 && error.statusCode < 500) {
    statusCode = error.statusCode;
    ({ code, message } = clientErrors[statusCode] ?? {
      code: 'REQUEST_REJECTED', message: 'No fue posible procesar la solicitud.',
    });
  }
  return { statusCode, body: { error: { code, message, requestId } } };
}
