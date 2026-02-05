import { config } from "@lib/config"
import { SettingsSecurityService } from "@lib/proto/settings_security_pb"
import { StandardForm } from "@lib/standard-form"
import { batch, useSignal, useSignalEffect } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { encodeBase32 } from "@std/encoding/base32"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { render } from "preact"
import { useId, useLayoutEffect, useRef } from "preact/hooks"

const generateTOTPSecret = () => {
  const buffer = new Uint8Array(16) // 128 bits
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

const SetupTotpModal = () => {
  const labelId = useId()
  const secret = useSignal("")
  const digits = useSignal<6 | 8>(8)
  const qrSvg = useSignal("")

  const modalRef = useRef<HTMLDivElement>(null)
  const codeInputRef = useRef<HTMLInputElement>(null)

  useLayoutEffect(() => {
    const modal = modalRef.current!

    modal.addEventListener("show.bs.modal", () => {
      batch(() => {
        digits.value = 8
        secret.value = generateTOTPSecret()
        qrSvg.value = ""
      })
      codeInputRef.current!.value = ""
    })

    modal.addEventListener("shown.bs.modal", () => {
      codeInputRef.current!.focus()
    })

    modal.addEventListener("hidden.bs.modal", () => {
      batch(() => {
        secret.value = ""
        qrSvg.value = ""
      })
      codeInputRef.current!.value = ""
    })
  }, [])

  useSignalEffect(() => {
    const secretValue = secret.value
    if (!secretValue) return

    const digitsValue = digits.value
    const abortController = new AbortController()

    void (async () => {
      const nextSvg = await generateTOTPQRCode(
        secretValue,
        digitsValue,
        `${config.userConfig!.displayName} (${config.userConfig!.email})`,
      )
      abortController.signal.throwIfAborted()
      qrSvg.value = nextSvg
    })()

    return () => {
      abortController.abort()
    }
  })

  return (
    <div
      class="modal fade"
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
            method={SettingsSecurityService.method.setupTotp}
            buildRequest={({ formData }) => ({
              secret: secret.value,
              digits: digits.value,
              totpCode: formData.get("totp_code") as string,
            })}
            onSuccess={() => window.location.reload()}
          >
            <div class="modal-body">
              <h6>{t("two_fa.step_1_choose_code_length")}</h6>
              <p class="text-muted mb-3">
                {t("two_fa.adjust_the_strength_of_your_one_time_codes")}
              </p>

              <div class="form-check mb-2">
                <label class="form-check-label w-100">
                  <input
                    class="form-check-input"
                    type="radio"
                    name="digits"
                    value="8"
                    checked={digits.value === 8}
                    onChange={() => (digits.value = 8)}
                  />
                  {t("two_fa.8_digit_code_more_secure")}
                </label>
              </div>
              <div class="form-check mb-4">
                <label class="form-check-label w-100">
                  <input
                    class="form-check-input"
                    type="radio"
                    name="digits"
                    value="6"
                    checked={digits.value === 6}
                    onChange={() => (digits.value = 6)}
                  />
                  {t("two_fa.6_digit_code")}
                </label>
              </div>

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

export const getSetupTotpModal = memoize(() => {
  const root = document.createElement("div")
  render(<SetupTotpModal />, root)
  document.body.append(root)

  const modal = root.firstElementChild
  return new Modal(modal!)
})
