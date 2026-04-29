import {
  DISPLAY_NAME_MAX_LENGTH,
  EMAIL_MAX_LENGTH,
  EMAIL_MIN_LENGTH,
  PASSWORD_MIN_LENGTH,
} from "@lib/config"
import { activityTracking } from "@lib/config"
import { tRich } from "@lib/i18n"
import { Service, PageSchema } from "@lib/proto/signup_pb"
import { mountProtoPage } from "@lib/proto-page"
import { StandardForm } from "@lib/standard-form"
import { t } from "i18next"
import { Action } from "@lib/proto/auth_provider_pb"
import { useSignal } from "@preact/signals"
import { AuthSwitcher } from "./_auth-switcher"
import { showLoginModal } from "./login"
import { TestSiteReminder } from "./_test-site-reminder"

const SIGNUP_ACTION_CLASS =
  "col-12 col-sm-10 offset-sm-1 col-md-8 offset-md-2 col-lg-6 offset-lg-3 col-xl-12 offset-xl-0 mt-3 px-3"

mountProtoPage(PageSchema, ({ verification }) => {
  const displayName = verification?.name ?? ""
  const verifiedEmail = verification?.email
  const showAuthProviders = useSignal(false)
  const hasPassword = useSignal(false)

  const form = (
    <StandardForm
      method={Service.method.submit}
      buildRequest={({ formData, passwords }) => ({
        displayName: formData.get("display_name") as string,
        email: formData.get("email") as string,
        password: passwords.password,
        tracking: activityTracking,
      })}
      onSuccess={({ emailVerified }, ctx) =>
        ctx.redirect(emailVerified ? "/welcome" : "/user/account-confirm/pending")
      }
      class="signup-form"
    >
      <label class="form-label d-block">
        {t("activerecord.attributes.user.display_name")}
        <input
          type="text"
          class="form-control mt-2"
          name="display_name"
          defaultValue={displayName}
          maxLength={DISPLAY_NAME_MAX_LENGTH}
          autoComplete="username"
          autoCapitalize="none"
          required
        />
      </label>
      <p class="form-text">
        {t("settings.your_public_username")}{" "}
        {t("settings.you_can_change_it_later_in_the_settings")}
      </p>

      <label class="form-label d-block">
        {t("passwords.new.email address")}
        <TestSiteReminder>
          <input
            type="email"
            class={`form-control mt-2 ${verifiedEmail ? "bg-body-tertiary" : ""}`}
            name="email"
            minLength={EMAIL_MIN_LENGTH}
            maxLength={EMAIL_MAX_LENGTH}
            defaultValue={verifiedEmail ?? ""}
            autoComplete="email"
            readOnly={Boolean(verifiedEmail)}
            required
          />
        </TestSiteReminder>
      </label>
      <p class="form-text">
        {t("settings.your_email_address_is_not_displayed_publicly")}
      </p>

      <label class="form-label d-block mb-3">
        {t("sessions.new.password")}
        <input
          type="password"
          class="form-control mt-2"
          name="password"
          minLength={PASSWORD_MIN_LENGTH}
          autoComplete="new-password"
          onInput={(e) => (hasPassword.value = e.currentTarget.value.length > 0)}
          required
        />
      </label>

      <div class={`collapse ${hasPassword.value ? "show" : ""}`}>
        <label class="form-label d-block mb-4">
          {t("activerecord.attributes.user.pass_crypt_confirmation")}
          <input
            type="password"
            class="form-control mt-2"
            name="password_confirm"
            minLength={PASSWORD_MIN_LENGTH}
            autoComplete="new-password"
            required={hasPassword.value}
          />
        </label>
      </div>

      <div class="form-check small mx-1 mb-3">
        <label class="form-check-label">
          <input
            class="form-check-input"
            type="checkbox"
            autoComplete="off"
            required
          />
          <span class="required">
            {tRich("signup.i_agree_to_the_terms_privacy_and_contributor", {
              terms: (
                <a
                  href="https://osmfoundation.org/wiki/Terms_of_Use"
                  rel="noopener noreferrer terms-of-service"
                  target="_blank"
                >
                  {t("layouts.tou").toLowerCase()}
                </a>
              ),
              privacy: (
                <a
                  href="https://osmfoundation.org/wiki/Privacy_Policy"
                  rel="noopener noreferrer privacy-policy"
                  target="_blank"
                >
                  {t("users.new.privacy_policy")}
                </a>
              ),
              contributor: (
                <a
                  href="https://osmfoundation.org/wiki/Licence/Contributor_Terms"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {t("accounts.edit.contributor terms.heading").toLowerCase()}
                </a>
              ),
            })}
          </span>
        </label>
      </div>

      <button
        class="btn btn-lg py-2 btn-primary rounded-pill fw-medium col-12 col-sm-10 offset-sm-1 col-md-8 offset-md-2 col-lg-6 offset-lg-3 col-xl-12 offset-xl-0"
        type="submit"
      >
        {t("layouts.sign_up")}
      </button>
    </StandardForm>
  )

  return (
    <div class="content-body">
      <div class="row g-0">
        <div class="col-7 d-none d-xl-block">
          <div class="brand-content">
            <img
              class="background-image"
              src="/static/img/signup/background.webp"
              alt={t("alt.image_of_planet_earth")}
              loading="lazy"
            />

            <div>
              <h1 class="brand-title fw-bold">
                <img
                  src="/static/img/favicon/256.webp"
                  alt={t("alt.logo", { name: t("project_name") })}
                  draggable={false}
                />
                {t("project_name")}
              </h1>
              <p
                class="brand-description mb-0"
                dangerouslySetInnerHTML={{ __html: t("signup.brand_description") }}
              />
            </div>

            <p class="background-image-credits mx-3 mb-2">
              {t("signup.photo_by_author", {
                author:
                  "Earth Science and Remote Sensing Unit, NASA Johnson Space Center",
              })}
            </p>
          </div>
        </div>

        <div class="signup-content col">
          <div class="col-12 col-xxl-9">
            <div class="text-center">
              <h1 class="brand-title-sm display-4 fw-bold d-xl-none">
                <img
                  class="d-none d-sm-inline-block"
                  src="/static/img/favicon/256.webp"
                  alt={t("alt.logo", { name: t("project_name") })}
                  draggable={false}
                />
                {t("project_name")}
              </h1>
              <h2 class="brand-subtitle">{t("signup.get_started_contributing")}</h2>
              <p class="form-text mt-0 mb-4">
                {t("signup.already_have_an_account")}{" "}
                <button
                  class="link-primary btn btn-link p-0 align-baseline"
                  type="button"
                  onClick={showLoginModal}
                >
                  {t("signup.sign_in_here")}
                </button>
              </p>
            </div>

            {verification ? (
              form
            ) : (
              <AuthSwitcher
                action={Action.signup}
                showProviders={showAuthProviders}
                ctaClass={SIGNUP_ACTION_CLASS}
                ctaButtonClass="fw-medium"
              >
                {form}
              </AuthSwitcher>
            )}

            {verification && (
              <div class={SIGNUP_ACTION_CLASS}>
                <StandardForm
                  method={Service.method.cancelProvider}
                  buildRequest={() => ({})}
                  onSuccess={(_, ctx) => ctx.redirect("/signup")}
                >
                  <button
                    class="btn btn-sm btn-outline-secondary w-100"
                    type="submit"
                  >
                    {t("signup.cancel_sign_up")}
                  </button>
                </StandardForm>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
})
