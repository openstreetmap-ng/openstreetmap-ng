import { formatMonthName, formatShortDate, formatWeekdayName } from "@lib/format"
import type { Page_ActivityChartValid } from "@lib/proto/profile_pb"
import { DAY } from "@std/datetime/constants"
import { Tooltip } from "bootstrap"
import { t } from "i18next"
import { useRef } from "preact/hooks"

type ActivityDay = {
  iso: string
  level: number
  value: number
  week: number
  weekday: number
}

type ActivityWeek = {
  key: string
  label: string
}

type ActivityWeekRow = {
  key: string
  label: string
  days: readonly ActivityDay[]
}

const WEEKDAY_COUNT = 7
const WEEKS_PER_MONTH = 52 / 12

const activityLevel = (value: number, maxActivityClip: number) =>
  Math.ceil(Math.min(value / maxActivityClip, 1) * 19)

const getActivityMetrics = (chart: Page_ActivityChartValid) => {
  let activitySum = 0
  let activityMax = 0
  let activityDays = 0

  for (const value of chart.values) {
    activitySum += value
    if (value > activityMax) activityMax = value
    if (value) activityDays += 1
  }

  return { activitySum, activityMax, activityDays }
}

const getActivitySummaryMonths = (chart: Page_ActivityChartValid) =>
  Math.max(1, Math.round(chart.values.length / WEEKDAY_COUNT / WEEKS_PER_MONTH))

const buildActivityDays = (chart: Page_ActivityChartValid) => {
  const dayMs = DAY
  const startMs = chart.startDay * dayMs
  const totalWeeks = Math.ceil(chart.values.length / WEEKDAY_COUNT)

  const monthLabels = Array.from({ length: totalWeeks }, () => "")
  const weekStarts = Array.from({ length: totalWeeks }, () => "")

  const days: ActivityDay[] = chart.values.map((value, index) => {
    const date = new Date(startMs + index * dayMs)
    const iso = date.toISOString().slice(0, 10)
    const week = Math.floor(index / WEEKDAY_COUNT)

    if (date.getUTCDate() === 1) {
      monthLabels[week] = formatMonthName(iso, "short")
    }

    return {
      iso,
      level: activityLevel(value, chart.maxActivityClip),
      value,
      week,
      weekday: index % WEEKDAY_COUNT,
    }
  })

  for (const day of days) {
    if (!weekStarts[day.week]) {
      weekStarts[day.week] = day.iso
    }
  }

  const weekRows = Array.from({ length: WEEKDAY_COUNT }, () => [] as ActivityDay[])
  for (const day of days) {
    weekRows[day.weekday].push(day)
  }

  const weeks: ActivityWeek[] = monthLabels.map((label, week) => ({
    key: weekStarts[week],
    label,
  }))

  const rows: ActivityWeekRow[] = weekRows.map((daysInWeekday, weekday) => ({
    key: `weekday-${weekday}`,
    label:
      weekday % 2 === 1
        ? formatWeekdayName(new Date(startMs + weekday * dayMs).toISOString(), "short")
        : "",
    days: daysInWeekday,
  }))

  return { weeks, rows }
}

const ActivityCell = ({
  day,
  hrefPrefix,
}: {
  day: ActivityDay
  hrefPrefix: string
}) => {
  const initialized = useRef(false)

  const activateTooltip = (element: HTMLElement) => {
    if (initialized.current) return
    initialized.current = true

    const dateLabel = formatShortDate(day.iso)
    const title =
      day.value > 0
        ? t("user.activity.details.count", {
            count: day.value,
            date: dateLabel,
          })
        : t("user.activity.details.no_activity", {
            date: dateLabel,
          })

    new Tooltip(element, { customClass: "activity-tooltip", title })
  }

  const onActivate = (event: Event & { currentTarget: HTMLElement }) =>
    activateTooltip(event.currentTarget)

  const commonProps = {
    class: `activity activity-${day.level}`,
    onPointerEnter: onActivate,
    onFocus: onActivate,
  }

  return day.value ? (
    <a
      href={`${hrefPrefix}${day.iso}`}
      aria-label={`${day.iso}: ${day.value}`}
      {...commonProps}
    />
  ) : (
    <div
      aria-label={`${day.iso}: ${day.value}`}
      {...commonProps}
    />
  )
}

const ProfileActivityChart = ({
  chart,
  displayName,
}: {
  chart: Page_ActivityChartValid
  displayName: string
}) => {
  const { weeks, rows } = buildActivityDays(chart)
  const hrefPrefix = `/user/${encodeURIComponent(displayName)}/history?date=`

  return (
    <table class="activity-chart mb-2">
      <tbody>
        <tr
          class="months-row"
          aria-hidden="true"
        >
          <td class="month-cell" />
          {weeks.map((week) => (
            <td
              key={week.key}
              class="month-cell"
            >
              {week.label}
            </td>
          ))}
        </tr>

        {rows.map((row) => (
          <tr key={row.key}>
            <td
              class="week-cell"
              aria-hidden="true"
            >
              {row.label}
            </td>
            {row.days.map((day) => (
              <td key={day.iso}>
                <ActivityCell
                  day={day}
                  hrefPrefix={hrefPrefix}
                />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export const ProfileActivity = ({
  chart,
  displayName,
}: {
  chart: Page_ActivityChartValid
  displayName: string
}) => {
  const { activityDays, activitySum, activityMax } = getActivityMetrics(chart)
  const statisticsUrl = `/user/${encodeURIComponent(displayName)}/statistics`
  const mappingDay = t("user.activity.mapping_day.count", { count: activityDays })
  const numChangesets = `${activitySum} ${t("changeset.count", { count: activitySum })}`
  const lastNMonths = t("user.activity.last_n_months.count", {
    count: getActivitySummaryMonths(chart),
  })
  const summary = t("user.activity.summary", {
    mapping_day: mappingDay,
    num_changesets: numChangesets,
    last_n_months: lastNMonths,
  })

  return (
    <>
      <h3 class="ms-1">{t("user.activity.recent")}</h3>
      <p class="mb-2">{summary}</p>

      <ProfileActivityChart
        chart={chart}
        displayName={displayName}
      />

      <div class="d-flex justify-content-between small">
        <div>
          <a
            class="me-1"
            href={statisticsUrl}
          >
            {t("user.activity.view_all")}
            <i class="bi bi-box-arrow-up-right ms-2" />
          </a>
        </div>
        <div class="text-muted">
          {t("user.activity.less")} (0)
          <span class="inline-activity activity activity-0" />
          <span class="inline-activity activity activity-6" />
          <span class="inline-activity activity activity-12" />
          <span class="inline-activity activity activity-19" />{" "}
          {t("user.activity.more")} ({activityMax})
        </div>
      </div>
    </>
  )
}
