import i18next from "i18next"
import qrcode from "qrcode-generator"
import { mount } from "../lib/mount"
import { qsEncode } from "../lib/qs"
import { type APIDetail, configureStandardForm } from "../lib/standard-form"

const generateTOTPSecret = (): string => {
    const buffer = new Uint8Array(16) // 128 bits
    crypto.getRandomValues(buffer)

    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    let value = 0
    let bits = 0

    const output: string[] = []
    for (const byte of buffer) {
        value = (value << 8) | byte
        bits += 8
        while (bits >= 5) {
            output.push(alphabet[(value >>> (bits - 5)) & 31])
            bits -= 5
        }
    }
    if (bits > 0) {
        output.push(alphabet[(value << (5 - bits)) & 31])
    }
    return output.join("")
}

const generateTOTPQRCode = (secret: string, accountName: string): string => {
    const issuer = i18next.t("project_name")
    const label = `${issuer}:${accountName}`
    const uri = `otpauth://totp/${encodeURIComponent(label)}?secret=${secret}&issuer=${encodeURIComponent(issuer)}&algorithm=SHA1&digits=6&period=30`

    const qr = qrcode(0, "L")
    qr.addData(uri)
    qr.make()
    return qr.createSvgTag(3)
}

mount("settings-security-body", (body) => {
    const passwordForm = body.querySelector("form.password-form")
    const newPasswordInput = passwordForm.querySelector(
        "input[type=password][data-name=new_password]",
    )
    const newPasswordConfirmInput = passwordForm.querySelector(
        "input[type=password][data-name=new_password_confirm]",
    )

    configureStandardForm(
        passwordForm,
        () => {
            // On success callback, reset the password change form
            console.debug("onPasswordFormSuccess")
            passwordForm.reset()
        },
        {
            clientValidationCallback: () => {
                const result: APIDetail[] = []
                // Validate passwords equality
                if (newPasswordInput.value !== newPasswordConfirmInput.value) {
                    const msg = i18next.t("validation.passwords_missmatch")
                    result.push({ type: "error", loc: ["", "new_password"], msg })
                    result.push({
                        type: "error",
                        loc: ["", "new_password_confirm"],
                        msg,
                    })
                }
                return result
            },
        },
    )

    const setupTOTPForm = body.querySelector("form.setup-totp-form")
    if (setupTOTPForm) {
        const secretInput = setupTOTPForm.querySelector("input[name=secret]")
        const qrContainer = setupTOTPForm.querySelector(".qr-code-container")
        const codeInput = setupTOTPForm.querySelector("input[name=totp_code]")
        const setupModal = document.getElementById("setupTotpModal")

        setupModal.addEventListener("show.bs.modal", () => {
            const secret = generateTOTPSecret()
            const accountName = setupTOTPForm.dataset.accountName
            secretInput.value = secret
            qrContainer.innerHTML = generateTOTPQRCode(secret, accountName)
        })

        // Clear sensitive data on modal close
        setupModal.addEventListener("hidden.bs.modal", () => {
            secretInput.value = ""
            qrContainer.innerHTML = ""
            codeInput.value = ""
        })

        configureStandardForm(setupTOTPForm, () => {
            console.debug("onSetupTOTPFormSuccess")
            window.location.reload()
        })
    }

    // Generic authentication method disable handling
    const disableAuthMethodModal = document.getElementById("disableAuthMethodModal")
    const disableAuthMethodForm = disableAuthMethodModal.querySelector("form")

    disableAuthMethodModal.addEventListener("show.bs.modal", (event: Event) => {
        const button = (event as any).relatedTarget as HTMLButtonElement
        const action = button.dataset.authAction
        const method = button
            .closest("tr")
            .querySelector("h6")
            .textContent.toLocaleLowerCase()
        disableAuthMethodForm.action = action
        disableAuthMethodModal.querySelector(".modal-title").textContent = i18next.t(
            "settings.disable_method",
            { method },
        )
    })

    configureStandardForm(disableAuthMethodForm, () => {
        console.debug("onDisableAuthMethodSuccess")
        window.location.reload()
    })

    const revokeTokenForms = body.querySelectorAll("form.revoke-token-form")
    for (const form of revokeTokenForms) {
        configureStandardForm(form, () => {
            // On success callback, remove the HTML element or redirect to login page
            const row = form.closest("li")
            const isCurrentSession = row.querySelector(".current-session") !== null
            console.debug(
                "onRevokeTokenFormSuccess",
                isCurrentSession ? "(current session)" : "(other session)",
            )

            if (isCurrentSession) {
                window.location.href = `/login?${qsEncode({ referer: window.location.pathname + window.location.search })}`
            } else {
                row.remove()
            }
        })
    }
})
