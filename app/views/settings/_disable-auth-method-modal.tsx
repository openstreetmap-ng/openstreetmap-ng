import { StandardForm } from "@components/standard-form"
import type { Signal } from "@preact/signals"
import { type PasskeyValid, Service } from "@proto/settings_security_pb"
import { config } from "@utils/config"
import { useDisposeLayoutEffect } from "@utils/dispose-scope"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"

export const DISABLE_AUTH_METHOD_MODAL_ID = "DisableAuthMethodModal"

/**
 * Discriminator for which auth method the modal is targeting:
 * - `Uint8Array` → remove that passkey (the value IS the credentialId)
 * - `"totp"`     → disable the TOTP authenticator app
 * - `undefined`  → modal closed / no pending action
 */
export type DisableAuthMethodContext = Uint8Array | "totp" | undefined

export const DisableAuthMethodModal = ({
  ctx,
  passkeys,
  totpCreatedAt,
}: {
  ctx: Signal<DisableAuthMethodContext>
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
  const title =
    current instanceof Uint8Array
      ? t("two_fa.remove_passkey")
      : current === "totp"
        ? t("two_fa.disable_authenticator_app")
        : undefined

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
              {title}
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label={t("javascripts.close")}
            />
          </div>

          {current instanceof Uint8Array ? (
            <StandardForm
              method={Service.method.removePasskey}
              buildRequest={({ passwords }) => ({
                credentialId: current,
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
                  defaultValue={config.userConfig!.user.displayName}
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
          ) : current === "totp" ? (
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
                  defaultValue={config.userConfig!.user.displayName}
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
