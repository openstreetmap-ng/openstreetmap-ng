import { isLoggedIn } from "@lib/config"
import { AccountNotFoundPageSchema } from "@lib/proto/auth_provider_pb"
import { mountProtoPage } from "@lib/proto-page"
import { getAuthProviderTitle } from "@lib/auth-provider"
import { t } from "i18next"
import { showLoginModal } from "./login"

mountProtoPage(AccountNotFoundPageSchema, ({ provider }) => {
  const providerTitle = getAuthProviderTitle(provider)
  const isGuest = !isLoggedIn

  return (
    <>
      <div class="content-header">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>{t("oauth.account_not_found")}</h1>
          <p class="mb-2">
            {t("oauth.we_couldnt_find_account", { provider: providerTitle })}
          </p>
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          {isGuest && (
            <>
              <h3>{t("oauth.new_to_openstreetmap")}</h3>
              <p class="mb-2">{t("oauth.create_an_account")}</p>
              <a
                class="mb-4 btn btn-primary px-4 fw-medium"
                href="/signup"
              >
                {t("users.new.title")}
              </a>
            </>
          )}

          <h3>{t("oauth.already_have_an_openstreetmap_account")}</h3>
          <p class="mb-2">
            {t("oauth.connect_it_in_settings", { provider: providerTitle })}
          </p>
          {isGuest && (
            <button
              class="btn btn-outline-primary px-4 fw-medium"
              type="button"
              onClick={showLoginModal}
            >
              {t("login.sign_in")}
            </button>
          )}
        </div>
      </div>
    </>
  )
})
