import { themeStorage } from "@lib/local-storage"
import { getDeviceThemePreference } from "@lib/polyfills"

export type AppTheme = "light" | "dark" | "auto"

type ThemeEventHandler = (theme: "light" | "dark") => void

const themeEventHandlers: ThemeEventHandler[] = []

/** Add a theme event handler, called when app theme is changed */
export const addThemeEventHandler = (handler: ThemeEventHandler): number =>
    themeEventHandlers.push(handler)

// Support for pages without a navbar
const control = document.querySelector(".navbar-theme")
if (control) {
    const buttonIcon = control.querySelector(".dropdown-toggle i.bi")
    const themeItemButtonMap = new Map<AppTheme, HTMLButtonElement>()
    const themeIconMap = new Map<AppTheme, string>()
    for (const itemButton of control.querySelectorAll(
        "button.dropdown-item[data-bs-theme-value]",
    )) {
        const key = itemButton.dataset.bsThemeValue as AppTheme
        const iconClass = Array.from(itemButton.querySelector("i.bi").classList).find(
            (c) => c.startsWith("bi-"),
        )
        themeItemButtonMap.set(key, itemButton)
        themeIconMap.set(key, iconClass)
    }

    const updateState = (forceAppTheme?: AppTheme): void => {
        const appTheme = forceAppTheme ?? themeStorage.get()
        const activeTheme = appTheme === "auto" ? getDeviceThemePreference() : appTheme
        console.debug(
            "Updating theme state, preference:",
            appTheme,
            "; active:",
            activeTheme,
        )

        document.documentElement.dataset.bsTheme = activeTheme
        buttonIcon.classList.remove(...themeIconMap.values(), "opacity-0")
        buttonIcon.classList.add(themeIconMap.get(appTheme))
        for (const [theme, itemButton] of themeItemButtonMap) {
            itemButton.classList.toggle("active", theme === appTheme)
        }

        for (const handler of themeEventHandlers) handler(activeTheme)
    }

    // Listen for system color scheme changes
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
        console.debug("Handling system color scheme change")
        updateState()
    })

    for (const [theme, itemButton] of themeItemButtonMap.entries()) {
        itemButton.addEventListener("click", () => {
            if (themeStorage.get() === theme) return
            console.debug("Handling application theme change to", theme)
            themeStorage.set(theme)
            updateState(theme)
        })
    }

    // Initial update
    updateState()
}
