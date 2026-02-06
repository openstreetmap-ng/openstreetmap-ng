import { base64Decode } from "@bufbuild/protobuf/wire"
import { config } from "@lib/config"
import { SettingsSecurityService } from "@lib/proto/settings_security_pb"
import { StandardForm } from "@lib/standard-form"
import { type Signal, signal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { render } from "preact"
import { useId, useLayoutEffect, useRef } from "preact/hooks"

type DisableAuthMethodCtx =
  | {
      method: "totp"
      title: string
    }
  | {
      method: "passkey"
      title: string
      credentialId: string
    }

const DisableAuthMethodModal = ({
  ctx,
}: {
  ctx: Signal<DisableAuthMethodCtx | null>
}) => {
  const labelId = useId()

  const modalRef = useRef<HTMLDivElement>(null)
  const passwordInputRef = useRef<HTMLInputElement>(null)

  useLayoutEffect(() => {
    const modal = modalRef.current!

    modal.addEventListener("shown.bs.modal", () => {
      passwordInputRef.current?.focus()
    })

    modal.addEventListener("hidden.bs.modal", () => {
      passwordInputRef.current!.value = ""
      ctx.value = null
    })
  }, [])

  const current = ctx.value

  const FormContents = () => (
    <>
      <div class="modal-body">
        <input
          type="text"
          class="d-none"
          name="display_name"
          defaultValue={config.userConfig!.displayName}
          autoComplete="username"
        />

        <label class="form-label d-block">
          <span class="required">{t("settings.enter_your_password_to_confirm")}</span>
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
    </>
  )

  return (
    <div
      class="modal fade"
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
              {current?.title ?? ""}
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
              method={SettingsSecurityService.method.removePasskey}
              buildRequest={({ passwords }) => ({
                credentialId: base64Decode(current.credentialId),
                password: passwords.password,
              })}
              onSuccess={() => window.location.reload()}
            >
              <FormContents />
            </StandardForm>
          ) : current?.method === "totp" ? (
            <StandardForm
              method={SettingsSecurityService.method.disableTotp}
              buildRequest={({ passwords }) => ({
                password: passwords.password,
              })}
              onSuccess={() => window.location.reload()}
            >
              <FormContents />
            </StandardForm>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export const getDisableAuthMethodModal = memoize(() => {
  const ctx = signal<DisableAuthMethodCtx | null>(null)

  const root = document.createElement("div")
  render(<DisableAuthMethodModal ctx={ctx} />, root)
  document.body.append(root)

  const modal = root.firstElementChild
  return { ctx, modal: new Modal(modal!) }
})
