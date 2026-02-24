import { polylineDecode } from "@lib/polyline"
import { useMemo } from "preact/hooks"

const TRACE_SEGMENT_LENGTH = 50
const TRACE_SPEED = 120

const getTracePath = (line: string, precision: number) => {
  const coords = polylineDecode(line, precision)
  if (!coords.length) return null

  let pathLength = 0
  let pathData = `M${coords[0][0]},${coords[0][1]}`
  for (let i = 1; i < coords.length; i++) {
    const [x, y] = coords[i]
    const [prevX, prevY] = coords[i - 1]
    pathLength += Math.hypot(x - prevX, y - prevY)
    pathData += ` L${x},${y}`
  }

  return { pathData, pathLength }
}

export const TraceLinePreview = ({
  href,
  line,
  precision = 0,
  animate = false,
  class: className = "",
}: {
  href: string
  line: string
  precision?: number
  animate?: boolean
  class?: string
}) => {
  const tracePath = useMemo(() => getTracePath(line, precision), [line, precision])

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
                  dur={`${Math.max(tracePath.pathLength / TRACE_SPEED, 0.2)}s`}
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
