export interface HealthResponse {
  status: 'ok';
  service: 'anivideos-api';
}

export const healthResponseSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['status', 'service'],
  properties: {
    status: { type: 'string', const: 'ok' },
    service: { type: 'string', const: 'anivideos-api' },
  },
} as const;
