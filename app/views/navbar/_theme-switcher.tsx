import { themeStorage } from "@lib/local-storage"
import type { Theme } from "@lib/theme"
import { useComputed } from "@preact/signals"
import { t } from "i18next"

const THEME_OPTIONS: {
  value: Theme
  icon: string
  label: string
}[] = [
  { value: "light", icon: "bi-sun-fill", label: t("theme.light") },
  { value: "dark", icon: "bi-moon-stars-fill", label: t("theme.dark") },
  { value: "auto", icon: "bi-circle-half", label: t("theme.auto") },
]

export const ThemeSwitcher = () => {
  const buttonIcon = useComputed(
    () => THEME_OPTIONS.find((option) => option.value === themeStorage.value)!.icon,
  )

  return (
    <fieldset
      id="ThemeSwitcher"
      class="btn-group dropdown d-flex d-lg-inline-flex mb-2 mb-lg-0 mx-lg-1"
    >
      <button
        class="btn btn-light text-navbar dropdown-toggle"
        type="button"
        title={t("theme.toggle_theme")}
        aria-expanded="false"
        data-bs-toggle="dropdown"
      >
        <i class={`bi ${buttonIcon.value}`} />
        <span class="d-lg-none ms-2">{t("theme.toggle_theme")}</span>
      </button>

      <ul class="dropdown-menu dropdown-menu-end">
        <li>
          <h6 class="dropdown-item-text">{t("theme.toggle_theme")}</h6>
        </li>
        {THEME_OPTIONS.map((option) => (
          <li>
            <button
              class={`dropdown-item ${option.value === themeStorage.value ? "active" : ""}`}
              type="button"
              onClick={() => (themeStorage.value = option.value)}
            >
              <i class={`bi ${option.icon} me-2`} />
              {option.label}
            </button>
          </li>
        ))}
      </ul>
    </fieldset>
  )
}
