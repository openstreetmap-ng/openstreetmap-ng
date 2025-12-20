import { primaryLanguage } from "@lib/config"
import { tRich } from "@lib/i18n"
import { getLocaleDisplayName, LOCALE_OPTIONS } from "@lib/locale"
import { useComputed, useSignal } from "@preact/signals"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { render } from "preact"
import { useLayoutEffect, useRef } from "preact/hooks"

const GUIDE_HREF =
  "https://wiki.openstreetmap.org/wiki/Website_internationalization#How_to_translate"

const NON_ALPHA_SPACE_RE = /[^a-z\s]/g
const MULTISPACE_RE = /\s+/g

type LocaleEntry = {
  code: string
  english: string
  native: string | null
  flag?: string
  title: string
  search: string
  isPrimary: boolean
}

const normalizeSearch = (value: string) =>
  value
    .toLowerCase()
    .replace(NON_ALPHA_SPACE_RE, " ")
    .replace(MULTISPACE_RE, " ")
    .trim()

const buildLocales = () => {
  const entries = LOCALE_OPTIONS.map((locale) => {
    const [code, english, native, flag] = locale
    const search = normalizeSearch([code, english, native].filter(Boolean).join(" "))
    const entry: LocaleEntry = {
      code,
      english,
      native,
      title: getLocaleDisplayName(locale),
      search,
      isPrimary: code === primaryLanguage,
    }
    if (flag) entry.flag = flag
    return entry
  })

  const primary = entries.find((e) => e.isPrimary)
  return primary ? [primary, ...entries.filter((e) => !e.isPrimary)] : entries
}

const LanguageSwitcherModal = ({ modalInstance }: { modalInstance: () => Modal }) => {
  const modalRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const search = useSignal("")
  const searchNormalized = useComputed(() => normalizeSearch(search.value))

  const locales = useComputed(() => buildLocales())
  const localesFiltered = useComputed(() =>
    searchNormalized.value
      ? locales.value.filter((locale) => locale.search.includes(searchNormalized.value))
      : locales.value,
  )

  useLayoutEffect(() => {
    modalRef.current!.addEventListener("shown.bs.modal", () => {
      searchInputRef.current!.focus()
    })
  }, [])

  const setLanguage = (code: string) => {
    if (code !== primaryLanguage) {
      document.cookie = `lang=${code}; path=/; max-age=31536000; samesite=lax`
      window.location.reload()
      return
    }

    modalInstance().hide()
  }

  return (
    <div
      id="LanguageSwitcherModal"
      class="modal fade"
      tabIndex={-1}
      aria-hidden="true"
      ref={modalRef}
    >
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              {t("language_picker.select_your_preferred_language")}
            </h5>
            <button
              class="btn-close"
              aria-label={t("javascripts.close")}
              type="button"
              data-bs-dismiss="modal"
            />
          </div>

          <div class="modal-body">
            <input
              type="text"
              class="form-control mb-3"
              placeholder={`${t("language_picker.search_languages")}...`}
              autoComplete="off"
              aria-label={t("language_picker.search_languages")}
              value={search.value}
              onInput={(e) => (search.value = e.currentTarget.value)}
              ref={searchInputRef}
            />
            <ul
              class="language-list list-unstyled mb-3"
              aria-live="polite"
            >
              {localesFiltered.value.map((locale) => (
                <li key={locale.code}>
                  <button
                    type="button"
                    title={locale.title}
                    aria-current={locale.isPrimary ? "true" : undefined}
                    onClick={() => setLanguage(locale.code)}
                  >
                    {locale.flag ? <span class="flag">{locale.flag}</span> : null}
                    <span class="name-native">{locale.native ?? locale.english}</span>
                    {locale.native ? (
                      <span class="name-english">{locale.english}</span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>

            <p class="form-text mb-0">
              {tRich("internalization.get_started", {
                this_guide: () => (
                  <a
                    href={GUIDE_HREF}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("internalization.this_guide")}
                  </a>
                ),
              })}
            </p>
          </div>

          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {t("javascripts.close")}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export const LanguageSwitcher = () => {
  const modalInstanceRef = useRef<Modal | null>(null)

  const ensureModal = () => {
    if (modalInstanceRef.current) {
      return modalInstanceRef.current
    }

    const modalRoot = document.createElement("div")
    document.body.append(modalRoot)
    render(<LanguageSwitcherModal modalInstance={() => modalInstance} />, modalRoot)

    const modalElement = modalRoot.querySelector(".modal")!
    const modalInstance = Modal.getOrCreateInstance(modalElement)
    modalInstanceRef.current = modalInstance
    return modalInstance
  }

  const showModal = () => {
    ensureModal().show()
  }

  return (
    <div
      id="LanguageSwitcher"
      class="d-flex d-lg-inline-flex mt-2 mt-lg-0 ms-lg-1"
    >
      <button
        class="btn btn-light btn-bg-initial navbar-color w-100"
        type="button"
        title={t("settings.choose_language")}
        onClick={showModal}
      >
        <i class="bi bi-translate" />
        <span class="d-lg-none ms-2">{t("settings.choose_language")}</span>
      </button>
    </div>
  )
}
