import { themeStorage } from "@lib/local-storage"
import { type AppTheme, activeTheme, refreshActiveTheme } from "@lib/theme"
import { effect } from "@preact/signals-core"

// Support for pages without a navbar
const control = document.querySelector(".navbar-theme")
if (control) {
    const buttonIcon = control.querySelector(".dropdown-toggle i.bi")!
    const themeItemButtonMap = new Map<AppTheme, HTMLButtonElement>()
    const themeIconMap = new Map<AppTheme, string>()
    for (const itemButton of control.querySelectorAll(
        "button.dropdown-item[data-bs-theme-value]",
    )) {
        const key = itemButton.dataset.bsThemeValue as AppTheme
        const iconClass = Array.from(itemButton.querySelector("i.bi")!.classList).find(
            (c) => c.startsWith("bi-"),
        )!
        themeItemButtonMap.set(key, itemButton)
        themeIconMap.set(key, iconClass)
    }

    // React to theme changes
    effect(() => {
        const theme = activeTheme.value
        const appTheme = themeStorage.get()
        console.debug("NavbarTheme: Updating state", {
            preference: appTheme,
            active: theme,
        })

        document.documentElement.dataset.bsTheme = theme
        buttonIcon.classList.remove(...themeIconMap.values(), "opacity-0")
        buttonIcon.classList.add(themeIconMap.get(appTheme)!)
        for (const [t, itemButton] of themeItemButtonMap) {
            itemButton.classList.toggle("active", t === appTheme)
        }
    })

    for (const [theme, itemButton] of themeItemButtonMap.entries()) {
        itemButton.addEventListener("click", () => {
            if (themeStorage.get() === theme) return
            console.debug("NavbarTheme: Change requested", theme)
            themeStorage.set(theme)
            refreshActiveTheme()
        })
    }
}
