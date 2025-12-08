import Bowser from "bowser"
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

/** Populate .ua-icons elements with browser/OS/device icons */
export const resolveUserAgentIconsLazy = (container: HTMLElement) => {
    queueMicrotask(() => {
        const icons = container.querySelectorAll<HTMLElement>(".ua-icons[title]")
        console.debug("Initializing", icons.length, "UserAgent icons")

        for (const el of icons) {
            const userAgent = el.title
            const parser = Bowser.getParser(userAgent)

            // Build icons
            const browser = parser.getBrowserName()
            const browserSuffix = browser ? BROWSER_ICON_MAP[browser] : null
            if (browserSuffix) {
                const img = document.createElement("img")
                img.src = BROWSER_PREFIX + browserSuffix
                img.alt = browser
                img.className = "me-1 align-middle"
                el.appendChild(img)
            }

            const os = parser.getOSName()
            const osSuffix = os ? OS_ICON_MAP[os] : null
            if (osSuffix) {
                const img = document.createElement("img")
                img.src = OS_PREFIX + osSuffix
                img.alt = os
                img.className = "ua-os-icon me-1 align-middle"
                el.appendChild(img)
            }

            const platformType = parser.getPlatformType()
            const deviceClass = DEVICE_ICON_CLASS[platformType] ?? "bi-display"
            const deviceIcon = document.createElement("i")
            deviceIcon.className = `bi ${deviceClass} align-middle`
            el.appendChild(deviceIcon)
        }
    })
}
