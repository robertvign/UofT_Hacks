import { z } from 'zod';
import { insertSongSchema, songs } from './schema';

export const errorSchemas = {
  validation: z.object({
    message: z.string(),
    field: z.string().optional(),
  }),
  notFound: z.object({
    message: z.string(),
  }),
  internal: z.object({
    message: z.string(),
  }),
};

export const api = {
  songs: {
    list: {
      method: 'GET' as const,
      path: '/api/songs',
      responses: {
        200: z.array(z.custom<typeof songs.$inferSelect>()),
      },
    },
    create: {
      method: 'POST' as const,
      path: '/api/songs',
      input: insertSongSchema,
      responses: {
        201: z.custom<typeof songs.$inferSelect>(),
        400: errorSchemas.validation,
      },
    },
    update: {
      method: 'PUT' as const,
      path: '/api/songs/:id',
      input: insertSongSchema.partial(),
      responses: {
        200: z.custom<typeof songs.$inferSelect>(),
        404: errorSchemas.notFound,
      },
    },
    delete: {
      method: 'DELETE' as const,
      path: '/api/songs/:id',
      responses: {
        204: z.void(),
        404: errorSchemas.notFound,
      },
    },
  },
};

export function buildUrl(path: string, params?: Record<string, string | number>): string {
  let url = path;
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (url.includes(`:${key}`)) {
        url = url.replace(`:${key}`, String(value));
      }
    });
  }
  return url;
}

export type SongInput = z.infer<typeof api.songs.create.input>;
export type SongResponse = z.infer<typeof api.songs.create.responses[201]>;
