import { config } from "@lib/config"
import { useDisposeLayoutEffect, useDisposeSignalEffect } from "@lib/dispose-scope"
import { Service } from "@lib/proto/settings_security_pb"
import { StandardForm } from "@lib/standard-form"
import { batch, type Signal, useSignal } from "@preact/signals"
import { encodeBase32 } from "@std/encoding/base32"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"

export const SETUP_TOTP_MODAL_ID = "SettingsSecuritySetupTotpModal"

const generateTOTPSecret = () => {
  const buffer = new Uint8Array(16)
  crypto.getRandomValues(buffer)
  return encodeBase32(buffer).replaceAll("=", "")
}

const generateTOTPQRCode = async (
  secret: string,
  digits: number,
  accountName: string,
) => {
  const issuer = t("project_name")
  const label = `${issuer}:${accountName}`
  const uri = `otpauth://totp/${encodeURIComponent(label)}?secret=${secret}&issuer=${encodeURIComponent(issuer)}&digits=${digits}`

  const qrcode = (await import("qrcode-generator")).default
  const qr = qrcode(0, "M")
  qr.addData(uri)
  qr.make()
  return qr.createSvgTag(3)
}

export const SetupTotpModal = ({
  email,
  totpCreatedAt,
}: {
  email: string
  totpCreatedAt: Signal<bigint | undefined>
}) => {
  const labelId = useId()
  const secret = useSignal("")
  const digits = useSignal<6 | 8>(8)
  const qrSvg = useSignal("")

  const modalRef = useRef<HTMLDivElement>(null)
  const codeInputRef = useRef<HTMLInputElement>(null)

  const accountName = `${config.userConfig!.user.displayName} (${email})`

  useDisposeLayoutEffect((scope) => {
    const modal = modalRef.current!
    scope.dom(modal, "show.bs.modal", () => {
      batch(() => {
        digits.value = 8
        secret.value = generateTOTPSecret()
        qrSvg.value = ""
      })
      codeInputRef.current!.value = ""
    })
    scope.dom(modal, "shown.bs.modal", () => {
      codeInputRef.current!.focus()
    })
    scope.dom(modal, "hidden.bs.modal", () => {
      batch(() => {
        secret.value = ""
        qrSvg.value = ""
      })
      codeInputRef.current!.value = ""
    })
  }, [])

  useDisposeSignalEffect((scope) => {
    const secretValue = secret.value
    if (!secretValue) return

    const digitsValue = digits.value

    void (async () => {
      const nextSvg = await generateTOTPQRCode(secretValue, digitsValue, accountName)
      if (scope.signal.aborted) return
      qrSvg.value = nextSvg
    })()
  })

  return (
    <div
      class="modal fade"
      id={SETUP_TOTP_MODAL_ID}
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
              {t("two_fa.configure_authenticator_app")}
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label={t("javascripts.close")}
            />
          </div>

          <StandardForm
            method={Service.method.setupTotp}
            buildRequest={({ formData }) => ({
              secret: secret.value,
              digits: digits.value,
              totpCode: Number.parseInt(formData.get("totp_code") as string, 10),
            })}
            onSuccess={(resp) => {
              totpCreatedAt.value = resp.createdAt
              Modal.getOrCreateInstance(modalRef.current!).hide()
            }}
          >
            <div class="modal-body">
              <h6>{t("two_fa.step_1_choose_code_length")}</h6>
              <p class="text-muted mb-3">
                {t("two_fa.adjust_the_strength_of_your_one_time_codes")}
              </p>

              {[
                {
                  value: 8 as const,
                  label: t("two_fa.8_digit_code_more_secure"),
                  className: "mb-2",
                },
                {
                  value: 6 as const,
                  label: t("two_fa.6_digit_code"),
                  className: "mb-4",
                },
              ].map(({ value, label, className }) => (
                <div class={`form-check ${className}`}>
                  <label class="form-check-label w-100">
                    <input
                      class="form-check-input"
                      type="radio"
                      name="digits"
                      value={value}
                      checked={digits.value === value}
                      onChange={() => (digits.value = value)}
                    />
                    {label}
                  </label>
                </div>
              ))}

              <h6>{t("two_fa.step_2_scan_qr_code")}</h6>
              <p class="text-muted">
                {t("two_fa.scan_this_qr_code_with_your_preferred_authenticator_app")}
              </p>
              <div
                class="qr-code-container text-center mb-4"
                dangerouslySetInnerHTML={{ __html: qrSvg.value }}
              />

              <p class="text-muted mb-2">
                {t("two_fa.alternatively_enter_secret_key_manually")}
              </p>
              <input
                type="text"
                class="form-control mb-4"
                name="secret"
                readOnly
                value={secret.value}
                onClick={(e) => e.currentTarget.select()}
              />

              <h6>{t("two_fa.step_3_enter_code")}</h6>
              <p class="text-muted mb-2">
                {t("two_fa.enter_the_one_time_code_from_your_app_to_finish_setup")}
              </p>
              <input
                type="text"
                class="form-control"
                name="totp_code"
                placeholder={"0".repeat(digits.value)}
                pattern={`[0-9]{${digits.value}}`}
                minLength={digits.value}
                maxLength={digits.value}
                inputMode="numeric"
                autoComplete="off"
                required
                ref={codeInputRef}
              />
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
                {t("action.verify_and_enable")}
              </button>
            </div>
          </StandardForm>
        </div>
      </div>
    </div>
  )
}
