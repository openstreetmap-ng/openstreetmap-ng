import { themeStorage } from "@lib/local-storage"
import type { Theme } from "@lib/theme"
import { useComputed } from "@preact/signals"
import { t } from "i18next"

type ThemeOption = {
  value: Theme
  icon: string
  label: string
}

const themeOptions: ThemeOption[] = [
  { value: "light", icon: "bi-sun-fill", label: t("theme.light") },
  { value: "dark", icon: "bi-moon-stars-fill", label: t("theme.dark") },
  { value: "auto", icon: "bi-circle-half", label: t("theme.auto") },
]

const BUTTON_LABEL = t("theme.toggle_theme")

export const ThemeSwitcher = () => {
  const buttonIcon = useComputed(
    () => themeOptions.find((o) => o.value === themeStorage.value)!.icon,
  )

  return (
    <fieldset
      id="ThemeSwitcher"
      class="btn-group dropdown d-flex d-lg-inline-flex mb-2 mb-lg-0 mx-lg-1"
    >
      <button
        class="btn btn-light text-navbar dropdown-toggle"
        type="button"
        title={BUTTON_LABEL}
        aria-expanded="false"
        data-bs-toggle="dropdown"
      >
        <i class={`bi ${buttonIcon.value}`} />
        <span class="d-lg-none ms-2">{BUTTON_LABEL}</span>
      </button>

      <ul class="dropdown-menu dropdown-menu-end">
        <li>
          <h6 class="dropdown-item-text">{BUTTON_LABEL}</h6>
        </li>
        {themeOptions.map((option) => (
          <li key={option.value}>
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
