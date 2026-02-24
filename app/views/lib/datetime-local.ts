import { SECOND } from "@std/datetime/constants"
import { format as formatDatetime } from "@std/datetime/format"
import { parse as parseDatetime } from "@std/datetime/parse"

const DATETIME_LOCAL_FORMAT = "yyyy-MM-dd'T'HH:mm"

export const unixToLocalDatetime = (unix: bigint | number | undefined) => {
  if (unix === undefined) return ""
  return formatDatetime(new Date(Number(unix) * SECOND), DATETIME_LOCAL_FORMAT)
}

export const localDatetimeToUnix = (value: string) =>
  value
    ? BigInt(Math.floor(parseDatetime(value, DATETIME_LOCAL_FORMAT).getTime() / SECOND))
    : undefined
