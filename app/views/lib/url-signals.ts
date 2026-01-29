import type { QuerySchema } from "@lib/codecs"
import { qsEncode, qsParseAll } from "@lib/qs"
import { type Signal, signal, useSignal, useSignalEffect } from "@preact/signals"

type UpdateMode = "replace" | "push"

type QuerySignalOptions = {
  mode?: UpdateMode
  defaultValue?: never
}

type QuerySignalDefaultOptions<TDefault> = {
  mode?: UpdateMode
  defaultValue: TDefault
}

const currentUrl = signal(new URL(window.location.href))

window.addEventListener("popstate", () => {
  currentUrl.value = new URL(window.location.href)
})

const updateUrl = (update: (url: URL) => void, mode: UpdateMode) => {
  const prev = currentUrl.peek()
  const url = new URL(prev.href)
  update(url)

  if (url.href === prev.href) return
  if (mode === "push") history.pushState(null, "", url)
  else history.replaceState(null, "", url)
  currentUrl.value = url
}

export function useQuerySignal<TSchema>(
  key: string,
  schema: QuerySchema<TSchema>,
  options?: QuerySignalOptions,
): Signal<TSchema | undefined>
export function useQuerySignal<TSchema, TDefault>(
  key: string,
  schema: QuerySchema<TSchema>,
  options: QuerySignalDefaultOptions<TDefault>,
): Signal<Exclude<TSchema, undefined> | TDefault>
export function useQuerySignal<TSchema, TDefault>(
  key: string,
  schema: QuerySchema<TSchema>,
  options?: QuerySignalOptions | QuerySignalDefaultOptions<TDefault>,
) {
  const { mode = "replace", defaultValue } = options ?? {}

  const getValue = () => {
    const raw = qsParseAll(currentUrl.value.search)[key]
    if (raw === undefined) return defaultValue
    const decoded = schema.safeDecode(raw)
    return decoded.success && decoded.data !== undefined ? decoded.data : defaultValue
  }
  const value = useSignal(getValue())

  // Effect: URL -> signal
  useSignalEffect(() => {
    value.value = getValue()
  })

  // Effect: signal -> URL
  useSignalEffect(() => {
    updateUrl((url) => {
      const next = value.value
      const nextDefault =
        defaultValue !== undefined && next === defaultValue
          ? undefined
          : (next as Exclude<typeof next, TDefault>)

      const params: Record<string, string[] | undefined> = qsParseAll(url.search)
      params[key] = nextDefault === undefined ? undefined : schema.encode(nextDefault)
      url.search = qsEncode(params)
    }, mode)
  })

  return value
}

export const usePathSuffixSignal = (
  suffix: string,
  options?: { mode?: UpdateMode },
) => {
  const { mode = "push" } = options ?? {}

  const getHasSuffix = () => currentUrl.value.pathname.endsWith(suffix)
  const hasSuffix = useSignal(getHasSuffix())

  // Effect: URL -> signal
  useSignalEffect(() => {
    hasSuffix.value = getHasSuffix()
  })

  // Effect: signal -> URL
  useSignalEffect(() => {
    updateUrl((url) => {
      const base = url.pathname.endsWith(suffix)
        ? url.pathname.slice(0, -suffix.length)
        : url.pathname
      url.pathname = hasSuffix.value ? base + suffix : base
    }, mode)
  })

  return hasSuffix
}
