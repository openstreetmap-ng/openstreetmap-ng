import i18next from "i18next"
import qrcode from "qrcode-generator"
import { mount } from "../lib/mount"
import { qsEncode } from "../lib/qs"
import { type APIDetail, configureStandardForm } from "../lib/standard-form"
import { getPageTitle } from "../lib/utils"

// Base32 encoding for TOTP secrets (RFC 4648)
const base32Encode = (buffer: Uint8Array): string => {
    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    let bits = 0
    let value = 0
    let output = ""

    for (const byte of buffer) {
        value = (value << 8) | byte
        bits += 8

        while (bits >= 5) {
            output += alphabet[(value >>> (bits - 5)) & 31]
            bits -= 5
        }
    }

    if (bits > 0) {
        output += alphabet[(value << (5 - bits)) & 31]
    }

    return output
}

// Generate a cryptographically secure TOTP secret
const generateTOTPSecret = (): string => {
    const buffer = new Uint8Array(32) // 256 bits
    crypto.getRandomValues(buffer)
    return base32Encode(buffer)
}

// Generate otpauth:// URI for QR code
const generateTOTPUri = (secret: string, accountName: string): string => {
    const issuer = "OpenStreetMap"
    const label = `${issuer}:${accountName}`
    return `otpauth://totp/${encodeURIComponent(label)}?secret=${secret}&issuer=${encodeURIComponent(issuer)}&algorithm=SHA1&digits=6&period=30`
}

// Generate QR code as SVG
const generateQRCode = (text: string): string => {
    const qr = qrcode(0, "M")
    qr.addData(text)
    qr.make()
    return qr.createSvgTag(4, 0)
}

mount("settings-security-body", (body) => {
    const passwordForm = body.querySelector("form.password-form")
    if (!passwordForm) throw new Error("passwordForm not found on security page")

    const newPasswordInput = passwordForm.querySelector<HTMLInputElement>(
        "input[type=password][data-name=new_password]",
    )
    if (!newPasswordInput) throw new Error("newPasswordInput not found")

    const newPasswordConfirmInput = passwordForm.querySelector<HTMLInputElement>(
        "input[type=password][data-name=new_password_confirm]",
    )
    if (!newPasswordConfirmInput) throw new Error("newPasswordConfirmInput not found")

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

    // === 2FA Setup Form ===
    const setupTOTPForm = body.querySelector("form.setup-totp-form")
    if (setupTOTPForm) {
        // Get user's email or display name for QR code
        const accountName = getPageTitle().split("|")[0].trim()

        // Generate secret on modal show
        const setupModal = document.getElementById("setup2FAModal")
        setupModal?.addEventListener("show.bs.modal", () => {
            const secret = generateTOTPSecret()
            const uri = generateTOTPUri(secret, accountName)

            // Store secret in hidden input
            const secretInput = setupTOTPForm.querySelector(".totp-secret-input")
            secretInput.value = secret

            // Display secret for manual entry
            const secretDisplay = setupTOTPForm.querySelector(".totp-secret-display")
            secretDisplay.textContent = secret

            // Generate and display QR code
            const qrContainer = setupTOTPForm.querySelector(".qr-code-container")
            qrContainer.innerHTML = generateQRCode(uri)

            // Focus on code input
            const codeInput = setupTOTPForm.querySelector<HTMLInputElement>(".totp-code-input")
            setTimeout(() => codeInput.focus(), 100)
        })

        // Clear sensitive data on modal close (security measure)
        setupModal?.addEventListener("hide.bs.modal", () => {
            const secretInput = setupTOTPForm.querySelector<HTMLInputElement>(".totp-secret-input")
            const secretDisplay = setupTOTPForm.querySelector(".totp-secret-display")
            const qrContainer = setupTOTPForm.querySelector(".qr-code-container")
            const codeInput = setupTOTPForm.querySelector<HTMLInputElement>(".totp-code-input")

            secretInput.value = ""
            secretDisplay.textContent = ""
            qrContainer.innerHTML = ""
            codeInput.value = ""
        })

        // Configure form submission
        configureStandardForm(setupTOTPForm, () => {
            console.debug("onSetupTOTPFormSuccess")
            // Reload page to show updated 2FA status
            window.location.reload()
        })
    }

    // === 2FA Disable Form ===
    const disableTOTPForm = body.querySelector("form.disable-totp-form")
    if (disableTOTPForm) {
        configureStandardForm(disableTOTPForm, () => {
            console.debug("onDisableTOTPFormSuccess")
            // Reload page to show updated 2FA status
            window.location.reload()
        })
    }
})
