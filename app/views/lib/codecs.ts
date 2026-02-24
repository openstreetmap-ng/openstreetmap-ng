import { encodeMapState, parseLonLatZoom } from "@lib/map/state"
import { polylineDecode, polylineEncode } from "@lib/polyline"
import { z } from "@zod/zod"

const PATH_POSITIVE_INT_RE = /^(?:0*[1-9][0-9]*)$/

export const getPathParamSpecificity = (schema: z.ZodType) => {
  const meta = schema.meta() as { routeParamSpecificity?: number } | undefined
  return meta?.routeParamSpecificity ?? 1
}

export const pathParam = {
  segment: () => z.string().min(1).meta({ routeParamSpecificity: 0 }),

  enum: <const T extends readonly [string, ...string[]]>(values: T) => z.enum(values),

  positive: () =>
    z.codec(z.string().regex(PATH_POSITIVE_INT_RE), z.bigint().positive(), {
      decode: (s) => BigInt(s),
      encode: (n) => n.toString(),
    }),

  optional: <T>(inner: z.ZodType<T, string>) =>
    inner as z.ZodType<T | undefined, string>,
} as const

export type QuerySchema<T = unknown> = z.ZodType<T, string[] | undefined>

type ProtoEnumLike<TValue extends number> = Readonly<Record<string, TValue | string>> &
  Readonly<Record<number, string | undefined>>
type EnumCodecDefaultOptions<TValue> = Readonly<{
  default: TValue
  omitDefault?: boolean
}>
type EnumListCodecOptions = Readonly<{
  dedup?: boolean
}>

const protoEnumValue = <TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
  name: string,
) => {
  const value = enumLike[name]
  return typeof value === "number" ? value : undefined
}

const protoEnumName = <TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
  value: TValue,
) => enumLike[value]

const isStringTuple = (value: unknown): value is readonly [string, ...string[]] =>
  Array.isArray(value)

const queryEnumString = <const T extends readonly [string, ...string[]]>(
  values: T,
  options?: EnumCodecDefaultOptions<T[number]>,
) => {
  const schema = pathParam.enum(values)
  if (options) {
    const { default: defaultValue, omitDefault = true } = options
    return z.codec(z.array(z.string()).optional(), schema, {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (last === undefined) return defaultValue
        const parsed = schema.safeDecode(last)
        return parsed.success ? parsed.data : defaultValue
      },
      encode: (value) => {
        if (omitDefault && value === defaultValue) return
        return [value]
      },
    })
  }

  return z.codec(z.array(z.string()).optional(), schema.optional(), {
    decode: (raw) => {
      const last = raw?.at(-1)
      if (last === undefined) return
      const parsed = schema.safeDecode(last)
      return parsed.success ? parsed.data : undefined
    },
    encode: (value) => (value !== undefined ? [value] : undefined),
  })
}

const queryEnumProto = <TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
  options?: EnumCodecDefaultOptions<TValue>,
) => {
  if (options) {
    const { default: defaultValue, omitDefault = true } = options
    if (protoEnumName(enumLike, defaultValue) === undefined)
      throw new Error(`Missing enum name for default value '${defaultValue}'`)

    return z.codec(
      z.array(z.string()).optional(),
      z.number() as unknown as z.ZodType<TValue, number>,
      {
        decode: (raw) => {
          const last = raw?.at(-1)
          if (last === undefined) return defaultValue
          return protoEnumValue(enumLike, last) ?? defaultValue
        },
        encode: (value) => {
          if (omitDefault && value === defaultValue) return
          const name = protoEnumName(enumLike, value)
          return name !== undefined ? [name] : undefined
        },
      },
    )
  }

  return z.codec(
    z.array(z.string()).optional(),
    z.number().optional() as unknown as z.ZodType<
      TValue | undefined,
      number | undefined
    >,
    {
      decode: (raw) => {
        const last = raw?.at(-1)
        return last === undefined ? undefined : protoEnumValue(enumLike, last)
      },
      encode: (value) => {
        if (value === undefined) return
        const name = protoEnumName(enumLike, value)
        return name !== undefined ? [name] : undefined
      },
    },
  )
}

function queryEnum<const T extends readonly [string, ...string[]]>(
  values: T,
): QuerySchema<T[number] | undefined>
function queryEnum<const T extends readonly [string, ...string[]]>(
  values: T,
  options: EnumCodecDefaultOptions<T[number]>,
): QuerySchema<T[number]>
function queryEnum<TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
): QuerySchema<TValue | undefined>
function queryEnum<TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
  options: EnumCodecDefaultOptions<TValue>,
): QuerySchema<TValue>
function queryEnum(source: any, options?: any) {
  return isStringTuple(source)
    ? queryEnumString(source, options)
    : queryEnumProto(source, options)
}

const queryEnumListString = <const T extends readonly [string, ...string[]]>(
  values: T,
  options?: EnumListCodecOptions,
) => {
  const dedup = options?.dedup ?? true
  const nameSet = new Set<string>(values)

  return z.codec(z.array(z.string()).optional(), z.array(pathParam.enum(values)), {
    decode: (raw) => {
      if (!raw) return []
      const names = raw.filter((name): name is T[number] => nameSet.has(name))
      return dedup ? [...new Set(names)] : names
    },
    encode: (value) => {
      if (!value.length) return
      const names = dedup ? [...new Set(value)] : value
      return [...names]
    },
  })
}

const queryEnumListProto = <TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
  options?: EnumListCodecOptions,
) => {
  const dedup = options?.dedup ?? true

  return z.codec(
    z.array(z.string()).optional(),
    z.array(z.number()) as unknown as z.ZodType<TValue[], number[]>,
    {
      decode: (raw) => {
        if (!raw) return []
        const values = raw
          .map((name) => protoEnumValue(enumLike, name))
          .filter((value): value is TValue => value !== undefined)
        return dedup ? [...new Set(values)] : values
      },
      encode: (value) => {
        if (!value.length) return
        const entries = dedup ? [...new Set(value)] : value
        const names = entries
          .map((entry) => protoEnumName(enumLike, entry))
          .filter((name): name is string => name !== undefined)
        return names.length ? names : undefined
      },
    },
  )
}

function queryEnumList<const T extends readonly [string, ...string[]]>(
  values: T,
  options?: EnumListCodecOptions,
): QuerySchema<T[number][]>
function queryEnumList<TValue extends number>(
  enumLike: ProtoEnumLike<TValue>,
  options?: EnumListCodecOptions,
): QuerySchema<TValue[]>
function queryEnumList(source: any, options?: any) {
  return isStringTuple(source)
    ? queryEnumListString(source, options)
    : queryEnumListProto(source, options)
}

export const queryParam = {
  text: () =>
    z.codec(z.array(z.string()).optional(), z.string().optional(), {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (last === undefined) return
        const value = last.trim()
        return value || undefined
      },
      encode: (value) => {
        const next = value?.trim()
        return next ? [next] : undefined
      },
    }),

  positive: () => {
    const schema = pathParam.positive()
    return z.codec(z.array(z.string()).optional(), z.bigint().positive().optional(), {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (last === undefined) return
        const parsed = schema.safeDecode(last)
        return parsed.success ? parsed.data : undefined
      },
      encode: (value) => (value !== undefined ? [schema.encode(value)] : undefined),
    })
  },

  enum: queryEnum,

  enumList: queryEnumList,

  timestamp: () =>
    z.codec(z.array(z.string()).optional(), z.bigint().optional(), {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (last === undefined) return
        const ms = Date.parse(last)
        return Number.isNaN(ms) ? undefined : BigInt(Math.trunc(ms / 1000))
      },
      encode: (value) =>
        value !== undefined
          ? [new Date(Number(value) * 1000).toISOString()]
          : undefined,
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
