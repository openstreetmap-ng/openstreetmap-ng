import { associateWith } from "@std/collections/associate-with"
import { distinct } from "@std/collections/distinct"

/**
 * Parse a query string into an object
 * @example
 * qsParse("?foo=bar&baz=qux")
 * // => { foo: "bar", baz: "qux" }
 */
export const qsParse = (qs: string) => {
  if (!qs) return {}
  if (qs.startsWith("#")) qs = qs.slice(1)
  const params = new URLSearchParams(qs)
  return associateWith(distinct(params.keys()), (key) => params.getAll(key).join(";"))
}

/**
 * Encode an object into a query string with prefix
 * @example
 * qsEncode({ foo: "bar", baz: "qux", quux: undefined })
 * // => "?foo=bar&baz=qux"
 * qsEncode({})
 * // => ""
 * qsEncode({ hash: "value" }, "#")
 * // => "#hash=value"
 */
export const qsEncode = (
  obj: Record<string, string | string[] | undefined>,
  prefix = "?",
): string => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(obj)) {
    // Skip undefined values
    if (value === undefined) continue

    if (typeof value === "string") {
      params.set(key, value)
    } else {
      for (const item of value) {
        params.append(key, item)
      }
    }
  }
  const str = params.toString()
  return str ? `${prefix}${str.replaceAll("%2F", "/")}` : ""
}

export const updateSearchParams = (
  update: (searchParams: URLSearchParams) => void,
  mode: "replace" | "push" = "replace",
) => {
  const url = new URL(window.location.href)
  update(url.searchParams)

  if (mode === "replace") window.history.replaceState(null, "", url)
  else window.history.pushState(null, "", url)
}

/** Read a single query parameter from the current page URL. */
export const getSearchParam = (key: string) =>
  new URL(window.location.href).searchParams.get(key)
