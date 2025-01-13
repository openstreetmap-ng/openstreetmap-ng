import { getAppTheme, setAppTheme } from "./_local-storage"

export type AppTheme = "light" | "dark" | "auto"

const control = document.querySelector(".navbar-theme")
const buttonIcon = control.querySelector(".dropdown-toggle i.bi")
const themeItemButtonMap = new Map<AppTheme, HTMLButtonElement>()
const themeIconMap = new Map<AppTheme, string>()
for (const itemButton of control.querySelectorAll("button.dropdown-item[data-bs-theme-value]")) {
    const key = itemButton.dataset.bsThemeValue as AppTheme
    const iconClass = Array.from(itemButton.querySelector("i.bi").classList).find((c) => c.startsWith("bi-"))
    console.debug("Theme", key, "icon:", iconClass)
    themeItemButtonMap.set(key, itemButton)
    themeIconMap.set(key, iconClass)
}

const getDeviceTheme = (): "light" | "dark" =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"

const updateState = (forceAppTheme?: AppTheme): void => {
    const appTheme = forceAppTheme ?? getAppTheme()
    const activeTheme = appTheme === "auto" ? getDeviceTheme() : appTheme
    console.debug("Updating theme state, preference:", appTheme, "active:", activeTheme)

    document.documentElement.dataset.bsTheme = activeTheme
    buttonIcon.classList.remove(...themeIconMap.values())
    buttonIcon.classList.add(themeIconMap.get(appTheme))
    for (const [theme, itemButton] of themeItemButtonMap) {
        itemButton.classList.toggle("active", theme === appTheme)
    }
}

// Listen for system color scheme changes
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    console.debug("onSystemColorSchemeChange")
    updateState()
})

for (const [theme, itemButton] of themeItemButtonMap.entries()) {
    itemButton.addEventListener("click", () => {
        console.debug("onThemeButtonClick", theme)
        setAppTheme(theme)
        updateState(theme)
    })
}

// Initial update
updateState()
