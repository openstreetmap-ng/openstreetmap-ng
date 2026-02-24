import { useDisposeEffect } from "@lib/dispose-scope"
import { useSignal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { getBrowserIconMap, getOsIconMap } from "./user-agent-icons.macro" with {
  type: "macro",
}

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

const renderUserAgentIcons = (
  element: HTMLElement,
  state: Readonly<UserAgentIconsState>,
) => {
  const children: Element[] = []

  if (state.browserSrc) {
    const img = document.createElement("img")
    img.src = state.browserSrc
    img.alt = state.browserAlt ?? ""
    img.className = "me-1 align-middle"
    children.push(img)
  }

  if (state.osSrc) {
    const img = document.createElement("img")
    img.src = state.osSrc
    img.alt = state.osAlt ?? ""
    img.className = "ua-os-icon me-1 align-middle"
    children.push(img)
  }

  const deviceIcon = document.createElement("i")
  deviceIcon.className = `bi ${state.deviceClass} align-middle`
  children.push(deviceIcon)

  element.replaceChildren(...children)
}

/** Populate .ua-icons elements with browser/OS/device icons */
export const resolveUserAgentIconsLazy = (container: HTMLElement) => {
  queueMicrotask(async () => {
    const icons = container.querySelectorAll<HTMLElement>(".ua-icons[title]")
    if (!icons.length) return

    const userAgentSet = new Set(
      Array.from(icons, (icon) => icon.title).filter(Boolean),
    )

    const iconEntries: (readonly [string, UserAgentIconsState])[] = await Promise.all(
      Array.from(userAgentSet, async (userAgent) => [
        userAgent,
        await parseUserAgentIcons(userAgent),
      ]),
    )
    const iconMap = new Map<string, UserAgentIconsState>(iconEntries)

    for (const icon of icons) {
      const next = iconMap.get(icon.title)
      if (next) renderUserAgentIcons(icon, next)
    }
  })
}

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
