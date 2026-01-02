import { computed, effect, signal } from "@preact/signals"
import { themeStorage } from "./local-storage"

type PrefersColorScheme = "light" | "dark"

export type Theme = PrefersColorScheme | "auto"

const getPrefersColorScheme = () =>
  window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"

const prefersColorScheme = signal<PrefersColorScheme>(getPrefersColorScheme())

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  console.debug("Theme: System preference changed")
  prefersColorScheme.value = getPrefersColorScheme()
})

export const effectiveTheme = computed(() =>
  themeStorage.value === "auto" ? prefersColorScheme.value : themeStorage.value,
)

effect(() => {
  document.documentElement.dataset.bsTheme = effectiveTheme.value
})
