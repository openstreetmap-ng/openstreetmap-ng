import { polylineDecode } from "@lib/polyline"
import { type SummaryValid, Visibility } from "@lib/proto/trace_pb"
import { useSignal } from "@preact/signals"
import { assertNever } from "@std/assert/unstable-never"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { useMemo } from "preact/hooks"
import { traceMotionDuration } from "./_motion"

const TRACE_SEGMENT_LENGTH = 50
const TRACE_SPEED = 120

const getPath = (line: string, precision: number) => {
  const coords = polylineDecode(line, precision)
  if (!coords.length) return null

  let pathLength = 0
  let pathData = `M${coords[0]![0]},${coords[0]![1]}`
  for (let i = 1; i < coords.length; i++) {
    const [x, y] = coords[i]!
    const [prevX, prevY] = coords[i - 1]!
    pathLength += Math.hypot(x - prevX, y - prevY)
    pathData += ` L${x},${y}`
  }

  return { pathData, pathLength }
}

const getVisibilityMeta = (visibility: Visibility) => {
  switch (visibility) {
    case Visibility.identifiable:
      return {
        className: "text-bg-green",
        iconClass: "bi-eye",
        label: toSentenceCase(t("traces.trace.identifiable")),
      }
    case Visibility.public:
      return {
        className: "text-bg-green",
        iconClass: "bi-eye",
        label: toSentenceCase(t("traces.trace.public")),
      }
    case Visibility.trackable:
      return {
        className: "text-bg-danger",
        iconClass: "bi-eye-slash",
        label: toSentenceCase(t("traces.trace.trackable")),
      }
    case Visibility.private:
      return {
        className: "text-bg-danger",
        iconClass: "bi-eye-slash",
        label: toSentenceCase(t("traces.trace.private")),
      }
    default:
      assertNever(visibility)
  }
}

const LinePreview = ({
  class: className,
  href,
  line,
  animate,
}: {
  class: string
  href: string
  line: string
  animate: boolean
}) => {
  const tracePath = useMemo(() => getPath(line, 0), [line])

  return (
    <a
      class={className}
      href={href}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="92"
        height="92"
        viewBox="-1 -1 92 92"
      >
        {tracePath &&
          (animate && tracePath.pathLength > 0 ? (
            <>
              <path
                d={tracePath.pathData}
                fill="none"
                stroke="#aaa"
                strokeWidth="0.45"
                strokeLinecap="round"
              />
              <path
                d={tracePath.pathData}
                fill="none"
                stroke="var(--bs-body-color)"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeDasharray={`${TRACE_SEGMENT_LENGTH} ${tracePath.pathLength}`}
              >
                <animate
                  attributeName="stroke-dashoffset"
                  values={`0;${-tracePath.pathLength - TRACE_SEGMENT_LENGTH}`}
                  dur={`${traceMotionDuration(Math.max(tracePath.pathLength / TRACE_SPEED, 0.2))}s`}
                  repeatCount="indefinite"
                  fill="freeze"
                />
              </path>
            </>
          ) : (
            <path
              d={tracePath.pathData}
              fill="none"
              stroke="var(--bs-body-color)"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          ))}
      </svg>
    </a>
  )
}

const VisibilityBadge = ({ visibility }: { visibility: Visibility }) => {
  const meta = getVisibilityMeta(visibility)

  return (
    <span class={`stat-visibility ${meta.className}`}>
      <i class={`bi ${meta.iconClass}`} />
      {meta.label}
    </span>
  )
}

const SummaryBody = ({
  description,
  tags,
  visibility,
  size,
  tagBasePath,
  showPointIcon = false,
}: {
  description: string
  tags: readonly string[]
  visibility: Visibility
  size: number
  tagBasePath: string
  showPointIcon?: boolean
}) => (
  <div class="body">
    <p class="mb-0">
      <span class="fst-italic me-1">{description}</span>
      {tags.map((tag) => (
        <a
          key={tag}
          class="hashtag"
          href={`${tagBasePath}/tag/${encodeURIComponent(tag)}`}
        >
          #{tag}
        </a>
      ))}
    </p>
    <div class="trace-stats">
      <VisibilityBadge visibility={visibility} />
      <span class="stat-points text-bg-secondary">
        {showPointIcon && <i class="bi bi-geo-alt" />}
        {t("traces.trace.count_points", { count: size })}
      </span>
    </div>
  </div>
)

export const SummaryCard = ({
  summary,
  tagBasePath,
  header,
  title,
  clickable = false,
  showPointIcon = false,
}: {
  summary: Pick<SummaryValid, "description" | "tags" | "visibility" | "size">
  tagBasePath: string
  header: ComponentChildren
  title?: ComponentChildren
  clickable?: boolean
  showPointIcon?: boolean
}) => (
  <div class={`social-entry ${clickable ? "clickable h-100" : ""}`}>
    <div class={`header text-muted ${title ? "d-flex justify-content-between" : ""}`}>
      <div>{header}</div>
      {title && <div>{title}</div>}
    </div>
    <SummaryBody
      description={summary.description}
      tags={summary.tags}
      visibility={summary.visibility}
      size={summary.size}
      tagBasePath={tagBasePath}
      showPointIcon={showPointIcon}
    />
  </div>
)

export const SummaryRow = ({
  summary,
  href,
  tagBasePath,
  header,
  title,
  sideAction,
  showPointIcon = false,
}: {
  summary: SummaryValid
  href: string
  tagBasePath: string
  header: ComponentChildren
  title: ComponentChildren
  sideAction?: ComponentChildren
  showPointIcon?: boolean
}) => {
  const previewAnimated = useSignal(false)

  return (
    <li class="row g-2">
      <LinePreview
        class="col-auto"
        href={href}
        line={summary.previewLine}
        animate={previewAnimated.value}
      />
      <div class="col">
        <div
          onPointerEnter={() => (previewAnimated.value = true)}
          onPointerLeave={() => (previewAnimated.value = false)}
          onFocusIn={() => (previewAnimated.value = true)}
          onFocusOut={(e) => {
            const nextTarget = e.relatedTarget
            if (nextTarget instanceof Node && e.currentTarget.contains(nextTarget)) {
              return
            }
            previewAnimated.value = false
          }}
        >
          <SummaryCard
            summary={summary}
            tagBasePath={tagBasePath}
            header={header}
            title={title}
            clickable
            showPointIcon={showPointIcon}
          />
        </div>
      </div>
      {sideAction && <div class="col-auto d-none d-md-block">{sideAction}</div>}
    </li>
  )
}
