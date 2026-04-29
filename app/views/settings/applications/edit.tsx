import { OAUTH_APP_NAME_MAX_LENGTH } from "@lib/config"
import { CopyButton } from "@lib/copy-group"
import { mountProtoPage } from "@lib/proto-page"
import { EditPageSchema, Service } from "@lib/proto/settings_applications_pb"
import { Scope } from "@lib/proto/shared_pb"
import { formDataScopes, SCOPE_LABEL, SCOPES_NO_WEB_USER } from "@lib/scope"
import { formDataBytes, StandardForm } from "@lib/standard-form"
import { throwAbortError } from "@lib/utils"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import { useRef } from "preact/hooks"
import { Nav } from "../_nav"
import { ApplicationsNav } from "./_nav"

mountProtoPage(
  EditPageSchema,
  ({
    id,
    name,
    clientId,
    avatarUrl: initialAvatarUrl,
    clientSecretPreview,
    confidential: initialConfidential,
    redirectUris,
    scopes,
  }) => {
    const avatarUrl = useSignal(initialAvatarUrl)
    const clientSecret = useSignal(
      clientSecretPreview ? `${clientSecretPreview}...` : "",
    )
    const clientSecretCopyable = useSignal(false)
    const confidential = useSignal(initialConfidential)

    const avatarFormRef = useRef<HTMLFormElement>(null)
    const avatarFileInputRef = useRef<HTMLInputElement>(null)
    const resetSecretFormRef = useRef<HTMLFormElement>(null)

    return (
      <>
        <div class="content-header">
          <h1 class="container">{t("settings.applications")}</h1>
        </div>

        <div class="content-body">
          <div class="container">
            <div class="row">
              <div class="col-lg-auto mb-4">
                <Nav />
              </div>

              <div class="col-lg">
                <ApplicationsNav />

                <div class="row g-3 g-lg-5 flex-wrap-reverse">
                  <StandardForm
                    class="col-lg"
                    method={Service.method.update}
                    buildRequest={({ formData }) => ({
                      id,
                      name: formData.get("name") as string,
                      confidential: formData.get("confidential") === "true",
                      redirectUris: (formData.get("redirect_uris") as string).split(
                        /\r?\n/u,
                      ),
                      scopes: formDataScopes(formData),
                      revokeAllAuthorizations: formData.has(
                        "revoke_all_authorizations",
                      ),
                    })}
                    onSuccess={(_, ctx) => {
                      const revokeCheckbox = ctx.form.elements.namedItem(
                        "revoke_all_authorizations",
                      ) as HTMLInputElement
                      revokeCheckbox.checked = false
                    }}
                  >
                    <label class="form-label d-block mb-3">
                      <span class="required">{t("settings.name")}</span>
                      <input
                        type="text"
                        class="form-control mt-2"
                        name="name"
                        maxLength={OAUTH_APP_NAME_MAX_LENGTH}
                        defaultValue={name}
                        required
                      />
                    </label>

                    <label class="form-label d-block mb-3">
                      {t("settings.client_id")}
                      <div class="input-group mt-2">
                        <input
                          type="text"
                          class="form-control font-monospace bg-body-tertiary"
                          value={clientId}
                          readOnly
                        />
                        <CopyButton
                          class="btn btn-primary"
                          title={t("action.copy")}
                          getText={() => clientId}
                        />
                      </div>
                    </label>

                    <label
                      class="form-label d-block mb-3"
                      hidden={!confidential.value}
                    >
                      {t("settings.client_secret")}
                      <div class="input-group mt-2">
                        <input
                          type="text"
                          class="form-control font-monospace bg-body-tertiary"
                          value={clientSecret.value}
                          readOnly
                        />
                        <button
                          class="btn btn-soft"
                          type="button"
                          onClick={() => resetSecretFormRef.current!.requestSubmit()}
                        >
                          <i class="bi bi-arrow-clockwise me-1-5" />
                          {t("settings.new_client_secret")}
                        </button>
                        {clientSecretCopyable.value && (
                          <CopyButton
                            class="btn btn-primary"
                            title={t("action.copy")}
                            getText={() => clientSecret.value}
                          />
                        )}
                      </div>
                    </label>

                    <label class="form-label">
                      <span class="required">{t("settings.client_type")}</span>
                    </label>
                    <div class="ms-1">
                      <div class="form-check">
                        {[
                          {
                            value: false,
                            icon: "unlock",
                            label: t("settings.public_client"),
                            description: t("settings.public_client_description"),
                          },
                          {
                            value: true,
                            icon: "key",
                            label: t("settings.confidential_client"),
                            description: t("settings.confidential_client_description"),
                          },
                        ].map(({ value, icon, label, description }) => (
                          <div>
                            <label class="form-check-label w-100">
                              <input
                                class="form-check-input"
                                type="radio"
                                name="confidential"
                                value={value.toString()}
                                checked={confidential.value === value}
                                onChange={() => (confidential.value = value)}
                              />
                              <i class={`bi bi-${icon} text-primary me-1-5`} />
                              {label}
                            </label>
                            <p class="form-text">{description}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <label class="form-label d-block">
                      {t("settings.redirect_uris")}
                      <textarea
                        class="form-control mt-2"
                        name="redirect_uris"
                        rows={4}
                        placeholder="http://localhost/callback"
                        defaultValue={redirectUris.join("\n")}
                      />
                    </label>
                    <p class="form-text mb-3">
                      {t("settings.redirect_uris_description")}
                    </p>

                    <p class="form-label">{t("settings.requested_permissions")}</p>
                    <ul class="list-unstyled ms-1">
                      {SCOPES_NO_WEB_USER.map((scope) => (
                        <li class="form-check">
                          <label class="form-check-label d-block">
                            <input
                              class="form-check-input"
                              type="checkbox"
                              name="scopes"
                              value={scope}
                              defaultChecked={scopes.includes(scope)}
                            />
                            {SCOPE_LABEL[scope]}{" "}
                            <span class="scope">({Scope[scope]})</span>
                          </label>
                        </li>
                      ))}
                    </ul>

                    <div class="row g-2 g-xl-3 align-items-center text-end">
                      <div class="col-xl form-check">
                        <label class="form-check-label">
                          <input
                            class="form-check-input"
                            type="checkbox"
                            name="revoke_all_authorizations"
                          />
                          {t("settings.revoke_all_authorizations")}
                        </label>
                      </div>
                      <div class="col-xl-auto">
                        <button
                          class="btn btn-primary px-3"
                          type="submit"
                        >
                          {t("action.save_changes")}
                        </button>
                      </div>
                    </div>
                  </StandardForm>
                  <StandardForm
                    hidden
                    formRef={resetSecretFormRef}
                    method={Service.method.resetClientSecret}
                    buildRequest={() => {
                      if (!confirm(t("settings.new_secret_question"))) {
                        throwAbortError()
                      }
                      return { id }
                    }}
                    onSuccess={(resp) => {
                      clientSecret.value = resp.secret
                      clientSecretCopyable.value = true
                    }}
                  />

                  <div class="col-lg-auto">
                    <div class="d-flex justify-content-center mt-lg-2">
                      <StandardForm
                        class="avatar-form"
                        formRef={avatarFormRef}
                        method={Service.method.updateAvatar}
                        buildRequest={async ({ formData }) => ({
                          id,
                          avatarFile: await formDataBytes(formData, "avatar_file"),
                        })}
                        onSuccess={(resp) => (avatarUrl.value = resp.avatarUrl)}
                      >
                        <input
                          class="visually-hidden"
                          type="file"
                          name="avatar_file"
                          accept="image/*"
                          ref={avatarFileInputRef}
                          onChange={() => avatarFormRef.current!.requestSubmit()}
                        />
                        <img
                          class="avatar"
                          src={avatarUrl.value}
                          alt={t("alt.application_image")}
                        />
                        <div class="dropdown">
                          <button
                            class="btn btn-sm btn-soft dropdown-toggle"
                            type="button"
                            data-bs-toggle="dropdown"
                            aria-expanded="false"
                          >
                            {t("layouts.edit")}
                          </button>
                          <ul class="dropdown-menu">
                            <li>
                              <h6 class="dropdown-header">
                                {t("alt.application_image")}
                              </h6>
                            </li>
                            <li>
                              <button
                                class="dropdown-item"
                                type="button"
                                onClick={() => avatarFileInputRef.current!.click()}
                              >
                                {t("action.upload_image")}...
                              </button>
                            </li>
                            <li>
                              <button
                                class="dropdown-item"
                                type="button"
                                onClick={() => {
                                  avatarFileInputRef.current!.value = ""
                                  avatarFormRef.current!.requestSubmit()
                                }}
                              >
                                {t("action.remove_image")}
                              </button>
                            </li>
                          </ul>
                        </div>
                      </StandardForm>
                    </div>
                  </div>
                </div>

                <hr class="my-4" />

                <h3 class="mb-3">{t("settings.danger_zone")}</h3>
                <StandardForm
                  method={Service.method.delete}
                  buildRequest={() => {
                    if (!confirm(t("settings.delete_this_application_question"))) {
                      throwAbortError()
                    }
                    return { id }
                  }}
                  onSuccess={(_, ctx) => ctx.redirect("/settings/applications/admin")}
                >
                  <button
                    class="btn btn-outline-danger"
                    type="submit"
                  >
                    {t("settings.delete_application")}
                  </button>
                </StandardForm>
              </div>
            </div>
          </div>
        </div>
      </>
    )
  },
)
