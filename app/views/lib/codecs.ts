import { encodeMapState, parseLonLatZoom } from "@lib/map/state"
import { polylineDecode, polylineEncode } from "@lib/polyline"
import { z } from "@zod/zod"

const ROUTE_POSITIVE_INT_RE = /^[0-9]+$/

export const getRouteParamSpecificity = (schema: z.ZodType) => {
  const meta = schema.meta() as { routeParamSpecificity?: number } | undefined
  return meta?.routeParamSpecificity ?? 1
}

export const routeParam = {
  segment: () => z.string().min(1).meta({ routeParamSpecificity: 0 }),

  enum: <const T extends readonly [string, ...string[]]>(values: T) => z.enum(values),

  positive: () =>
    z.codec(z.string().regex(ROUTE_POSITIVE_INT_RE), z.bigint().positive(), {
      decode: (s) => BigInt(s),
      encode: (n) => n.toString(),
    }),

  optional: <T>(inner: z.ZodType<T, string>) =>
    inner as unknown as z.ZodType<T | undefined, string>,
} as const

export type QuerySchema<T = unknown> = z.ZodType<T, string[] | undefined>

export const queryParam = {
  string: () =>
    z.codec(z.array(z.string()).optional(), z.string().optional(), {
      decode: (raw) => raw?.at(-1),
      encode: (value) => (value === undefined ? undefined : [value]),
    }),

  flag: () =>
    z.codec(z.array(z.string()).optional(), z.boolean(), {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (!last) return false
        const parsed = z.stringbool().safeDecode(last)
        return parsed.success ? parsed.data : false
      },
      encode: (value) => (value ? ["1"] : undefined),
    }),

  lonLatZoom: () =>
    z.codec(
      z.array(z.string()).optional(),
      z
        .object({
          lon: z.number(),
          lat: z.number(),
          zoom: z.number(),
        })
        .optional(),
      {
        decode: (raw) => parseLonLatZoom(raw?.at(-1)) ?? undefined,
        encode: (value) => (value ? [encodeMapState(value, "")] : undefined),
      },
    ),

  polyline: (precision: number) =>
    z.codec(
      z.array(z.string()).optional(),
      z
        .array(z.tuple([z.number(), z.number()]).readonly())
        .readonly()
        .optional(),
      {
        decode: (raw) => {
          const last = raw?.at(-1)
          if (last === undefined) return
          return polylineDecode(last, precision)
        },
        encode: (value) => {
          if (!value?.length) return
          return [polylineEncode(value, precision)]
        },
      },
    ),
} as const satisfies Readonly<Record<string, (...args: any[]) => QuerySchema<any>>>
