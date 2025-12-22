import { primaryLanguage } from "@lib/config"
import { dateTimeFormat, relativeTimeFormat } from "@lib/format"
import { assert } from "@std/assert"
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

type TimeProps =
  | (TimePropsBase & { unix: number | bigint; date?: never })
  | (TimePropsBase & { date: Date; unix?: never })

const TIME_UNITS = [
  [365 * DAY, "year"],
  [30 * DAY, "month"],
  [WEEK, "week"],
  [DAY, "day"],
  [HOUR, "hour"],
  [MINUTE, "minute"],
] as const

const getDayDiff = (date: Date): number => {
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
  return [(diff / ms) | 0, unit] as const
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

export const Time = (props: TimeProps) => {
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

const utcStringToLocalInputValue = (utcDateString: string): number => {
  const utcDate = new Date(utcDateString)
  const ms = utcDate.getTime()
  assert(!Number.isNaN(ms), `Invalid UTC datetime string: ${utcDateString}`)

  // datetime-local defaults to minute precision; keep behavior stable by truncating.
  return ms - (ms % MINUTE)
}

const localInputToUtcString = (input: HTMLInputElement): string => {
  if (input.value === "") return ""
  const ms = input.valueAsNumber
  assert(!Number.isNaN(ms), `Invalid datetime-local value: ${input.value}`)
  return new Date(ms).toISOString()
}

/**
 * Setup timezone conversion for datetime-local inputs in a form.
 * This function:
 * 1. Converts any existing UTC values to local time for display
 * 2. Creates hidden inputs that are automatically updated with UTC values
 * 3. Removes the name attribute from visible inputs to prevent direct submission
 *
 * @param form - The form element containing datetime-local inputs
 * @param datetimeInputNames - Array of input names to handle
 */
export const configureDatetimeInputs = (
  form: HTMLFormElement,
  datetimeInputNames: string[],
) => {
  for (const inputName of datetimeInputNames) {
    const input = form.querySelector(`input[type=datetime-local][name="${inputName}"]`)
    assert(input, `Missing datetime-local input: ${inputName}`)

    // Remove name from visible input so it doesn't get submitted
    input.removeAttribute("name")

    // Create hidden input that will hold the UTC value for submission
    const hiddenInput = document.createElement("input")
    hiddenInput.type = "hidden"
    hiddenInput.name = inputName
    input.after(hiddenInput)

    // Update hidden input whenever visible input changes
    const sync = () => {
      hiddenInput.value = localInputToUtcString(input)
    }
    input.addEventListener("input", sync)

    // Convert existing UTC value to local time for display
    const dataValue = input.dataset.value
    if (dataValue) input.valueAsNumber = utcStringToLocalInputValue(dataValue)
    input.removeAttribute("data-value")
    sync()
  }
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
