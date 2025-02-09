// This file is loaded synchronously to avoid theme flashes.
// It doesn't have type="module"/defer to intentionally block the rendering.
// Also, don't use imports to avoid unnecessary polyfills.
const appTheme = localStorage.getItem("theme") || "auto"
const activeTheme =
    appTheme === "auto" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : appTheme
document.documentElement.dataset.bsTheme = activeTheme
