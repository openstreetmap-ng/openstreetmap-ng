import { ELEMENT_HISTORY_PAGE_SIZE } from "@utils/config"

export const HISTORY_LIMITS = [
  ...new Set([ELEMENT_HISTORY_PAGE_SIZE, 25, 50, 100]),
].sort((a, b) => a - b)

export const parseHistoryLimit = (raw: string | null) => {
  const value = raw && /^\d+$/.test(raw) ? Number(raw) : NaN
  return HISTORY_LIMITS.includes(value) ? value : ELEMENT_HISTORY_PAGE_SIZE
}

export const changeHistoryLimit = (url: URL, limit: number) => {
  if (!HISTORY_LIMITS.includes(limit)) throw new RangeError("Unsupported history limit")
  if (limit === ELEMENT_HISTORY_PAGE_SIZE) url.searchParams.delete("limit")
  else url.searchParams.set("limit", String(limit))
  // A cursor from the old page size is not valid for a new pagination resource.
  url.searchParams.delete("page")
}
