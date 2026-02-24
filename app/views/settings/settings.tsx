import { config, URLSAFE_BLACKLIST, URLSAFE_BLACKLIST_RE } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { tRich } from "@lib/i18n"
import { getLocaleDisplayName, LOCALE_OPTIONS } from "@lib/locale"
import { PageSchema, Service } from "@lib/proto/settings_pb"
import { mountProtoPage } from "@lib/proto-page"
import { StandardForm } from "@lib/standard-form"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { t } from "i18next"
import { useEffect, useRef } from "preact/hooks"
import { SettingsNav } from "./_nav"

mountProtoPage(PageSchema, ({ email, language, passwordUpdatedAt }) => {
  const displayNameInputRef = useRef<HTMLInputElement>(null)

  const syncDisplayNameValidity = () => {
    const displayNameInput = displayNameInputRef.current!
    const message = URLSAFE_BLACKLIST_RE.test(displayNameInput.value)
      ? t("validations.url_characters", {
          characters: URLSAFE_BLACKLIST,
          interpolation: { escapeValue: false },
        })
      : ""
    displayNameInput.setCustomValidity(message)
  }

  useEffect(syncDisplayNameValidity, [])

  return (
    <>
      <div class="content-header">
        <h1 class="container">{toSentenceCase(t("accounts.edit.my settings"))}</h1>
      </div>

      <div class="content-body">
        <div class="container">
          <div class="row">
            <div class="col-lg-auto mb-4">
              <SettingsNav />
            </div>

            <div class="col-lg">
              <h3 class="mb-3">{t("settings.main_settings")}</h3>
              <StandardForm
                method={Service.method.updateSettings}
                buildRequest={({ formData }) => ({
                  displayName: formData.get("display_name") as string,
                  language: formData.get("language") as string,
                  activityTracking: formData.get("activity_tracking") === "true",
                  crashReporting: formData.get("crash_reporting") === "true",
                })}
                onSuccess={() => window.location.reload()}
                class="settings-form"
              >
                <label class="form-label d-block mb-3">
                  {toSentenceCase(t("activerecord.attributes.user.display_name"))}
                  <input
                    type="text"
                    class="form-control mt-2"
                    name="display_name"
                    defaultValue={config.userConfig!.user.displayName}
                    autocapitalize="none"
                    required
                    ref={displayNameInputRef}
                    onInput={syncDisplayNameValidity}
                  />
                </label>

                <label class="form-label d-block">
                  {toSentenceCase(t("passwords.new.email address"))}
                  <div class="input-group mt-2">
                    <input
                      type="email"
                      class="form-control bg-body-tertiary"
                      value={email}
                      readOnly
                    />
                    <a
                      class="btn btn-soft"
                      href="/settings/email"
                    >
                      {t("settings.change_email")}
                    </a>
                  </div>
                </label>
                <p class="form-text">
                  {t("settings.your_email_address_is_not_displayed_publicly")}
                </p>

                <label class="form-label d-block mb-3">
                  {t("settings.password_last_changed")}
                  <div class="input-group mt-2">
                    <div class="form-control bg-body-tertiary">
                      <Time
                        unix={passwordUpdatedAt}
                        relativeStyle="long"
                      />
                    </div>
                    <a
                      class="btn btn-soft"
                      href="/settings/security"
                    >
                      {t("settings.change_password")}
                    </a>
                  </div>
                </label>

                <label class="form-label d-block">
                  {t("settings.preferred_language")}
                  <select
                    class="form-select format-select mt-2"
                    name="language"
                    defaultValue={language}
                    required
                  >
                    {LOCALE_OPTIONS.map((locale) => (
                      <option
                        key={locale[0]}
                        value={locale[0]}
                      >
                        {getLocaleDisplayName(locale, true)}
                      </option>
                    ))}
                  </select>
                </label>
                <p class="form-text mb-3">
                  {tRich("internalization.get_started", {
                    this_guide: (
                      <a href="https://wiki.openstreetmap.org/wiki/Website_internationalization#How_to_translate">
                        {t("internalization.this_guide")}
                      </a>
                    ),
                  })}
                </p>

                <div class="form-check ms-1">
                  <label class="form-check-label d-block">
                    <input
                      class="form-check-input"
                      type="checkbox"
                      name="activity_tracking"
                      value="true"
                      defaultChecked={config.userConfig!.activityTracking}
                    />
                    <i class="bi bi-graph-up text-primary" />
                    {t("privacy.enable_activity_tracking.title")}
                  </label>
                </div>
                <p class="form-text mb-3">
                  {t("privacy.enable_activity_tracking.description")}{" "}
                  {t("privacy.enable_activity_tracking.we_use_matomo")}
                </p>

                <div class="form-check ms-1">
                  <label class="form-check-label d-block">
                    <input
                      class="form-check-input"
                      type="checkbox"
                      name="crash_reporting"
                      value="true"
                      defaultChecked={config.userConfig!.crashReporting}
                    />
                    <i class="bi bi-bug text-primary" />
                    {t("privacy.enable_crash_reporting.title")}
                  </label>
                </div>
                <p class="form-text mb-3">
                  {t("privacy.enable_crash_reporting.description")}
                </p>

                <div class="text-end">
                  <button
                    class="btn btn-primary px-3"
                    type="submit"
                  >
                    {t("action.save_changes")}
                  </button>
                </div>
              </StandardForm>

              <hr class="my-4" />

              <h3 class="mb-3">{t("report.account_support")}</h3>
              <p class="form-text">{t("report.account_support_description")}</p>
              <button
                class="btn btn-outline-secondary"
                type="button"
                data-report-type="user"
                data-report-type-id={config.userConfig!.user.id.toString()}
                data-report-action="user_account"
              >
                <i class="bi bi-flag me-1" />
                {t("report.report_problem")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
})
