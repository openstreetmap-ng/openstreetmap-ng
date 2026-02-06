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
export function useQuerySignal<TSchema, const TDefault>(
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
      params[key] = nextDefault !== undefined ? schema.encode(nextDefault) : undefined
      url.search = qsEncode(params)
    }, mode)
  })

  return value
}

type PathSuffix = "" | `/${string}`
type EmptySuffixKey<T extends Readonly<Record<string, PathSuffix>>> = {
  [K in keyof T & string]: T[K] extends "" ? K : never
}[keyof T & string]
type PathSuffixSwitchArgs<T extends Readonly<Record<string, PathSuffix>>> =
  EmptySuffixKey<T> extends never
    ? [options: { mode?: UpdateMode; defaultKey: keyof T & string }]
    : [options?: { mode?: UpdateMode }]

export const usePathSuffixSwitch = <
  const TVariants extends Readonly<Record<string, PathSuffix>>,
>(
  variants: TVariants,
  ...[options]: PathSuffixSwitchArgs<TVariants>
) => {
  type TKey = keyof TVariants & string

  const mode = options?.mode ?? "push"

  const entries = Object.entries(variants) as [TKey, PathSuffix][]
  const fallbackKey =
    options && "defaultKey" in options
      ? options.defaultKey
      : entries.find(([, suffix]) => !suffix)![0]

  entries.sort((a, b) => b[1].length - a[1].length)

  const parsePathname = (pathname: string) => {
    for (const [key, suffix] of entries) {
      if (!suffix) continue
      if (pathname.endsWith(suffix))
        return { basePathname: pathname.slice(0, -suffix.length), key }
    }
    return { basePathname: pathname, key: fallbackKey }
  }

  const getKeyFromUrl = () => parsePathname(currentUrl.value.pathname).key
  const key = useSignal<TKey>(getKeyFromUrl())

  // Effect: URL -> signals
  useSignalEffect(() => {
    const next = getKeyFromUrl()
    if (key.peek() !== next) key.value = next
  })

  const href = (nextKey: TKey, hrefOptions?: { search?: string; hash?: string }) => {
    const prev = currentUrl.peek()
    const basePathname = parsePathname(prev.pathname).basePathname
    const pathname = (basePathname === "/" ? "" : basePathname) + variants[nextKey]
    const search = hrefOptions?.search ?? prev.search
    const hash = hrefOptions?.hash ?? prev.hash
    return (pathname || "/") + search + hash
  }

  // Effect: key -> URL
  useSignalEffect(() => {
    updateUrl((url) => {
      const basePathname = parsePathname(url.pathname).basePathname
      url.pathname =
        (basePathname === "/" ? "" : basePathname) + variants[key.value] || "/"
    }, mode)
  })

  return Object.assign(key, { href })
}
