import { tRich } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import { PageSchema, Service } from "@lib/proto/account_confirm_pb"
import { StandardForm } from "@lib/standard-form"
import { t } from "i18next"

mountProtoPage(PageSchema, () => (
  <>
    <div class="content-header">
      <h1 class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <span>{t("confirmations.confirm.heading")}</span>
        <img
          class="illustration"
          src="/static/img/account-confirm/illustration.webp"
          alt={t("alt.happy_globe_mascot")}
        />
      </h1>
    </div>
    <div class="content-body">
      <StandardForm
        class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3"
        method={Service.method.resend}
        buildRequest={() => ({})}
        onSuccess={(resp, ctx) => {
          if (resp.isActive) ctx.redirect("/welcome")
        }}
      >
        <h3 class="mb-3">{t("confirmations.confirm.introduction_1")}</h3>
        <p class="mb-3">{t("confirmations.confirm.introduction_2")}</p>
        <p>
          {tRich("confirmations.confirm.resend_html", {
            reconfirm_link: (
              <button
                class="btn btn-link p-0"
                type="submit"
              >
                {t("confirmations.confirm.click_here")}
              </button>
            ),
          })}
        </p>
      </StandardForm>
    </div>
  </>
))
