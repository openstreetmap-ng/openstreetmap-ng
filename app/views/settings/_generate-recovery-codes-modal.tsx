import { config } from "@lib/config"
import { CopyButton } from "@lib/copy-group"
import { useDisposeLayoutEffect } from "@lib/dispose-scope"
import { type RecoveryStatusValid, Service } from "@lib/proto/settings_security_pb"
import { StandardForm } from "@lib/standard-form"
import { batch, type Signal, useSignal } from "@preact/signals"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"

export const GENERATE_RECOVERY_CODES_MODAL_ID =
  "SettingsSecurityGenerateRecoveryCodesModal"

export const GenerateRecoveryCodesModal = ({
  recoveryCodesStatus,
}: {
  recoveryCodesStatus: Signal<RecoveryStatusValid>
}) => {
  const labelId = useId()
  const codes = useSignal<readonly string[] | undefined>()

  const modalRef = useRef<HTMLDivElement>(null)
  const passwordInputRef = useRef<HTMLInputElement>(null)

  useDisposeLayoutEffect((scope) => {
    const modal = modalRef.current!
    scope.dom(modal, "show.bs.modal", () => {
      codes.value = undefined
      passwordInputRef.current!.value = ""
    })
    scope.dom(modal, "shown.bs.modal", () => {
      passwordInputRef.current!.focus()
    })
  }, [])

  return (
    <div
      class="modal fade"
      id={GENERATE_RECOVERY_CODES_MODAL_ID}
      data-bs-backdrop="static"
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
              {t("two_fa.generate_recovery_codes")}
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label={t("javascripts.close")}
            />
          </div>

          {codes.value ? (
            <>
              <div class="modal-body">
                <div
                  class="alert alert-warning d-flex align-items-center mb-3"
                  role="alert"
                >
                  <i class="bi bi-exclamation-triangle-fill fs-4 me-3 flex-shrink-0" />
                  <div>{t("two_fa.save_recovery_codes_warning")}</div>
                </div>

                <div class="recovery-codes-container">
                  <div class="row row-cols-1 row-cols-sm-2 g-0">
                    {codes.value.map((code) => (
                      <div class="col">{code}</div>
                    ))}
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button
                  type="button"
                  class="btn btn-secondary"
                  data-bs-dismiss="modal"
                >
                  {t("javascripts.close")}
                </button>
                <CopyButton
                  class="btn btn-primary px-4"
                  iconClass="me-2"
                  getText={() => codes.value!.join("\n")}
                >
                  {t("action.copy")}
                </CopyButton>
              </div>
            </>
          ) : (
            <StandardForm
              method={Service.method.generateRecoveryCodes}
              buildRequest={({ passwords }) => ({
                password: passwords.password,
              })}
              onSuccess={(resp) => {
                batch(() => {
                  codes.value = resp.codes
                  recoveryCodesStatus.value = resp.status
                })
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

                <p>
                  {t("two_fa.recovery_codes_description")}{" "}
                  {t("two_fa.each_code_can_be_used_once")}
                </p>

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
                  class="btn btn-primary"
                >
                  {t("action.submit")}
                </button>
              </div>
            </StandardForm>
          )}
        </div>
      </div>
    </div>
  )
}
