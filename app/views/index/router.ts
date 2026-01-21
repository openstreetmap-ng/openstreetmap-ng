import { getRouteParamSpecificity, type QuerySchema } from "@lib/codecs"
import { qsEncode, qsParseAll } from "@lib/qs"
import { unquotePlus } from "@lib/utils"
import type { ReadonlySignal, Signal } from "@preact/signals"
import { batch, effect, signal } from "@preact/signals"
import { assert } from "@std/assert"
import { mapNotNullish } from "@std/collections/map-not-nullish"
import { sumOf } from "@std/collections/sum-of"
import { trimEndBy } from "@std/text/unstable-trim-by"
import { z } from "@zod/zod"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { ComponentChildren } from "preact"

export type RouteLoadReason = "navigation" | "popstate"

export type RouteContext = Readonly<{
  reason: RouteLoadReason
  path: string
  pathname: string
  search: string
  queryParams: Readonly<Record<string, string[]>>
}>

type EmptyParams = Record<never, never>
type EmptyQuery = Record<never, never>

type ParamSignals<P extends object> = {
  [K in keyof P]-?: ReadonlySignal<P[K]>
}

type QuerySignals<Q extends object> = {
  [K in keyof Q]-?: Signal<Q[K]>
}

type AnyRouteComponent = (props: any) => ComponentChildren

export type RouteComponent<
  P extends object = EmptyParams,
  Q extends object = EmptyQuery,
> = (
  props: {
    map: MaplibreMap
    ctx: ReadonlySignal<RouteContext>
  } & ParamSignals<P> &
    QuerySignals<Q>,
) => ComponentChildren

type PathParamSchema<T = unknown> = z.ZodType<T, string>
type PathParamSpec = Record<string, PathParamSchema<any>>

type QuerySpec = Record<string, QuerySchema<any>>

type AliasMap = Readonly<Record<string, string>>
type RouteAliases = Readonly<{
  params?: AliasMap
  query?: AliasMap
}>

type PathToken =
  | { kind: "lit"; value: string }
  | { kind: "param"; name: string; schema: PathParamSchema<any> }

type Specificity = Readonly<{
  literalCount: number
  paramSpecificity: number
  registrationIndex: number
  variantIndex: number
}>

export type RouteDef = Readonly<{
  id: string
  path: string
  Component: AnyRouteComponent
  sidebarOverlay: boolean | undefined
}>

export type CompiledRouteDef<
  P extends object = EmptyParams,
  Q extends object = EmptyQuery,
> = RouteDef &
  Readonly<{
    _pathVariants: readonly Readonly<{ path: string; tokens: readonly PathToken[] }>[]
    _paramKeys: readonly string[]
    _queryKeys: readonly string[]
    _queryAliases: AliasMap | undefined
    _querySchema: z.ZodType<Q, Record<string, string[] | undefined>>
    _queryEncodeSchema: z.ZodType<any, Record<string, string[] | undefined>>
    _buildPathname: (params: P) => string
  }>

export type AnyRouteDef = CompiledRouteDef<any, any>

const removeTrailingSlash = (s: string) => trimEndBy(s, "/") || "/"
const getPathname = (path: string) => path.split("?", 1)[0]
const getPathSearch = (path: string) => {
  const i = path.indexOf("?")
  return i === -1 ? "" : path.slice(i)
}

const getCurrentPath = () =>
  removeTrailingSlash(window.location.pathname) + window.location.search

const dispatchHashChange = (oldURL: string, newURL: string) => {
  try {
    window.dispatchEvent(new HashChangeEvent("hashchange", { oldURL, newURL }))
  } catch {
    window.dispatchEvent(new Event("hashchange"))
  }
}

const compilePath = (
  path: string,
  spec: PathParamSpec,
  aliases?: AliasMap,
): readonly PathToken[] => {
  if (!path.startsWith("/")) throw new Error(`Route path must start with '/': ${path}`)
  if (path !== "/" && path.endsWith("/"))
    throw new Error(`Route path must not end with '/': ${path}`)

  if (path === "/") return []

  const seenParamNames = new Set<string>()
  const segments = path.slice(1).split("/")
  return segments.map((segment) => {
    if (segment.startsWith(":")) {
      const placeholderName = segment.slice(1)
      if (!placeholderName) throw new Error(`Invalid empty route param in: ${path}`)

      let name = placeholderName
      let schema = spec[name]

      if (!schema) {
        const target = aliases?.[name]
        const resolved = target ? spec[target] : undefined
        if (resolved) {
          name = target!
          schema = resolved
        }
      }

      if (!schema)
        throw new Error(
          `Missing param codec for ':${placeholderName}' in route: ${path}`,
        )

      if (seenParamNames.has(name))
        throw new Error(
          `Duplicate route param ':${name}' (via ':${placeholderName}') in route: ${path}`,
        )
      seenParamNames.add(name)

      return { kind: "param", name, schema } as const
    }
    if (!segment) throw new Error(`Invalid empty path segment in: ${path}`)
    return { kind: "lit", value: segment } as const
  })
}

const computeSpecificity = (
  tokens: readonly PathToken[],
  registrationIndex: number,
  variantIndex: number,
): Specificity => ({
  literalCount: sumOf(tokens, (t) => (t.kind === "lit" ? 1 : 0)),
  paramSpecificity: sumOf(tokens, (t) =>
    t.kind === "param" ? getRouteParamSpecificity(t.schema) : 0,
  ),
  registrationIndex,
  variantIndex,
})

const compareSpecificity = (a: Specificity, b: Specificity) => {
  if (a.literalCount !== b.literalCount) return b.literalCount - a.literalCount
  if (a.paramSpecificity !== b.paramSpecificity)
    return b.paramSpecificity - a.paramSpecificity
  if (a.registrationIndex !== b.registrationIndex)
    return a.registrationIndex - b.registrationIndex
  return a.variantIndex - b.variantIndex
}

const matchTokens = <P extends object>(
  tokens: readonly PathToken[],
  segments: readonly string[],
) => {
  if (segments.length !== tokens.length) return null

  const out: Record<string, unknown> = {}

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]
    const raw = segments[i]
    if (token.kind === "lit") {
      let segment: string
      try {
        segment = decodeURIComponent(raw)
      } catch {
        return null
      }
      if (segment !== token.value) return null
    } else {
      let segment: string
      try {
        segment = unquotePlus(raw)
      } catch {
        return null
      }
      const result = token.schema.safeDecode(segment)
      if (!result.success) return null
      out[token.name] = result.data
    }
  }

  return out as P
}

const buildPathname = <P extends object>(tokens: readonly PathToken[], params: P) => {
  if (!tokens.length) return "/"
  const obj = params as Record<string, unknown>
  const segments = tokens.map((t) => {
    if (t.kind === "lit") return t.value
    const value = obj[t.name]
    return encodeURIComponent(t.schema.encode(value))
  })
  return `/${segments.join("/")}`
}

type DecodeSpec<S extends Record<string, z.ZodType>> = {
  [K in keyof S]: z.output<S[K]>
}

type DecodeParams<S extends PathParamSpec | undefined> = S extends PathParamSpec
  ? DecodeSpec<S>
  : EmptyParams

type DecodeQuery<S extends QuerySpec | undefined> = S extends QuerySpec
  ? DecodeSpec<S>
  : EmptyQuery

export function defineRoute<
  Params extends PathParamSpec | undefined = undefined,
  Q extends QuerySpec | undefined = undefined,
>(def: {
  id: string
  path: string | readonly string[]
  params?: Params
  query?: Q
  aliases?: RouteAliases
  Component: RouteComponent<DecodeParams<Params>, DecodeQuery<Q>>
  sidebarOverlay?: boolean
}): CompiledRouteDef<DecodeParams<Params>, DecodeQuery<Q>> {
  const matchSpec = (def.params ?? {}) as PathParamSpec
  const paths = Array.isArray(def.path) ? def.path : [def.path]
  if (!paths.length)
    throw new Error(`Route must define at least one path for id '${def.id}'`)

  const pathVariants = paths.map((path) => ({
    path,
    tokens: compilePath(path, matchSpec, def.aliases?.params),
  }))

  const paramKeys = Object.keys(matchSpec)
  const querySpec = (def.query ?? {}) as QuerySpec
  const queryKeys = Object.keys(querySpec)
  const queryAliases = normalizeQueryAliases(def.aliases?.query, queryKeys)
  const querySchema = z.object(querySpec).strip()
  const queryEncodeSchema = querySchema.partial()
  for (const key of queryKeys) {
    if (paramKeys.includes(key))
      throw new Error(`Query param conflicts with route param '${key}' in: ${paths[0]}`)
  }

  const buildCandidates = pathVariants
    .map(({ tokens }, variantIndex) => ({
      tokens,
      requiredKeys: mapNotNullish(tokens, (t) => (t.kind === "param" ? t.name : null)),
      specificity: computeSpecificity(tokens, 0, variantIndex),
    }))
    .sort((a, b) => compareSpecificity(a.specificity, b.specificity))

  const out = {
    id: def.id,
    path: paths[0],
    Component: def.Component,
    sidebarOverlay: def.sidebarOverlay,
    _pathVariants: pathVariants,
    _paramKeys: paramKeys,
    _queryKeys: queryKeys,
    _queryAliases: queryAliases,
    _querySchema: querySchema,
    _queryEncodeSchema: queryEncodeSchema,
    _buildPathname: (params: any) => {
      const obj = params as Record<string, unknown>
      for (const c of buildCandidates) {
        if (c.requiredKeys.every((k) => obj[k] !== undefined && obj[k] !== null)) {
          return buildPathname(c.tokens, params)
        }
      }

      return buildPathname(pathVariants[0].tokens, params)
    },
  } as unknown as CompiledRouteDef<DecodeParams<Params>, DecodeQuery<Q>>
  return out
}

type RouteParams<R extends CompiledRouteDef<any, any>> =
  R extends CompiledRouteDef<infer P, any> ? P : never

type RouteQuery<R extends CompiledRouteDef<any, any>> =
  R extends CompiledRouteDef<any, infer Q> ? Q : never

type QueryInput<Q extends object> = Partial<{
  [K in keyof Q]: Exclude<Q[K], undefined>
}>

type OptionalizeUndefined<T extends object> = {
  [K in keyof T as undefined extends T[K] ? never : K]: T[K]
} & {
  [K in keyof T as undefined extends T[K] ? K : never]?: Exclude<T[K], undefined>
}

const buildSearch = (route: AnyRouteDef, query: object) => {
  if (!route._queryKeys.length) return ""
  const encoded = route._queryEncodeSchema.encode(query) as Record<
    string,
    string[] | undefined
  >
  return qsEncode(encoded)
}

type RouteHrefInput<R extends CompiledRouteDef<any, any>> = OptionalizeUndefined<
  RouteParams<R>
> &
  QueryInput<RouteQuery<R>>

export function routerHref<R extends CompiledRouteDef<any, any>>(
  route: R,
  input?: RouteHrefInput<R> | null,
) {
  const obj = input ?? {}
  const pathname = route._buildPathname(obj)
  const search = buildSearch(route, obj)
  return pathname + search
}

type CompiledRouteVariant = Readonly<{
  route: AnyRouteDef
  tokens: readonly PathToken[]
  specificity: Specificity
}>

let compiledRouteVariants: CompiledRouteVariant[] = []
let loadReason: RouteLoadReason = "navigation"

const currentPath = signal<string>(getCurrentPath())

const activeRoute = signal<AnyRouteDef | null>(null)
export const routerRoute: ReadonlySignal<AnyRouteDef | null> = activeRoute

const activeCtx = signal<RouteContext>(parseContext(currentPath.value, loadReason))
export const routerCtx: ReadonlySignal<RouteContext> = activeCtx

const activeParamSignals = signal<Record<string, Signal<unknown>>>({})
export const routerParams: ReadonlySignal<Record<string, Signal<unknown>>> =
  activeParamSignals

const activeQuerySignals = signal<Record<string, Signal<unknown>>>({})
export const routerQuery: ReadonlySignal<Record<string, Signal<unknown>>> =
  activeQuerySignals

const matchRoute = (path: string) => {
  const pathname = removeTrailingSlash(getPathname(path))
  const segments = pathname === "/" ? [] : pathname.slice(1).split("/")
  for (const variant of compiledRouteVariants) {
    const params = matchTokens<Record<string, unknown>>(variant.tokens, segments)
    if (params) return { route: variant.route, params }
  }
  return null
}

const reconcileSignalBag = (
  bagSignal: Signal<Record<string, Signal<unknown>>>,
  keys: readonly string[],
  getNextValue: (key: string) => unknown,
) => {
  const bag = bagSignal.peek()
  if (!keys.length) {
    if (Object.keys(bag).length) bagSignal.value = {}
    return
  }

  const needsRebuild =
    Object.keys(bag).length !== keys.length || keys.some((k) => bag[k] === undefined)

  if (needsRebuild) {
    const next: Record<string, Signal<unknown>> = {}
    for (const key of keys) {
      next[key] = signal(getNextValue(key))
    }
    bagSignal.value = next
    return
  }

  batch(() => {
    for (const key of keys) {
      const sig = bag[key]
      const next = getNextValue(key)
      if (!Object.is(sig.peek(), next)) sig.value = next
    }
  })
}

function parseContext(path: string, reason: RouteLoadReason): RouteContext {
  const pathname = getPathname(path)
  const search = getPathSearch(path)
  return {
    reason,
    path,
    pathname,
    search,
    queryParams: qsParseAll(search),
  }
}

const normalizeQueryAliases = (aliases: AliasMap | undefined, queryKeys: string[]) => {
  if (!aliases) return
  const keySet = new Set(queryKeys)

  const out: Record<string, string> = {}
  for (const [aliasKey, targetKey] of Object.entries(aliases)) {
    if (aliasKey === targetKey) continue
    if (!keySet.has(targetKey))
      throw new Error(`Query alias target '${targetKey}' is not a declared query param`)
    if (keySet.has(aliasKey))
      throw new Error(
        `Query alias '${aliasKey}' conflicts with a declared query param key`,
      )
    out[aliasKey] = targetKey
  }

  return Object.keys(out).length ? out : undefined
}

const applyQueryAliases = (
  route: AnyRouteDef,
  queryParams: Readonly<Record<string, string[]>>,
) => {
  const aliases = route._queryAliases
  if (!aliases) return queryParams

  let out: Record<string, string[] | undefined> | null = null
  for (const [aliasKey, targetKey] of Object.entries(aliases)) {
    if (queryParams[targetKey]?.length) continue
    const values = queryParams[aliasKey]
    if (!values?.length) continue
    if (!out) out = { ...queryParams }
    out[targetKey] = values
  }

  return out ?? queryParams
}

const setPath = (mode: "push" | "replace", newPath: string, hash = location.hash) => {
  if (newPath === currentPath.value) return true
  if (!matchRoute(newPath)) {
    console.debug("IndexRouter: No route", mode, newPath)
    return false
  }

  const oldURL = location.href
  const oldHash = location.hash
  if (mode === "push") history.pushState(null, "", newPath + hash)
  else history.replaceState(null, "", newPath + hash)
  if (oldHash !== hash) dispatchHashChange(oldURL, location.href)
  loadReason = "navigation"
  currentPath.value = newPath
  return true
}

export function routerNavigate<R extends CompiledRouteDef<any, any>>(
  route: R,
  input?: RouteHrefInput<R> | null,
) {
  const path = routerHref(route, input)
  console.debug("IndexRouter: Navigate", route.id, "->", path)
  assert(setPath("push", path), `No route found for path: ${path}`)
}

export function routerReplace<R extends CompiledRouteDef<any, any>>(
  route: R,
  input?: RouteHrefInput<R> | null,
) {
  const path = routerHref(route, input)
  console.debug("IndexRouter: Replace", route.id, "->", path)
  assert(setPath("replace", path), `No route found for path: ${path}`)
}

export const configureRouter = (routeDefs: AnyRouteDef[]) => {
  compiledRouteVariants = routeDefs.flatMap((route, registrationIndex) =>
    route._pathVariants.map(({ tokens }, variantIndex) => ({
      route,
      tokens,
      specificity: computeSpecificity(tokens, registrationIndex, variantIndex),
    })),
  )

  compiledRouteVariants.sort((a, b) => compareSpecificity(a.specificity, b.specificity))

  console.debug(
    "IndexRouter: Configured",
    routeDefs.length,
    "routes",
    compiledRouteVariants.length,
    "variants",
  )

  const applyRoute = (path: string) => {
    const match = matchRoute(path)
    assert(match, `No route found for path: ${path}`)

    const prev = activeRoute.peek()
    const routeChanged = prev !== match.route
    if (routeChanged) activeRoute.value = match.route
    const ctx = parseContext(path, loadReason)
    activeCtx.value = ctx

    if (routeChanged || loadReason === "popstate") {
      console.debug(
        "IndexRouter: Route",
        loadReason,
        prev?.id ?? "<none>",
        "->",
        match.route.id,
        "@",
        ctx.path,
      )
    }

    const route = match.route
    const params = match.params
    const queryParams = ctx.queryParams

    reconcileSignalBag(activeParamSignals, route._paramKeys, (key) => params[key])

    if (!route._queryKeys.length) {
      reconcileSignalBag(activeQuerySignals, route._queryKeys, () => {})
      return
    }

    const decoded = route._querySchema.safeDecode(applyQueryAliases(route, queryParams))
    if (!decoded.success) {
      const firstIssue = decoded.error.issues[0]
      console.warn(
        "IndexRouter: Bad query",
        route.id,
        ctx.path,
        firstIssue.path.join("."),
        firstIssue.message,
      )
    }
    const decodedQuery = decoded.success
      ? (decoded.data as Record<string, unknown>)
      : {}

    reconcileSignalBag(activeQuerySignals, route._queryKeys, (key) => decodedQuery[key])
  }

  // Browser navigation
  window.addEventListener("popstate", () => {
    const path = getCurrentPath()
    if (path === currentPath.value) return

    loadReason = "popstate"
    currentPath.value = path
  })

  // Anchor click interception
  window.addEventListener("click", (e) => {
    if (
      e.defaultPrevented ||
      e.button !== 0 ||
      e.metaKey ||
      e.ctrlKey ||
      e.shiftKey ||
      e.altKey
    )
      return

    const target = (e.target as Element | null)?.closest("a[href]")
    if (!target?.href || target.origin !== location.origin) return

    const path = removeTrailingSlash(target.pathname) + target.search
    if (path === currentPath.value) {
      if (target.hash && target.hash !== location.hash) {
        location.hash = target.hash
      }
      e.preventDefault()
    } else if (setPath("push", path, target.hash || location.hash)) {
      e.preventDefault()
    }
  })

  // Effect: route updates (path and search changes)
  loadReason = "navigation"
  const initialPath = getCurrentPath()
  currentPath.value = initialPath
  let prevPath = initialPath
  batch(() => {
    applyRoute(initialPath)
  })

  // Effect: query signals -> URL (only for component-origin writes).
  effect(() => {
    const route = activeRoute.value!
    if (!route._queryKeys.length) return

    const querySignals = activeQuerySignals.value

    const queryObj: Record<string, unknown> = {}
    for (const key of route._queryKeys) {
      queryObj[key] = querySignals[key].value
    }

    const encoded = route._queryEncodeSchema.encode(queryObj) as Record<
      string,
      string[] | undefined
    >

    const paramSignals = activeParamSignals.peek()
    const params: Record<string, unknown> = {}
    for (const key of route._paramKeys) {
      params[key] = paramSignals[key].peek()
    }

    const pathname = route._buildPathname(params as any)
    const desired = pathname + qsEncode(encoded)
    if (desired === currentPath.peek()) return
    assert(setPath("replace", desired), `No route found for path: ${desired}`)
  })

  effect(() => {
    const path = currentPath.value
    if (path === prevPath) return

    prevPath = path
    applyRoute(path)
  })
}
