import { useDisposeEffect } from "@lib/dispose-scope"
import { useSignal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import {
  getBrowserIconMap,
  getOsIconMap,
} from "./user-agent-icons.macro" with { type: "macro" }

const { prefix: BROWSER_PREFIX, map: BROWSER_ICON_MAP } = getBrowserIconMap()
const { prefix: OS_PREFIX, map: OS_ICON_MAP } = getOsIconMap()
const DEVICE_ICON_CLASS: Record<string, string> = {
  mobile: "bi-phone",
  tablet: "bi-tablet",
  desktop: "bi-laptop",
}

type UserAgentIconsState = {
  browserSrc: string | undefined
  browserAlt: string | undefined
  osSrc: string | undefined
  osAlt: string | undefined
  deviceClass: string
}

const loadBowser = memoize(async () => (await import("bowser")).default)

const parseUserAgentIcons = memoize(async (userAgent: string) => {
  const Bowser = await loadBowser()
  const parser = Bowser.getParser(userAgent)

  const browser = parser.getBrowserName()
  const browserSuffix = browser ? BROWSER_ICON_MAP[browser] : undefined

  const os = parser.getOSName()
  const osSuffix = os ? OS_ICON_MAP[os] : undefined

  const platformType = parser.getPlatformType()
  const deviceClass = DEVICE_ICON_CLASS[platformType] ?? "bi-display"

  return {
    browserSrc: browserSuffix ? BROWSER_PREFIX + browserSuffix : undefined,
    browserAlt: browser,
    osSrc: osSuffix ? OS_PREFIX + osSuffix : undefined,
    osAlt: os,
    deviceClass,
  } satisfies UserAgentIconsState
})

export const UserAgentIcons = ({
  userAgent,
  class: className = "",
}: {
  userAgent: string
  class?: string
}) => {
  const state = useSignal<UserAgentIconsState | undefined>()

  useDisposeEffect(
    (scope) => {
      state.value = undefined
      void (async () => {
        const next = await parseUserAgentIcons(userAgent)
        if (scope.signal.aborted) return
        state.value = next
      })()
    },
    [userAgent],
  )

  const current = state.value

  return (
    <span
      class={`ua-icons ${className}`}
      title={userAgent}
    >
      {current?.browserSrc && (
        <img
          src={current.browserSrc}
          alt={current.browserAlt}
          class="me-1 align-middle"
        />
      )}
      {current?.osSrc && (
        <img
          src={current.osSrc}
          alt={current.osAlt}
          class="ua-os-icon me-1 align-middle"
        />
      )}
      <i class={`bi ${current?.deviceClass ?? "bi-display"} align-middle`} />
    </span>
  )
}
