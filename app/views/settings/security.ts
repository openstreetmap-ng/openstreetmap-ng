import { create, toBinary } from "@bufbuild/protobuf"
import i18next from "i18next"
import qrcode from "qrcode-generator"
import { configureCopyGroups } from "../lib/copy-group"
import { mount } from "../lib/mount"
import { PasskeyRegistrationSchema } from "../lib/proto/shared_pb"
import { qsEncode } from "../lib/qs"
import { type APIDetail, configureStandardForm } from "../lib/standard-form"
import { buildCredentialDescriptors, fetchPasskeyChallenge } from "../lib/webauthn"

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
    // Password change
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
            validationCallback: () => {
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

    // Passkey registration
    const addPasskeyModal = document.getElementById("addPasskeyModal")
    if (addPasskeyModal) {
        const addPasskeyForm = addPasskeyModal.querySelector("form")
        const nameInput = addPasskeyForm.querySelector("input[name=name]")

        addPasskeyModal.addEventListener("shown.bs.modal", () => {
            nameInput.focus()
        })

        addPasskeyModal.addEventListener("hidden.bs.modal", () => {
            addPasskeyForm.reset()
        })

        configureStandardForm(
            addPasskeyForm,
            () => {
                console.debug("onAddPasskeyFormSuccess")
                window.location.reload()
            },
            {
                formBody: addPasskeyForm.querySelector(".modal-body"),
                validationCallback: async (formData) => {
                    const challenge = await fetchPasskeyChallenge()
                    if (typeof challenge === "string") return challenge

                    // Convert user ID to bytes for WebAuthn
                    const userIdBytes = new Uint8Array(8)
                    new DataView(userIdBytes.buffer).setBigUint64(0, challenge.userId)

                    let credential: PublicKeyCredential | null = null
                    try {
                        credential = (await navigator.credentials.create({
                            publicKey: {
                                challenge: challenge.challenge as BufferSource,
                                rp: { name: i18next.t("project_name") },
                                user: {
                                    id: userIdBytes,
                                    name: challenge.userEmail,
                                    displayName: challenge.userDisplayName,
                                },
                                pubKeyCredParams: [
                                    { alg: -8, type: "public-key" }, // EdDSA
                                    { alg: -7, type: "public-key" }, // ES256
                                ],
                                excludeCredentials: buildCredentialDescriptors(
                                    challenge.credentials,
                                ),
                                authenticatorSelection: {
                                    residentKey: "preferred",
                                    userVerification: "required",
                                },
                            },
                        })) as PublicKeyCredential
                    } catch (e) {
                        console.warn("WebAuthn:", e)
                        return i18next.t(
                            "two_fa.could_not_complete_passkey_registration",
                        )
                    }
                    if (!credential) return ""

                    const response =
                        credential.response as AuthenticatorAttestationResponse
                    const registration = create(PasskeyRegistrationSchema, {
                        clientDataJson: new Uint8Array(response.clientDataJSON),
                        attestationObject: new Uint8Array(response.attestationObject),
                        transports: response.getTransports?.() ?? [],
                    })
                    formData.set(
                        "passkey",
                        new Blob([toBinary(PasskeyRegistrationSchema, registration)]),
                    )
                    return null
                },
            },
        )
    }

    // Authenticator app
    const setupModal = document.getElementById("setupTotpModal")
    if (setupModal) {
        const setupTOTPForm = setupModal.querySelector("form")
        const secretInput = setupTOTPForm.querySelector("input[name=secret]")
        const qrContainer = setupTOTPForm.querySelector(".qr-code-container")
        const codeInput = setupTOTPForm.querySelector("input[name=totp_code]")

        // Select secret on click for easy copying
        secretInput.addEventListener("click", () => {
            secretInput.select()
        })

        setupModal.addEventListener("show.bs.modal", () => {
            const secret = generateTOTPSecret()
            const accountName = setupTOTPForm.dataset.accountName
            secretInput.value = secret
            qrContainer.innerHTML = generateTOTPQRCode(secret, accountName)
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
            console.debug("onSetupTOTPFormSuccess")
            window.location.reload()
        })
    }

    // Generic authentication method disable handling
    const disableAuthMethodModal = document.getElementById("disableAuthMethodModal")
    const disableAuthMethodForm = disableAuthMethodModal.querySelector("form")

    disableAuthMethodModal.addEventListener("show.bs.modal", (event: Event) => {
        const button = (event as any).relatedTarget as HTMLButtonElement
        disableAuthMethodForm.action = button.dataset.authAction
        disableAuthMethodModal.querySelector(".modal-title").textContent =
            button.dataset.title
    })

    configureStandardForm(disableAuthMethodForm, () => {
        console.debug("onDisableAuthMethodSuccess")
        window.location.reload()
    })

    // Recovery codes generation
    const generateRecoveryCodesModal = document.getElementById(
        "generateRecoveryCodesModal",
    )
    const generateRecoveryCodesForm = generateRecoveryCodesModal.querySelector("form")
    const generateRecoveryCodesBody = generateRecoveryCodesForm.parentElement

    generateRecoveryCodesModal.addEventListener("hide.bs.modal", () => {
        if (!generateRecoveryCodesModal.querySelector("form")) {
            window.location.reload()
        } else {
            generateRecoveryCodesForm.reset()
        }
    })

    configureStandardForm(generateRecoveryCodesForm, (data) => {
        console.debug("onGenerateRecoveryCodesSuccess")
        generateRecoveryCodesBody.innerHTML = data.detail
        configureCopyGroups(generateRecoveryCodesBody)
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
