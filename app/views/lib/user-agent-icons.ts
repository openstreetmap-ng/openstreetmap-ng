import Bowser from "bowser"
import { getBrowserIconMap, getOsIconMap } from "./user-agent-icons.macro" with {
    type: "macro",
}

const BROWSER_ICON_MAP = getBrowserIconMap()
const OS_ICON_MAP = getOsIconMap()
const DEVICE_ICON_CLASS: Record<string, string> = {
    mobile: "bi-phone",
    tablet: "bi-tablet",
    desktop: "bi-laptop",
}

/** Populate .ua-icons elements with browser/OS/device icons */
export const configureUserAgentIcons = (container: HTMLElement): void => {
    const icons = container.querySelectorAll<HTMLElement>(".ua-icons[title]")
    console.debug("Initializing", icons.length, "UserAgent icons")

    for (const el of icons) {
        const userAgent = el.title
        const parser = Bowser.getParser(userAgent)

        // Build icons
        const browser = parser.getBrowserName()
        const browserIcon = browser ? BROWSER_ICON_MAP[browser] : null
        if (browserIcon) {
            const img = document.createElement("img")
            img.src = browserIcon
            img.alt = browser
            img.className = "me-1 align-middle"
            el.appendChild(img)
        }

        const os = parser.getOSName()
        const osIcon = os ? OS_ICON_MAP[os] : null
        if (osIcon) {
            const img = document.createElement("img")
            img.src = osIcon
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
}
