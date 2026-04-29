import type { DescMessage, MessageShape } from "@bufbuild/protobuf"
import type { QuerySchema } from "@lib/codecs"
import { qsEncode, qsParseAll } from "@lib/qs"
import { assert } from "@std/assert"
import type { z } from "@zod/zod"

type ProtoFieldDescriptor = {
  readonly name: string
  readonly localName: string
}

type QueryContractSpec = Readonly<Record<string, QuerySchema<any>>>

type QueryOutput<Spec extends QueryContractSpec> = {
  [K in keyof Spec]: z.output<Spec[K]>
}

type ProtoKeys<Schema extends DescMessage> = Exclude<
  keyof MessageShape<Schema> & string,
  "$typeName" | "$unknown"
>

type ProtoFieldType<
  Schema extends DescMessage,
  Key extends ProtoKeys<Schema>,
> = MessageShape<Schema>[Key]

type ProtoQuerySpec<Schema extends DescMessage> = Required<
  Record<ProtoKeys<Schema>, QuerySchema<any>>
>

type NoExtraKeys<Type, Allowed extends PropertyKey> = Type &
  Record<Exclude<keyof Type, Allowed>, never>

type FieldTypeMismatch<Field extends string, Got, Expected> = {
  readonly __protoQueryContractError: "Field codec output is not assignable to proto field type"
  readonly field: Field
  readonly got: Got
  readonly expected: Expected
}

type EnforceProtoFieldTypes<
  Schema extends DescMessage,
  Spec extends ProtoQuerySpec<Schema>,
> = {
  [Key in ProtoKeys<Schema>]: z.output<Spec[Key]> extends ProtoFieldType<Schema, Key>
    ? Spec[Key]
    : FieldTypeMismatch<Key, z.output<Spec[Key]>, ProtoFieldType<Schema, Key>>
}

type QueryContractExternalKeys<Spec extends QueryContractSpec> = Partial<
  Record<keyof Spec & string, string>
>

type QueryContractOptions<Spec extends QueryContractSpec> = {
  externalKeys?: QueryContractExternalKeys<Spec>
  aliases?: Readonly<Record<string, keyof Spec & string>>
}

type QueryEncodeInput<T extends Record<string, unknown>> = Partial<QueryState<T>>

type OptionalizeUndefined<T extends Record<string, unknown>> = {
  [K in keyof T as undefined extends T[K] ? never : K]: T[K]
} & {
  [K in keyof T as undefined extends T[K] ? K : never]?: Exclude<T[K], undefined>
}

type QueryState<T extends Record<string, unknown>> = OptionalizeUndefined<T>

export type QueryContract<T extends Record<string, unknown>> = Readonly<{
  keys: readonly (keyof T & string)[]
  parseQueryParams: (
    query: Readonly<Record<string, string[] | undefined>>,
  ) => QueryState<T>
  parseSearch: (search: string) => QueryState<T>
  parseFormData: (formData: FormData) => QueryState<T>
  encodeParams: (value: QueryEncodeInput<T>) => Record<string, string[] | undefined>
  encode: (value: QueryEncodeInput<T>, prefix?: "?" | "#") => string
  keyOf: (value: QueryEncodeInput<T>) => string
}>

export type QueryContractState<C extends QueryContract<any>> = ReturnType<
  C["parseSearch"]
>

export type QueryContractEncodeInput<C extends QueryContract<any>> = Parameters<
  C["encode"]
>[0]

const formDataToQueryParams = (formData: FormData) => {
  const params: Record<string, string[]> = {}
  for (const [key, value] of formData.entries()) {
    const values = params[key] ?? (params[key] = [])
    values.push(value)
  }
  return params
}

export const defineQueryContract = <const Spec extends QueryContractSpec>(
  spec: Spec,
  options?: QueryContractOptions<Spec>,
): QueryContract<QueryOutput<Spec>> => {
  type Output = QueryOutput<Spec>

  const entries = Object.entries(spec) as [
    keyof QueryState<Output> & string,
    QuerySchema,
  ][]
  const keys = entries.map(([property]) => property)
  const keySet = new Set<string>(keys)

  const externalKeyByProperty = new Map<string, string>(
    entries.map(([property]) => [
      property,
      options?.externalKeys?.[property] ?? property,
    ]),
  )

  const propertyByExternalKey = new Map<string, string>()
  for (const [property, externalKey] of externalKeyByProperty) {
    if (propertyByExternalKey.has(externalKey)) {
      throw new Error(`Duplicate query external key '${externalKey}'`)
    }
    propertyByExternalKey.set(externalKey, property)
  }

  const aliasToExternalKey = new Map<string, string>()
  for (const [alias, property] of Object.entries(options?.aliases ?? {})) {
    if (!keySet.has(property)) {
      throw new Error(`Query alias target '${property}' is not a declared query key`)
    }

    const externalKey = externalKeyByProperty.get(property)!
    if (alias === externalKey) continue

    if (propertyByExternalKey.has(alias)) {
      throw new Error(
        `Query alias '${alias}' conflicts with canonical query key '${alias}'`,
      )
    }
    aliasToExternalKey.set(alias, externalKey)
  }

  const defaults = new Map<string, unknown>()
  const emptyQueryValues: string[] | undefined = undefined
  for (const [property, schema] of entries) {
    const result = schema.safeDecode(emptyQueryValues)
    if (!result.success || result.data === undefined) continue
    defaults.set(property, result.data)
  }

  const cloneValue = (value: unknown) => (Array.isArray(value) ? [...value] : value)

  const applyAliases = (query: Readonly<Record<string, string[] | undefined>>) => {
    if (!aliasToExternalKey.size) return query

    let out: Record<string, string[] | undefined> | null = null
    for (const [aliasKey, targetKey] of aliasToExternalKey) {
      if (query[targetKey]?.length) continue
      const values = query[aliasKey]
      if (!values?.length) continue
      if (!out) out = { ...query }
      out[targetKey] = values
    }

    return out ?? query
  }

  const parseQueryParams: QueryContract<Output>["parseQueryParams"] = (query) => {
    const source = applyAliases(query)
    const parsed: Record<string, unknown> = {}

    for (const [property, value] of defaults) {
      parsed[property] = cloneValue(value)
    }

    for (const [property, schema] of entries) {
      const result = schema.safeDecode(source[externalKeyByProperty.get(property)!])
      if (!result.success || result.data === undefined) continue
      parsed[property] = cloneValue(result.data)
    }

    return parsed as QueryState<Output>
  }

  const encodeParams: QueryContract<Output>["encodeParams"] = (value) => {
    const out: Record<string, string[] | undefined> = {}

    for (const [property, schema] of entries) {
      const fieldValue = value[property]
      if (fieldValue === undefined) continue
      out[externalKeyByProperty.get(property)!] = schema.encode(fieldValue)
    }

    return out
  }

  const keyOf: QueryContract<Output>["keyOf"] = (value) => qsEncode(encodeParams(value))

  return {
    keys,
    parseQueryParams,
    parseSearch: (search) => parseQueryParams(qsParseAll(search)),
    parseFormData: (formData) => parseQueryParams(formDataToQueryParams(formData)),
    encodeParams,
    encode: (value, prefix = "?") => qsEncode(encodeParams(value), prefix),
    keyOf,
  }
}

export const defineProtoQueryContract = <
  Schema extends DescMessage & { readonly fields: readonly ProtoFieldDescriptor[] },
  const Spec extends ProtoQuerySpec<Schema>,
>(
  schema: Schema,
  spec: NoExtraKeys<Spec, ProtoKeys<Schema>> & EnforceProtoFieldTypes<Schema, Spec>,
  options?: QueryContractOptions<Spec>,
): QueryContract<QueryOutput<Spec>> => {
  const fieldNameByLocalName = new Map<string, string>(
    schema.fields.map((field) => [field.localName, field.name]),
  )

  const externalKeys: QueryContractExternalKeys<Spec> = {}
  if (options?.externalKeys) Object.assign(externalKeys, options.externalKeys)
  for (const property of Object.keys(spec) as (keyof Spec & string)[]) {
    if (externalKeys[property] !== undefined) continue
    const fieldName = fieldNameByLocalName.get(property)
    assert(
      fieldName !== undefined,
      `Missing proto field '${property}' in schema '${schema.typeName}'`,
    )
    externalKeys[property] = fieldName
  }

  return defineQueryContract(spec, {
    ...options,
    externalKeys,
  })
}
