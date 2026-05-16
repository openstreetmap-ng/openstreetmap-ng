import { StandardForm } from "@components/standard-form"
import { PageSchema, Service } from "@proto/reset_password_pb"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { PASSWORD_MIN_LENGTH } from "@utils/config"
import { mountProtoPage } from "@utils/proto-page"
import { t } from "i18next"

const RequestForm = ({ prefilledEmail }: { prefilledEmail?: string | undefined }) => (
  <>
    <p>{t("passwords.new.help_text")}</p>
    <StandardForm
      method={Service.method.request}
      buildRequest={({ formData }) => ({
        email: (formData.get("email") as string).trim(),
      })}
      onSuccess={(_, ctx) => ctx.form.reset()}
    >
      <input
        type="email"
        class={`form-control mb-3 ${prefilledEmail ? "bg-body-tertiary" : ""}`}
        name="email"
        autocomplete="email"
        placeholder={toSentenceCase(t("passwords.new.email address"))}
        aria-label={t("passwords.new.email address")}
        defaultValue={prefilledEmail}
        readonly={Boolean(prefilledEmail)}
        required
      />
      <div class="text-end">
        <button
          class="btn btn-primary"
          type="submit"
        >
          {t("settings.send_password_reset_link")}
        </button>
      </div>
    </StandardForm>
  </>
)

const ConfirmForm = ({
  token,
  displayName,
  avatarUrl,
}: {
  token: string
  displayName: string
  avatarUrl: string
}) => (
  <>
    <div class="card mb-4">
      <div class="card-body d-flex align-items-center gap-3">
        <img
          class="avatar"
          src={avatarUrl}
          alt={t("alt.profile_picture")}
        />
        <div class="d-inline-block">
          <p class="fw-semibold mb-0">{displayName}</p>
          <p class="text-muted mb-0">
            {t("settings.please_choose_a_new_password_for_your_account")}
          </p>
        </div>
      </div>
    </div>

    <StandardForm
      method={Service.method.reset}
      buildRequest={({ passwords }) => ({
        token,
        newPassword: passwords.new_password,
      })}
      onSuccess={(_, ctx) => ctx.redirect("/settings")}
    >
      <input
        type="text"
        name="display_name"
        value={displayName}
        autocomplete="username"
        hidden
      />

      <label class="form-label d-block mb-3">
        <span class="required">{t("settings.new_password")}</span>
        <input
          type="password"
          class="form-control mt-2"
          name="new_password"
          minLength={PASSWORD_MIN_LENGTH}
          autocomplete="new-password"
          required
        />
      </label>

      <label class="form-label d-block mb-3">
        <span class="required">{t("settings.new_password_repeat")}</span>
        <input
          type="password"
          class="form-control mt-2"
          name="new_password_confirm"
          minLength={PASSWORD_MIN_LENGTH}
          autocomplete="new-password"
          required
        />
      </label>

      <div class="text-end">
        <button
          class="btn btn-primary"
          type="submit"
        >
          {t("settings.change_password")}
        </button>
      </div>
    </StandardForm>
  </>
)

mountProtoPage(PageSchema, ({ currentEmail, confirm }) => (
  <>
    <div class="content-header">
      <h1 class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        {t("passwords.edit.title")}
      </h1>
    </div>
    <div class="content-body">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        {confirm ? (
          <ConfirmForm
            token={confirm.token}
            displayName={confirm.profile.displayName}
            avatarUrl={confirm.profile.avatarUrl}
          />
        ) : (
          <RequestForm prefilledEmail={currentEmail} />
        )}
      </div>
    </div>
  </>
))
