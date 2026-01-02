import { configureCopyGroups } from "@lib/copy-group"
import { mount } from "@lib/mount"
import { qsEncode } from "@lib/qs"
import { type APIDetail, configureStandardForm } from "@lib/standard-form"
import { resolveUserAgentIconsLazy } from "@lib/user-agent-icons"
import { NON_DIGIT_RE } from "@lib/utils"
import { getPasskeyRegistration } from "@lib/webauthn"
import { encodeBase32 } from "@std/encoding/base32"
import { t } from "i18next"

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

mount("settings-security-body", (body) => {
    // Password change
    const passwordForm = body.querySelector("form.password-form")!
    const newPasswordInput = passwordForm.querySelector(
        "input[type=password][data-name=new_password]",
    )!
    const newPasswordConfirmInput = passwordForm.querySelector(
        "input[type=password][data-name=new_password_confirm]",
    )!

    configureStandardForm(
        passwordForm,
        () => {
            // On success callback, reset the password change form
            console.debug("Security: Password changed")
            passwordForm.reset()
        },
        {
            validationCallback: () => {
                const result: APIDetail[] = []
                // Validate passwords equality
                if (newPasswordInput.value !== newPasswordConfirmInput.value) {
                    const msg = t("validation.passwords_missmatch")
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

    // Passkey registration
    const addPasskeyForm = body.querySelector("form.add-passkey-form")
    if (addPasskeyForm) {
        configureStandardForm(
            addPasskeyForm,
            () => {
                console.debug("Security: Passkey added")
                window.location.reload()
            },
            {
                formBody: addPasskeyForm.closest(".table-responsive")!,
                validationCallback: async (formData) => {
                    const result = await getPasskeyRegistration()
                    if (typeof result === "string") return result
                    formData.set("passkey", result)
                    return null
                },
            },
        )
    }

    // Passkey rename
    const renameButtons = body.querySelectorAll("button.passkey-rename-btn")
    for (const renameButton of renameButtons) {
        const nameSpan = renameButton.parentElement!.querySelector(".passkey-name")!
        renameButton.addEventListener("click", async () => {
            const oldName = nameSpan.textContent
            const newName =
                prompt(t("two_fa.enter_new_passkey_name"), oldName)?.trim() ?? ""
            if (newName === oldName) return

            const credentialId = renameButton.dataset.credentialId
            const formData = new FormData()
            formData.set("name", newName)

            const resp = await fetch(
                `/api/web/settings/passkey/${credentialId}/rename`,
                {
                    method: "POST",
                    body: formData,
                    priority: "high",
                },
            )

            if (resp.ok) {
                const data = await resp.json()
                nameSpan.textContent = data.name
            }
        })
    }

    // Authenticator app
    const setupModal = document.getElementById("setupTotpModal")
    if (setupModal) {
        const setupTOTPForm = setupModal.querySelector("form")!
        const digitsInputs = setupTOTPForm.querySelectorAll("input[name=digits]")
        const secretInput = setupTOTPForm.querySelector("input[name=secret]")!
        const qrContainer = setupTOTPForm.querySelector(".qr-code-container")!
        const codeInput = setupTOTPForm.querySelector("input[name=totp_code]")!
        const accountName = setupTOTPForm.dataset.accountName!

        // Select secret on click for easy copying
        secretInput.addEventListener("click", () => {
            secretInput.select()
        })

        // Strip non-digit characters from code input
        codeInput.addEventListener("input", () => {
            codeInput.value = codeInput.value.replace(NON_DIGIT_RE, "")
        })

        // Update QR code and input attributes when digit selection changes
        for (const radio of digitsInputs) {
            radio.addEventListener("change", async () => {
                const digits = Number(radio.value)
                qrContainer.innerHTML = await generateTOTPQRCode(
                    secretInput.value,
                    digits,
                    accountName,
                )
                codeInput.placeholder = "0".repeat(digits)
                codeInput.pattern = `[0-9]{${digits}}`

                codeInput.maxLength = 100
                codeInput.minLength = digits
                codeInput.maxLength = digits
            })
        }

        setupModal.addEventListener("show.bs.modal", () => {
            secretInput.value = generateTOTPSecret()
            digitsInputs[0].checked = true
            digitsInputs[0].dispatchEvent(new Event("change"))
        })

        setupModal.addEventListener("shown.bs.modal", () => {
            codeInput.focus()
        })

        // Clear sensitive data on modal close
        setupModal.addEventListener("hidden.bs.modal", () => {
            setupTOTPForm.reset()
            qrContainer.innerHTML = ""
        })

        configureStandardForm(setupTOTPForm, () => {
            console.debug("Security: TOTP setup complete")
            window.location.reload()
        })
    }

    // Generic authentication method disable handling
    const disableAuthMethodModal = document.getElementById("disableAuthMethodModal")!
    const disableAuthMethodForm = disableAuthMethodModal.querySelector("form")!

    disableAuthMethodModal.addEventListener("show.bs.modal", (e) => {
        const button = e.relatedTarget as HTMLButtonElement
        disableAuthMethodForm.action = button.dataset.authAction!
        disableAuthMethodModal.querySelector(".modal-title")!.textContent =
            button.dataset.title!
    })

    configureStandardForm(disableAuthMethodForm, () => {
        console.debug("Security: Auth method disabled")
        window.location.reload()
    })

    // Recovery codes generation
    const generateRecoveryCodesModal = document.getElementById(
        "generateRecoveryCodesModal",
    )!
    const generateRecoveryCodesForm = generateRecoveryCodesModal.querySelector("form")!
    const generateRecoveryCodesBody = generateRecoveryCodesForm.parentElement!

    generateRecoveryCodesModal.addEventListener("hide.bs.modal", () => {
        if (generateRecoveryCodesModal.querySelector("form")) {
            generateRecoveryCodesForm.reset()
            return
        }
        window.location.reload()
    })

    configureStandardForm(generateRecoveryCodesForm, (data) => {
        console.debug("Security: Recovery codes generated")
        generateRecoveryCodesBody.innerHTML = data.detail
        configureCopyGroups(generateRecoveryCodesBody)
    })

    const revokeTokenForms = body.querySelectorAll("form.revoke-token-form")
    for (const form of revokeTokenForms) {
        configureStandardForm(form, () => {
            // On success callback, remove the HTML element or redirect to login page
            const row = form.closest("li")!
            const isCurrentSession = row.querySelector(".current-session") !== null
            console.debug(
                "Security: Token revoked",
                isCurrentSession ? "(current session)" : "(other session)",
            )

            if (isCurrentSession) {
                window.location.href = `/login${qsEncode({ referer: window.location.pathname + window.location.search })}`
            } else {
                row.remove()
            }
        })
    }

    resolveUserAgentIconsLazy(body)
})
