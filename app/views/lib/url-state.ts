import type { QuerySchema } from "@lib/codecs"
import { type ReadonlySignal, signal } from "@preact/signals"

export type UrlUpdateMode = "replace" | "push"

const currentUrl = signal(new URL(window.location.href))

window.addEventListener(
  "popstate",
  () => (currentUrl.value = new URL(window.location.href)),
)

export const currentUrlSignal: ReadonlySignal<URL> = currentUrl

export const updateUrl = (update: (url: URL) => void, mode: UrlUpdateMode) => {
  const prev = currentUrl.peek()
  const url = new URL(prev.href)
  update(url)

  if (url.href === prev.href) return
  if (mode === "push") history.pushState(null, "", url)
  else history.replaceState(null, "", url)
  currentUrl.value = url
}

const readUrlSearchParam = (key: string, url: URL = currentUrl.peek()) => {
  const values = url.searchParams.getAll(key)
  return values.length ? values : undefined
}

const updateUrlSearchParam = (
  key: string,
  values: string[] | undefined,
  mode: UrlUpdateMode,
) =>
  updateUrl((url) => {
    url.searchParams.delete(key)
    for (const value of values ?? []) url.searchParams.append(key, value)
  }, mode)

export const readUrlQueryParam = <T>(
  key: string,
  schema: QuerySchema<T>,
  url: URL = currentUrl.peek(),
) => schema.parse(readUrlSearchParam(key, url))

export const updateUrlQueryParam = <T>(
  key: string,
  schema: QuerySchema<T>,
  value: T,
  mode: UrlUpdateMode,
) => updateUrlSearchParam(key, schema.encode(value), mode)
