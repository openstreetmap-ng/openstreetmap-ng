import { signal } from "@preact/signals-core"
import { themeStorage } from "./local-storage"
import { getDeviceThemePreference } from "./polyfills"

export type AppTheme = "light" | "dark" | "auto"

/** Compute the active theme from app theme setting */
const computeActiveTheme = (appTheme: AppTheme) =>
    appTheme === "auto" ? getDeviceThemePreference() : appTheme

/** The currently active theme (resolved from user preference or system setting) */
export const activeTheme = signal(computeActiveTheme(themeStorage.get()))

/** Update active theme from current storage value */
export const refreshActiveTheme = () => {
    activeTheme.value = computeActiveTheme(themeStorage.get())
}

// Listen for system color scheme changes
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    console.debug("Theme: System preference changed")
    refreshActiveTheme()
})
