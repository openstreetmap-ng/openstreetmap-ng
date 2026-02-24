import { config, EMAIL_MAX_LENGTH, EMAIL_MIN_LENGTH } from "@lib/config"
import { mountProtoPage } from "@lib/proto-page"
import { EmailPageSchema, Service } from "@lib/proto/settings_pb"
import { StandardForm } from "@lib/standard-form"
import { t } from "i18next"
import { SettingsNav } from "./_nav"

mountProtoPage(EmailPageSchema, ({ email }) => (
  <>
    <div class="content-header">
      <h1 class="container">{t("settings.email_settings")}</h1>
    </div>

    <div class="content-body">
      <div class="container">
        <div class="row">
          <div class="col-lg-auto mb-4">
            <SettingsNav />
          </div>

          <div class="col-lg">
            <h3 class="mb-3">{t("settings.change_email")}</h3>
            <StandardForm
              method={Service.method.updateEmail}
              buildRequest={({ formData, passwords }) => ({
                email: formData.get("email") as string,
                password: passwords.password,
              })}
              resetOnSuccess
            >
              <input
                type="text"
                name="display_name"
                value={config.userConfig!.user.displayName}
                autoComplete="username"
                readOnly
                hidden
              />

              <label class="form-label d-block mb-3">
                {t("settings.current_email_address")}
                <input
                  type="email"
                  class="form-control bg-body-tertiary mt-2"
                  value={email}
                  readOnly
                />
              </label>

              <label class="form-label d-block">
                <span class="required">{t("settings.new_email_address")}</span>
                <input
                  type="email"
                  class="form-control mt-2"
                  name="email"
                  minLength={EMAIL_MIN_LENGTH}
                  maxLength={EMAIL_MAX_LENGTH}
                  autoComplete="email"
                  required
                />
              </label>
              <p class="form-text">
                {t("settings.your_email_address_is_not_displayed_publicly")}
              </p>

              <label class="form-label d-block">
                <span class="required">{t("sessions.new.password")}</span>
                <input
                  type="password"
                  class="form-control mt-2"
                  name="password"
                  autoComplete="current-password"
                  required
                />
              </label>
              <p class="form-text">
                <a
                  class="link-primary"
                  href="/reset-password"
                >
                  {t("sessions.new.lost password link")}
                </a>
              </p>

              <div class="text-end">
                <button
                  class="btn btn-primary px-3"
                  type="submit"
                >
                  {t("action.submit")}
                </button>
              </div>
            </StandardForm>
          </div>
        </div>
      </div>
    </div>
  </>
))
