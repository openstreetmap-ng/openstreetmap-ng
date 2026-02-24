import { config } from "@lib/config"
import { useDisposeLayoutEffect } from "@lib/dispose-scope"
import { type PasskeyValid, Service } from "@lib/proto/settings_security_pb"
import { StandardForm } from "@lib/standard-form"
import type { Signal } from "@preact/signals"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"

export const DISABLE_AUTH_METHOD_MODAL_ID = "SettingsSecurityDisableAuthMethodModal"

export type DisableAuthMethodContext =
  | {
      method: "totp"
      title: string
    }
  | {
      method: "passkey"
      title: string
      credentialId: Uint8Array
    }

export const DisableAuthMethodModal = ({
  ctx,
  passkeys,
  totpCreatedAt,
}: {
  ctx: Signal<DisableAuthMethodContext | undefined>
  passkeys: Signal<readonly PasskeyValid[]>
  totpCreatedAt: Signal<bigint | undefined>
}) => {
  const labelId = useId()
  const modalRef = useRef<HTMLDivElement>(null)
  const passwordInputRef = useRef<HTMLInputElement>(null)

  useDisposeLayoutEffect((scope) => {
    const modal = modalRef.current!
    scope.dom(modal, "shown.bs.modal", () => {
      passwordInputRef.current!.focus()
    })
    scope.dom(modal, "hidden.bs.modal", () => {
      passwordInputRef.current!.value = ""
      ctx.value = undefined
    })
  }, [])

  const current = ctx.value

  return (
    <div
      class="modal fade"
      id={DISABLE_AUTH_METHOD_MODAL_ID}
      tabIndex={-1}
      aria-labelledby={labelId}
      aria-hidden="true"
      ref={modalRef}
    >
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5
              class="modal-title"
              id={labelId}
            >
              {current?.title}
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label={t("javascripts.close")}
            />
          </div>

          {current?.method === "passkey" ? (
            <StandardForm
              method={Service.method.removePasskey}
              buildRequest={({ passwords }) => ({
                credentialId: current.credentialId,
                password: passwords.password,
              })}
              onSuccess={(resp) => {
                passkeys.value = resp.passkeys
                Modal.getOrCreateInstance(modalRef.current!).hide()
              }}
            >
              <div class="modal-body">
                <input
                  type="text"
                  name="display_name"
                  value={config.userConfig!.user.displayName}
                  autoComplete="username"
                  readOnly
                  hidden
                />

                <label class="form-label d-block">
                  <span class="required">
                    {t("settings.enter_your_password_to_confirm")}
                  </span>
                  <input
                    type="password"
                    class="form-control mt-2"
                    name="password"
                    autoComplete="current-password"
                    required
                    ref={passwordInputRef}
                  />
                </label>
              </div>
              <div class="modal-footer">
                <button
                  type="button"
                  class="btn btn-secondary"
                  data-bs-dismiss="modal"
                >
                  {t("action.cancel")}
                </button>
                <button
                  type="submit"
                  class="btn btn-danger"
                >
                  {t("action.disable")}
                </button>
              </div>
            </StandardForm>
          ) : current?.method === "totp" ? (
            <StandardForm
              method={Service.method.disableTotp}
              buildRequest={({ passwords }) => ({
                password: passwords.password,
              })}
              onSuccess={() => {
                totpCreatedAt.value = undefined
                Modal.getOrCreateInstance(modalRef.current!).hide()
              }}
            >
              <div class="modal-body">
                <input
                  type="text"
                  name="display_name"
                  value={config.userConfig!.user.displayName}
                  autoComplete="username"
                  readOnly
                  hidden
                />

                <label class="form-label d-block">
                  <span class="required">
                    {t("settings.enter_your_password_to_confirm")}
                  </span>
                  <input
                    type="password"
                    class="form-control mt-2"
                    name="password"
                    autoComplete="current-password"
                    required
                    ref={passwordInputRef}
                  />
                </label>
              </div>
              <div class="modal-footer">
                <button
                  type="button"
                  class="btn btn-secondary"
                  data-bs-dismiss="modal"
                >
                  {t("action.cancel")}
                </button>
                <button
                  type="submit"
                  class="btn btn-danger"
                >
                  {t("action.disable")}
                </button>
              </div>
            </StandardForm>
          ) : null}
        </div>
      </div>
    </div>
  )
}
