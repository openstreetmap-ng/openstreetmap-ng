import type {
  QueryContract,
  QueryContractEncodeInput,
  QueryContractState,
} from "@lib/query-contract"
import { type Signal, signal, useSignal, useSignalEffect } from "@preact/signals"

type UpdateMode = "replace" | "push"

export type QueryContractSignal<C extends QueryContract<any>> = Signal<
  QueryContractState<C>
>

const currentUrl = signal(new URL(window.location.href))

window.addEventListener(
  "popstate",
  () => (currentUrl.value = new URL(window.location.href)),
)

const updateUrl = (update: (url: URL) => void, mode: UpdateMode) => {
  const prev = currentUrl.peek()
  const url = new URL(prev.href)
  update(url)

  if (url.href === prev.href) return
  if (mode === "push") history.pushState(null, "", url)
  else history.replaceState(null, "", url)
  currentUrl.value = url
}

export const useUrlQueryState = <C extends QueryContract<any>>(
  contract: C,
  options?: { mode?: UpdateMode },
) => {
  const mode = options?.mode ?? "replace"
  const getValue = () => contract.parseSearch(currentUrl.value.search)
  const value = useSignal(getValue())

  // Effect: URL -> signal
  useSignalEffect(() => void (value.value = getValue()))

  // Effect: signal -> URL
  useSignalEffect(() => {
    updateUrl((url) => {
      url.search = contract.encode(value.value)
    }, mode)
  })

  return value as QueryContractSignal<C>
}

type PathSuffix = "" | `/${string}`
type PathSuffixSwitchOptions<TKey extends string> = {
  mode?: UpdateMode
  defaultKey?: TKey
}

type PathSuffixQueryStateOptions<TKey extends string> = {
  pathMode?: UpdateMode
  queryMode?: UpdateMode
  defaultKey?: TKey
}

type PathSuffixSwitchState<T extends Readonly<Record<string, PathSuffix>>> = Signal<
  keyof T & string
> & {
  href: (
    nextKey: keyof T & string,
    hrefOptions?: { search?: string; hash?: string },
  ) => string
}

type PathSuffixQueryState<
  TVariants extends Readonly<Record<string, PathSuffix>>,
  C extends QueryContract<any>,
> = Omit<PathSuffixSwitchState<TVariants>, "href"> & {
  query: QueryContractSignal<C>
  href: (
    nextKey: keyof TVariants & string,
    hrefOptions?: { query?: QueryContractEncodeInput<C>; hash?: string },
  ) => string
}

const usePathSuffixSwitch = <
  const TVariants extends Readonly<Record<string, PathSuffix>>,
>(
  variants: TVariants,
  options?: PathSuffixSwitchOptions<keyof TVariants & string>,
): PathSuffixSwitchState<TVariants> => {
  type TKey = keyof TVariants & string

  const mode = options?.mode ?? "push"

  const entries = Object.entries(variants) as [TKey, PathSuffix][]
  const fallbackKey = options?.defaultKey ?? entries.find(([, suffix]) => !suffix)![0]

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
  const key = useSignal(getKeyFromUrl())

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

export const usePathSuffixQueryState = <
  const TVariants extends Readonly<Record<string, PathSuffix>>,
  C extends QueryContract<any>,
>(
  variants: TVariants,
  contract: C,
  options?: PathSuffixQueryStateOptions<keyof TVariants & string>,
): PathSuffixQueryState<TVariants, C> => {
  const pathOptions: PathSuffixSwitchOptions<keyof TVariants & string> = {}
  if (options?.pathMode !== undefined) pathOptions.mode = options.pathMode
  if (options?.defaultKey !== undefined) pathOptions.defaultKey = options.defaultKey
  const path = usePathSuffixSwitch(variants, pathOptions)

  const query = useUrlQueryState(
    contract,
    options?.queryMode === undefined ? undefined : { mode: options.queryMode },
  )

  const href = (
    nextKey: keyof TVariants & string,
    hrefOptions?: { query?: QueryContractEncodeInput<C>; hash?: string },
  ) => {
    const nextQuery =
      hrefOptions?.query === undefined
        ? query.value
        : ({ ...query.value, ...hrefOptions.query } as QueryContractEncodeInput<C>)
    const search = contract.encode(nextQuery)
    return path.href(
      nextKey,
      hrefOptions?.hash === undefined ? { search } : { search, hash: hrefOptions.hash },
    )
  }

  return Object.assign(path as Omit<typeof path, "href">, { query, href })
}
