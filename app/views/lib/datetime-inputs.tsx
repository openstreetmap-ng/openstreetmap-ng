import { primaryLanguage } from "@lib/config"
import { dateTimeFormat, relativeTimeFormat } from "@lib/format"
import { DAY, HOUR, MINUTE, SECOND, WEEK } from "@std/datetime/constants"
import type { CSSProperties } from "preact"

const resolvedElements = new WeakSet<HTMLTimeElement>()

type DateStyle = Intl.DateTimeFormatOptions["dateStyle"]
type TimeStyle = Intl.DateTimeFormatOptions["timeStyle"]
type RelativeStyle = Intl.RelativeTimeFormatOptions["style"]
type RelativeOrDayStyle = RelativeStyle | "day"

type TimeFormatOptions = {
  dateStyle: DateStyle
  timeStyle: TimeStyle
  relativeStyle: RelativeOrDayStyle
}

type TimePropsBase = {
  class?: string
  style?: string | CSSProperties
  dateStyle?: DateStyle
  timeStyle?: TimeStyle
  relativeStyle?: RelativeOrDayStyle
}

const TIME_UNITS = [
  [365 * DAY, "year"],
  [30 * DAY, "month"],
  [WEEK, "week"],
  [DAY, "day"],
  [HOUR, "hour"],
  [MINUTE, "minute"],
] as const

const getDayDiff = (date: Date) => {
  const now = new Date()
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const todayDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((dateDay.getTime() - todayDay.getTime()) / DAY)
}

const getRelativeFormatValueUnit = (date: Date) => {
  const diff = date.getTime() - Date.now()
  const [ms, unit] = TIME_UNITS.find(([ms]) => Math.abs(diff) >= ms) ?? [
    SECOND,
    "second",
  ]
  return [Math.trunc(diff / ms), unit] as const
}

const formatTime = (date: Date, options: TimeFormatOptions) => {
  const { dateStyle, timeStyle, relativeStyle } = options

  if (dateStyle || timeStyle) {
    const text = dateTimeFormat(primaryLanguage, { dateStyle, timeStyle }).format(date)
    const title = dateTimeFormat(primaryLanguage, {
      dateStyle: dateStyle && "long",
      timeStyle: timeStyle && "long",
    }).format(date)
    return { text, title }
  }

  if (relativeStyle === "day") {
    const dayDiff = getDayDiff(date)
    const text = relativeTimeFormat(primaryLanguage, {
      style: "long",
      numeric: "auto",
    }).format(dayDiff, "day")
    const title = dateTimeFormat(primaryLanguage, { dateStyle: "long" }).format(date)
    return { text, title }
  }

  const [diff, unit] = getRelativeFormatValueUnit(date)
  const relativeOptions = relativeStyle ? { style: relativeStyle } : {}
  const text = relativeTimeFormat(primaryLanguage, relativeOptions).format(diff, unit)
  const title = dateTimeFormat(primaryLanguage, {
    dateStyle: "long",
    timeStyle: "long",
  }).format(date)
  return { text, title }
}

const timeFormatOptionsFromDataset = (dataset: DOMStringMap): TimeFormatOptions => ({
  dateStyle: dataset.date as DateStyle,
  timeStyle: dataset.time as TimeStyle,
  relativeStyle: dataset.style as RelativeOrDayStyle,
})

export const Time = (
  props:
    | (TimePropsBase & { unix: number | bigint; date?: never })
    | (TimePropsBase & { date: Date; unix?: never }),
) => {
  const date = props.date ?? new Date(Number(props.unix) * 1000)
  const relativeStyle =
    props.relativeStyle ?? (props.dateStyle || props.timeStyle ? undefined : "long")
  const { title, text } = formatTime(date, {
    dateStyle: props.dateStyle,
    timeStyle: props.timeStyle,
    relativeStyle,
  })
  return (
    <time
      class={props.class}
      style={props.style}
      datetime={date.toISOString()}
      data-date={props.dateStyle}
      data-time={props.timeStyle}
      data-style={relativeStyle}
      title={title}
    >
      {text}
    </time>
  )
}

export const resolveDatetimeLazy = (container: Element) =>
  queueMicrotask(() => {
    for (const element of container.querySelectorAll("time[datetime]")) {
      if (resolvedElements.has(element)) continue
      resolvedElements.add(element)

      const { title, text } = formatTime(
        new Date(element.dateTime),
        timeFormatOptionsFromDataset(element.dataset),
      )
      element.title = title
      element.textContent = text
    }
  })

// Initial update
resolveDatetimeLazy(document.body)
