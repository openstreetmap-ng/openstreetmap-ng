import { tRich } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import {
  AuthorizeRequestSchema,
  CodeChallengeMethod,
  type Page,
  PageSchema,
  ResponseMode,
  ResponseType,
  Service,
} from "@lib/proto/oauth2_authorize_pb"
import type { LooseMessageInitShape } from "@lib/rpc"
import { ScopeList } from "@lib/scope"
import { StandardForm } from "@lib/standard-form"
import { useSignal } from "@preact/signals"
import { Time } from "@lib/datetime-inputs"
import { t } from "i18next"

const ConsentUI = ({ page, onOob }: { page: Page; onOob: (code: string) => void }) => {
  const app = page.app!
  const owner = app.owner!
  const params = new URLSearchParams(window.location.search)
  const appNameNode = <span class="fw-semibold">{app.name}</span>

  return (
    <>
      <div class="content-header px-md-5">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2">
          <p class="text-body-secondary text-uppercase small fw-semibold mb-1">
            {t("oauth.authorization_request_app", { name: app.name })}
          </p>
          <h1 class="h3 text-body-emphasis mb-3">
            {tRich("oauth.authorize_app_to_access_your_account", {
              name: appNameNode,
            })}
          </h1>
          <div class="d-flex align-items-center flex-wrap gap-2 gap-md-3">
            <img
              class="avatar authorization-avatar"
              src={app.avatarUrl}
              alt={t("alt.application_image")}
            />
            <span
              class="authorization-arrow"
              aria-hidden="true"
            >
              <i class="bi bi-arrow-right-short" />
            </span>
            <a
              href={`/user/${owner.displayName}`}
              target="_blank"
              rel="noopener"
            >
              <img
                class="avatar authorization-avatar"
                src={owner.avatarUrl}
                alt={t("alt.profile_picture")}
              />
            </a>
            <span class="text-body-secondary small">
              {tRich("oauth.you_are_currently_signed_in_as", {
                name: (
                  <a
                    class="link-body-emphasis"
                    href={`/user/${owner.displayName}`}
                    target="_blank"
                    rel="noopener"
                  >
                    {owner.displayName}
                  </a>
                ),
              })}
            </span>
          </div>
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2">
          <StandardForm
            class="card"
            method={Service.method.authorize}
            buildRequest={() => buildAuthorizeRequest(params)}
            onSuccess={(resp) => handleOutcome(resp.outcome, onOob)}
          >
            <div class="card-body py-4 py-sm-5 px-4 px-md-5">
              <div class="row g-2 g-md-3 mb-4 mb-md-5">
                <div class="col-lg">
                  <h2 class="h5 mb-3">
                    {tRich("oauth.app_is_requesting_permissions_to", {
                      name: appNameNode,
                    })}
                  </h2>
                  <ScopeList
                    scopes={page.scopes}
                    className="authorize-scope-list mb-lg-0"
                  />
                </div>

                <div class="col-lg-auto">
                  <div class="authorize-summary">
                    <div>
                      <h2 class="h6 text-uppercase text-body-secondary">
                        {t("oauth.authorizing_will_redirect_you_to")}
                      </h2>
                      <ul class="authorize-summary-list list-unstyled">
                        <li>
                          <i class="bi bi-link-45deg text-primary" />
                          <span class="text-break">{page.redirectUri}</span>
                        </li>
                      </ul>
                    </div>
                    <div>
                      <h2 class="h6 text-uppercase text-body-secondary">
                        {t("oauth.application_information")}
                      </h2>
                      <ul class="authorize-summary-list list-unstyled mb-0">
                        <li>
                          <a
                            href={`/user/${owner.displayName}`}
                            target="_blank"
                            rel="noopener"
                          >
                            <img
                              class="avatar"
                              src={owner.avatarUrl}
                              alt={t("alt.profile_picture")}
                            />
                          </a>
                          <span>
                            {tRich("settings.owned_by_user", {
                              name: (
                                <a
                                  href={`/user/${owner.displayName}`}
                                  target="_blank"
                                  rel="noopener"
                                >
                                  {owner.displayName}
                                </a>
                              ),
                            })}
                          </span>
                        </li>
                        <li>
                          <i class="bi bi-clock-history text-primary" />
                          <span>
                            {tRich("browse.created_ago_html", {
                              time_ago: (
                                <Time
                                  unix={page.createdAt}
                                  relativeStyle="long"
                                />
                              ),
                            })}
                          </span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              <div class="d-flex flex-column flex-sm-row-reverse gap-2 mx-md-5 mb-4">
                <button
                  class="btn btn-lg btn-primary w-100"
                  type="submit"
                >
                  {t("action.authorize")}
                </button>
                <a
                  href="/"
                  class="btn btn-lg btn-outline-secondary w-100"
                >
                  {t("action.cancel")}
                </a>
              </div>

              <div
                class="authorize-footnote"
                role="note"
              >
                <i class="bi bi-shield-lock" />
                <span class="text-body-secondary small">
                  {t("oauth.revoke_access_anytime_in_settings")}
                </span>
              </div>
            </div>
          </StandardForm>
        </div>
      </div>
    </>
  )
}

const buildAuthorizeRequest = (params: URLSearchParams) => {
  const responseTypeStr = params.get("response_type") ?? "code"
  const responseModeStr = params.get("response_mode")
  const codeChallengeMethodStr = params.get("code_challenge_method")
  const codeChallenge = params.get("code_challenge")
  const state = params.get("state")

  const request: LooseMessageInitShape<typeof AuthorizeRequestSchema> = {
    clientId: params.get("client_id") ?? "",
    redirectUri: params.get("redirect_uri") ?? "",
    responseType: ResponseType[responseTypeStr as keyof typeof ResponseType],
    scope: params.get("scope") ?? "",
  }
  if (responseModeStr) {
    request.responseMode = ResponseMode[responseModeStr as keyof typeof ResponseMode]
  }
  if (codeChallengeMethodStr && codeChallenge) {
    request.pkce = {
      method:
        CodeChallengeMethod[codeChallengeMethodStr as keyof typeof CodeChallengeMethod],
      challenge: codeChallenge,
    }
  }
  if (state) request.state = state
  return request
}

const handleOutcome = (
  outcome: { case: string; value: unknown } | { case: undefined },
  onOob: (code: string) => void,
) => {
  switch (outcome.case) {
    case "redirectUri":
      window.location.href = outcome.value as string
      break
    case "oobCode":
      onOob(outcome.value as string)
      break
    case "formPost":
      submitFormPost(
        outcome.value as { actionUrl: string; fields: Record<string, string> },
      )
      break
    default:
      throw new Error("Authorize: missing outcome")
  }
}

const submitFormPost = ({
  actionUrl,
  fields,
}: {
  actionUrl: string
  fields: Record<string, string>
}) => {
  const form = document.createElement("form")
  form.method = "POST"
  form.action = actionUrl
  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement("input")
    input.type = "hidden"
    input.name = name
    input.value = value
    form.append(input)
  }
  document.body.append(form)
  form.submit()
}

const OobResult = ({ code }: { code: string }) => (
  <div class="content-body">
    <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
      <div class="card">
        <div class="card-body text-center">
          <h2 class="h4 mb-3">{t("oauth.authorization_code")}</h2>
          <p class="text-body-secondary mb-3">
            {t("oauth.copy_this_code_to_complete_authorization")}
          </p>
          <code class="d-block py-3 px-2 bg-body-tertiary rounded user-select-all">
            {code}
          </code>
        </div>
      </div>
    </div>
  </div>
)

mountProtoPage(PageSchema, (page) => {
  // null = pending consent; non-null string = received OOB code, render it.
  const oobCode = useSignal<string | null>(null)

  if (oobCode.value !== null) {
    return <OobResult code={oobCode.value} />
  }
  return (
    <ConsentUI
      page={page}
      onOob={(code) => (oobCode.value = code)}
    />
  )
})
