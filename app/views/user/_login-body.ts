import { mount } from "../lib/mount"
import { qsParse } from "../lib/qs"
import { configureStandardForm } from "../lib/standard-form"
import { getPasskeyAssertion, startConditionalMediation } from "../lib/webauthn"

type LoginState = "login" | "passkey" | "totp" | "recovery"

const loginForm = document.querySelector("form.login-form")
if (loginForm) {
    const defaultReferrer = `${window.location.pathname}${window.location.search}`
    const params = qsParse(window.location.search)
    let referrer = params.referer ?? defaultReferrer
    // Referrer must start with '/' to avoid open redirect
    if (!referrer.startsWith("/")) referrer = defaultReferrer

    const totpDigitInputs = loginForm.querySelectorAll("input.totp-digit")
    const totpCodeInput = loginForm.querySelector("input[name=totp_code]")
    const recoveryCodeInput = loginForm.querySelector("input[name=recovery_code]")
    const cancelBtns = loginForm.querySelectorAll(".cancel-auth-btn")
    const toggleRecoveryBtn = loginForm.querySelector(".toggle-recovery-btn")
    const toggleTotpBtn = loginForm.querySelector(".toggle-totp-btn")
    const totpInputRegex = /^\d$/
    const displayNameInput = loginForm.querySelector(
        "input[name=display_name_or_email]",
    )
    const passwordInput = loginForm.querySelector("input[data-name=password]")
    const rememberInput = loginForm.querySelector("input[name=remember]")
    const passkeyBtn = document.querySelector(".passkey-btn")
    const retryPasskeyBtn = loginForm.querySelector(".retry-passkey-btn")
    const useTotpBtn = loginForm.querySelector(".use-totp-btn")
    const useRecoveryBtn = loginForm.querySelector(".use-recovery-btn")

    let conditionalMediationAbort: AbortController | null = null
    let conditionalMediationAssertion: Blob | null = null
    let passwordless = false
    let passkeyHasTotpFallback = false
    let submittedFormData: FormData | null = null

    const navigateOnSuccess = (): void => {
        console.debug("onLoginSuccess", referrer)
        if (referrer !== defaultReferrer) {
            window.location.href = `${window.location.origin}${referrer}`
        } else {
            window.location.reload()
        }
    }

    // Set the login form state and focus the appropriate input.
    const setState = (state: LoginState): void => {
        console.debug("setLoginState", state)
        loginForm.setAttribute("data-login-state", state)

        totpCodeInput.value = ""
        recoveryCodeInput.value = ""

        if (state === "totp") {
            for (const input of totpDigitInputs) input.value = ""
            totpDigitInputs[0].focus()
        } else if (state === "recovery") {
            recoveryCodeInput.focus()
        }
    }

    // State transition handlers
    for (const cancelBtn of cancelBtns)
        cancelBtn.addEventListener("click", () => setState("login"))
    toggleRecoveryBtn.addEventListener("click", () => setState("recovery"))
    toggleTotpBtn.addEventListener("click", () => setState("totp"))

    /**
     * Tries to submit the TOTP code.
     * @returns Whether the submission was successful.
     */
    const tryTOTPSubmit = (): boolean => {
        const code = Array.from(totpDigitInputs)
            .map((input) => input.value)
            .join("")
        if (code.length !== 6) return false

        totpCodeInput.value = code
        loginForm.requestSubmit()
        return true
    }

    totpDigitInputs.forEach((input, index) => {
        input.addEventListener("input", () => {
            // Validate digit input
            if (!totpInputRegex.test(input.value)) {
                input.value = ""
                return
            }

            // Submit or focus next
            if (index < totpDigitInputs.length - 1) {
                totpDigitInputs[index + 1].focus()
                totpDigitInputs[index + 1].select()
            } else {
                tryTOTPSubmit()
            }
        })

        // Improve keyboard navigation
        input.addEventListener("keydown", (e) => {
            if (e.key === "Backspace" && !input.value && index) {
                totpDigitInputs[index - 1].focus()
                totpDigitInputs[index - 1].select()
            } else if (e.key === "ArrowLeft" && index) {
                e.preventDefault()
                totpDigitInputs[index - 1].focus()
                totpDigitInputs[index - 1].select()
            } else if (e.key === "ArrowRight" && index < totpDigitInputs.length - 1) {
                e.preventDefault()
                totpDigitInputs[index + 1].focus()
                totpDigitInputs[index + 1].select()
            }
        })

        // Select all on focus for easy replacement
        input.addEventListener("focus", () => input.select())

        // Handle paste - distribute digits across inputs
        input.addEventListener("paste", (e) => {
            e.preventDefault()
            const pastedData = e.clipboardData?.getData("text") || ""
            const digits = pastedData.replace(/\D/g, "")
            if (!digits.length) return

            // Distribute digits starting from current input
            for (
                let i = 0;
                i < digits.length && index + i < totpDigitInputs.length;
                i++
            ) {
                totpDigitInputs[index + i].value = digits[i]
            }

            const focusIndex = Math.min(
                index + digits.length,
                totpDigitInputs.length - 1,
            )
            totpDigitInputs[focusIndex].focus()
            tryTOTPSubmit()
        })
    })

    /** Starts the passkey 2FA flow after password validation. */
    const startPasskey2FA = async () => {
        const result = await getPasskeyAssertion(submittedFormData, "discouraged")
        if (typeof result === "string") {
            setState("passkey")
            return
        }
        submittedFormData.set("passkey", result)
        const resp = await fetch(loginForm.action, {
            method: "POST",
            body: submittedFormData,
        })
        if (!resp.ok) {
            setState("passkey")
            return
        }
        navigateOnSuccess()
    }

    // Configure login form with unified passkey/password flow
    configureStandardForm(
        loginForm,
        (data) => {
            if (data.passkey_required) {
                console.info("onLoginFormPasskeyRequired", data)
                passkeyHasTotpFallback = data.has_totp
                useTotpBtn.classList.toggle("d-none", !passkeyHasTotpFallback)
                startPasskey2FA()
                return
            }
            if (data.totp_required) {
                console.info("onLoginFormTOTPRequired")
                setState("totp")
                return
            }
            navigateOnSuccess()
        },
        {
            removeEmptyFields: true,
            validationCallback: async (formData) => {
                conditionalMediationAbort?.abort()
                submittedFormData = formData
                if (passwordless) {
                    passwordless = false
                    displayNameInput.required = true
                    passwordInput.required = true

                    // Use stored conditional mediation assertion or perform WebAuthn
                    let result: Blob | string
                    if (conditionalMediationAssertion) {
                        result = conditionalMediationAssertion
                        conditionalMediationAssertion = null
                    } else {
                        result = await getPasskeyAssertion(formData)
                    }
                    if (typeof result === "string") {
                        setState("login")
                        return result
                    }
                    formData.set("passkey", result)
                }
                return null
            },
        },
    )

    // Passkey button triggers form submit with passkey auth method (Mode 1)
    passkeyBtn.addEventListener("click", () => {
        passwordless = true
        displayNameInput.required = false
        passwordInput.required = false
        loginForm.requestSubmit()
    })

    // Fallback button handlers (Mode 2)
    retryPasskeyBtn.addEventListener("click", startPasskey2FA)
    useTotpBtn.addEventListener("click", () => setState("totp"))
    useRecoveryBtn.addEventListener("click", () => setState("recovery"))

    // Conditional mediation: passkey autofill
    const initConditionalMediation = async () => {
        conditionalMediationAbort = new AbortController()
        const assertion = await startConditionalMediation(
            conditionalMediationAbort.signal,
        )
        if (!assertion) return
        conditionalMediationAssertion = assertion
        passwordless = true
        displayNameInput.required = false
        passwordInput.required = false
        loginForm.requestSubmit()
    }

    // Start conditional mediation based on context
    const loginModal = document.querySelector("#loginModal")
    if (loginModal) {
        // Modal: defer until it opens
        loginModal.addEventListener("show.bs.modal", initConditionalMediation, {
            once: true,
        })
    } else {
        // Embedded: start shortly after
        setTimeout(initConditionalMediation, 100)
    }

    // Propagate referer to auth providers forms
    const authProvidersForms = document.querySelectorAll(".auth-providers form")
    for (const form of authProvidersForms) {
        const referrerInput = form.querySelector("input[name=referer]")
        if (referrerInput) referrerInput.value = referrer
    }

    // Autofill buttons are present in development environment
    const onAutofillButtonClick = ({ target }: Event): void => {
        const dataset = (target as HTMLButtonElement).dataset
        console.debug("onAutofillButtonClick", dataset)

        displayNameInput.value = dataset.login
        passwordInput.value = dataset.password
        rememberInput.checked = true
        loginForm.requestSubmit()
    }

    const autofillButtons = document.querySelectorAll("button.autofill-btn")
    for (const btn of autofillButtons) {
        btn.addEventListener("click", onAutofillButtonClick)
    }
}

// On /login page, remove modal handling and instead reload the page
mount("login-body", () => {
    const navbarLoginButton = document.querySelector(
        "button[data-bs-target='#loginModal']",
    )
    navbarLoginButton.removeAttribute("data-bs-target")
    navbarLoginButton.removeAttribute("data-bs-toggle")
    navbarLoginButton.addEventListener("click", () => {
        window.location.reload()
    })
})
