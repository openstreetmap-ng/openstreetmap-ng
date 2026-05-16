import type { GenEnum } from "@bufbuild/protobuf/codegenv2"
import { encodeMapState, parseLonLatZoom } from "@map/state"
import { distinct } from "@std/collections/distinct"
import { polylineDecode, polylineEncode } from "@utils/polyline"
import { z } from "@zod/zod/mini"

const PATH_POSITIVE_INT_RE = /^(?:0*[1-9][0-9]*)$/

const pathParamSpecificity = new WeakMap<z.ZodMiniType, number>()

export const getPathParamSpecificity = (schema: z.ZodMiniType): number =>
  pathParamSpecificity.get(schema) ?? 1

export const pathParam = {
  segment: () => {
    const schema = z.string().check(z.minLength(1))
    pathParamSpecificity.set(schema, 0)
    return schema
  },

  enum: <const T extends readonly [string, ...string[]]>(values: T) => z.enum(values),

  positive: () =>
    z.codec(
      z.string().check(z.regex(PATH_POSITIVE_INT_RE)),
      z.bigint().check(z.positive()),
      {
        decode: (s) => BigInt(s),
        encode: (n) => n.toString(),
      },
    ),

  optional: <T>(inner: z.ZodMiniType<T, string>) =>
    inner as z.ZodMiniType<T | undefined, string>,
} as const

export type QuerySchema<T = unknown> = z.ZodMiniType<T, string[] | undefined>

type ProtoEnumObject<TValue extends number> = Readonly<
  Record<string, TValue | string>
> &
  Readonly<Record<number, string | undefined>>
type ProtoEnumSource<TValue extends number> = ProtoEnumObject<TValue> | GenEnum<TValue>
type EnumCodecDefaultOptions<TValue> = Readonly<{
  default: TValue
  omitDefault?: boolean
}>
type EnumListCodecOptions = Readonly<{
  dedup?: boolean
}>

const STRINGBOOL = z.stringbool()

const isProtoEnumDescriptor = <TValue extends number>(
  value: ProtoEnumSource<TValue>,
): value is GenEnum<TValue> => "kind" in value && value.kind === "enum"

const protoEnumAccessors = <TValue extends number>(
  enumLike: ProtoEnumSource<TValue>,
) => {
  if (isProtoEnumDescriptor(enumLike)) {
    const valueByName = new Map<string, TValue>(
      enumLike.values.map((value) => [value.name, value.number as TValue]),
    )
    return {
      valueOf: (name: string) => valueByName.get(name),
      nameOf: (value: TValue) => enumLike.value[value]?.name,
    }
  }

  return {
    valueOf: (name: string) => {
      const value = enumLike[name]
      return typeof value === "number" ? value : undefined
    },
    nameOf: (value: TValue) => enumLike[value],
  }
}

const isStringTuple = (value: unknown): value is readonly [string, ...string[]] =>
  Array.isArray(value)

const mapQueryParam = <TIn, TOut>(
  schema: QuerySchema<TIn>,
  output: z.ZodMiniType<TOut, TOut>,
  options: {
    decode: (value: TIn) => TOut
    encode: (value: TOut) => TIn
  },
): QuerySchema<TOut> =>
  z.codec(z.optional(z.array(z.string())), output, {
    decode: (raw) => options.decode(z.parse(schema, raw)),
    encode: (value) => z.encode(schema, options.encode(value)),
  })

const queryEnumString = <const T extends readonly [string, ...string[]]>(
  values: T,
  options?: EnumCodecDefaultOptions<T[number]>,
) => {
  const schema = pathParam.enum(values)
  if (options) {
    const { default: defaultValue, omitDefault = true } = options
    return z.codec(z.optional(z.array(z.string())), schema, {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (last === undefined) return defaultValue
        const parsed = z.safeDecode(schema, last)
        return parsed.success ? parsed.data : defaultValue
      },
      encode: (value) => {
        if (omitDefault && value === defaultValue) return
        return [value]
      },
    })
  }

  return z.codec(z.optional(z.array(z.string())), z.optional(schema), {
    decode: (raw) => {
      const last = raw?.at(-1)
      if (last === undefined) return
      const parsed = z.safeDecode(schema, last)
      return parsed.success ? parsed.data : undefined
    },
    encode: (value) => (value !== undefined ? [value] : undefined),
  })
}

const queryEnumProto = <TValue extends number>(
  enumLike: ProtoEnumSource<TValue>,
  options?: EnumCodecDefaultOptions<TValue>,
) => {
  const enumAccessors = protoEnumAccessors(enumLike)

  if (options) {
    const { default: defaultValue, omitDefault = true } = options
    if (enumAccessors.nameOf(defaultValue) === undefined)
      throw new Error(`Missing enum name for default value '${defaultValue}'`)

    return z.codec(
      z.optional(z.array(z.string())),
      z.number() as unknown as z.ZodMiniType<TValue, number>,
      {
        decode: (raw) => {
          const last = raw?.at(-1)
          if (last === undefined) return defaultValue
          return enumAccessors.valueOf(last) ?? defaultValue
        },
        encode: (value) => {
          if (omitDefault && value === defaultValue) return
          const name = enumAccessors.nameOf(value as TValue)
          return name !== undefined ? [name] : undefined
        },
      },
    )
  }

  return z.codec(
    z.optional(z.array(z.string())),
    z.optional(z.number()) as unknown as z.ZodMiniType<
      TValue | undefined,
      number | undefined
    >,
    {
      decode: (raw) => {
        const last = raw?.at(-1)
        return last === undefined ? undefined : enumAccessors.valueOf(last)
      },
      encode: (value) => {
        if (value === undefined) return
        const name = enumAccessors.nameOf(value as TValue)
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
  enumLike: ProtoEnumSource<TValue>,
): QuerySchema<TValue | undefined>
function queryEnum<TValue extends number>(
  enumLike: ProtoEnumSource<TValue>,
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

  return z.codec(z.optional(z.array(z.string())), z.array(pathParam.enum(values)), {
    decode: (raw) => {
      if (!raw) return []
      const names = raw.filter((name): name is T[number] => nameSet.has(name))
      return dedup ? distinct(names) : names
    },
    encode: (value) => {
      if (!value.length) return
      return dedup ? distinct(value) : [...value]
    },
  })
}

const queryEnumListProto = <TValue extends number>(
  enumLike: ProtoEnumSource<TValue>,
  options?: EnumListCodecOptions,
) => {
  const dedup = options?.dedup ?? true
  const enumAccessors = protoEnumAccessors(enumLike)

  return z.codec(
    z.optional(z.array(z.string())),
    z.array(z.number()) as unknown as z.ZodMiniType<TValue[], number[]>,
    {
      decode: (raw) => {
        if (!raw) return []
        const values = raw
          .map((name) => enumAccessors.valueOf(name))
          .filter((value): value is TValue => value !== undefined)
        return dedup ? distinct(values) : values
      },
      encode: (value) => {
        if (!value.length) return
        const entries = dedup ? distinct(value) : value
        const names = entries
          .map((entry) => enumAccessors.nameOf(entry as TValue))
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
  enumLike: ProtoEnumSource<TValue>,
  options?: EnumListCodecOptions,
): QuerySchema<TValue[]>
function queryEnumList(source: any, options?: any) {
  return isStringTuple(source)
    ? queryEnumListString(source, options)
    : queryEnumListProto(source, options)
}

const queryPositive = () => {
  const schema = pathParam.positive()
  return z.codec(
    z.optional(z.array(z.string())),
    z.optional(z.bigint().check(z.positive())),
    {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (last === undefined) return
        const parsed = z.safeDecode(schema, last)
        return parsed.success ? parsed.data : undefined
      },
      encode: (value) => (value !== undefined ? [z.encode(schema, value)] : undefined),
    },
  )
}

const queryPositiveInt = () =>
  mapQueryParam(queryPositive(), z.optional(z.number().check(z.int(), z.positive())), {
    decode: (value) => {
      if (value === undefined) return
      const number = Number(value)
      return Number.isSafeInteger(number) && number > 0 ? number : undefined
    },
    encode: (value) => (value === undefined ? undefined : BigInt(value)),
  })

export const queryParam = {
  text: () =>
    z.codec(z.optional(z.array(z.string())), z.optional(z.string()), {
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

  positive: queryPositive,

  positiveInt: queryPositiveInt,

  enum: queryEnum,

  enumList: queryEnumList,

  timestamp: () =>
    z.codec(z.optional(z.array(z.string())), z.optional(z.bigint()), {
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
    z.codec(z.optional(z.array(z.string())), z.boolean(), {
      decode: (raw) => {
        const last = raw?.at(-1)
        if (!last) return false
        const parsed = z.safeDecode(STRINGBOOL, last)
        return parsed.success ? parsed.data : false
      },
      encode: (value) => (value ? ["1"] : undefined),
    }),

  lonLatZoom: () =>
    z.codec(
      z.optional(z.array(z.string())),
      z.optional(
        z.object({
          lon: z.number(),
          lat: z.number(),
          zoom: z.number(),
        }),
      ),
      {
        decode: (raw) => parseLonLatZoom(raw?.at(-1)) ?? undefined,
        encode: (value) => (value ? [encodeMapState(value, "")] : undefined),
      },
    ),

  polyline: (precision: number) =>
    z.codec(
      z.optional(z.array(z.string())),
      z.optional(z.readonly(z.array(z.readonly(z.tuple([z.number(), z.number()]))))),
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
