import { assert } from "@lib/assert"
import { mount } from "@lib/mount"
import { type LoginResponse, LoginResponseSchema } from "@lib/proto/shared_pb"
import { qsParse } from "@lib/qs"
import { configureStandardForm } from "@lib/standard-form"
import { NON_DIGIT_RE } from "@lib/utils"
import { getPasskeyAssertion, startConditionalMediation } from "@lib/webauthn"

type LoginState = "credentials" | "passkey" | "totp" | "recovery" | "method-select"

const loginForm = document.querySelector("form.login-form")
if (loginForm) {
    const defaultReferrer = `${window.location.pathname}${window.location.search}`
    const params = qsParse(window.location.search)
    let referrer = params.referer ?? defaultReferrer
    // Referrer must start with '/' to avoid open redirect
    if (!referrer.startsWith("/")) referrer = defaultReferrer

    const totpInputGroup = loginForm.querySelector(".totp-input-group")!
    const totpInputTemplate = totpInputGroup.firstElementChild as HTMLInputElement
    const totpCodeInput = loginForm.querySelector("input[name=totp_code]")!
    const bypass2faInput = loginForm.querySelector("input[name=bypass_2fa]")!
    const recoveryCodeInput = loginForm.querySelector("input[name=recovery_code]")!
    const cancelButtons = loginForm.querySelectorAll(".cancel-2fa-btn")
    const tryAnotherMethodButtons = loginForm.querySelectorAll(
        ".try-another-method-btn",
    )
    const methodOptions = loginForm.querySelectorAll("button[data-method]")
    const displayNameInput = loginForm.querySelector(
        "input[name=display_name_or_email]",
    )!
    const passwordInput = loginForm.querySelector("input[data-name=password]")!
    const rememberInput = loginForm.querySelector("input[name=remember]")!
    const passkeyButton = document.querySelector(".passkey-btn")!
    const passkeyRetryButton = loginForm.querySelector(".retry-passkey-btn")!

    let conditionalMediationAbort: AbortController | undefined
    let conditionalMediationAssertion: Blob | null = null
    let passwordless = false
    let loginResponse: LoginResponse | undefined
    let submittedFormData: FormData | undefined

    const isDigit = (c: string) => c.length === 1 && c >= "0" && c <= "9"

    const navigateOnSuccess = () => {
        console.debug("onLoginSuccess", referrer)
        if (referrer !== defaultReferrer) {
            window.location.href = `${window.location.origin}${referrer}`
        } else {
            window.location.reload()
        }
    }

    const tryTOTPSubmit = () => {
        assert(loginResponse)
        const inputs = totpInputGroup.children as HTMLCollectionOf<HTMLInputElement>
        const code = Array.from(inputs, (input) => input.value).join("")
        if (code.length !== loginResponse.totp) return false

        totpCodeInput.value = code
        loginForm.requestSubmit()
        return true
    }

    const createTOTPInputs = () => {
        assert(loginResponse)
        // Clear all except template
        while (totpInputGroup.children.length > 1) {
            totpInputGroup.lastElementChild!.remove()
        }

        // Clone template to create remaining inputs
        while (totpInputGroup.children.length < loginResponse.totp!) {
            const clone = totpInputTemplate.cloneNode(true) as HTMLInputElement
            clone.autocomplete = "off"
            totpInputGroup.appendChild(clone)
        }

        // Setup event handlers
        const inputs = totpInputGroup.children as HTMLCollectionOf<HTMLInputElement>
        for (let index = 0; index < inputs.length; index++) {
            const input = inputs[index]
            input.value = ""

            input.addEventListener("input", () => {
                if (!isDigit(input.value)) {
                    input.value = ""
                    return
                }
                if (index < inputs.length - 1) {
                    inputs[index + 1].focus()
                    inputs[index + 1].select()
                } else {
                    tryTOTPSubmit()
                }
            })

            input.addEventListener("keydown", (e: KeyboardEvent) => {
                if (e.key === "Backspace" && !input.value && index) {
                    inputs[index - 1].focus()
                    inputs[index - 1].select()
                } else if (e.key === "ArrowLeft" && index) {
                    e.preventDefault()
                    inputs[index - 1].focus()
                    inputs[index - 1].select()
                } else if (e.key === "ArrowRight" && index < inputs.length - 1) {
                    e.preventDefault()
                    inputs[index + 1].focus()
                    inputs[index + 1].select()
                }
            })

            input.addEventListener("focus", () => input.select())

            input.addEventListener("paste", (e: ClipboardEvent) => {
                e.preventDefault()
                const digits = e
                    .clipboardData!.getData("text")
                    .replace(NON_DIGIT_RE, "")
                if (!digits.length) return

                for (let i = 0; i < digits.length && index + i < inputs.length; i++) {
                    inputs[index + i].value = digits[i]
                }
                inputs[Math.min(index + digits.length, inputs.length - 1)].focus()
                tryTOTPSubmit()
            })
        }
    }

    const setState = (state: LoginState) => {
        console.debug("setLoginState", state)
        loginForm.dataset.loginState = state

        totpCodeInput.value = ""
        recoveryCodeInput.value = ""

        if (state === "totp") {
            createTOTPInputs()
            totpInputTemplate.focus()
        } else if (state === "recovery") {
            recoveryCodeInput.focus()
        } else if (state === "method-select") {
            // Update method visibility based on available methods
            assert(loginResponse)
            for (const option of methodOptions) {
                const method = option.dataset.method
                const isAvailable =
                    (method === "passkey" && loginResponse.passkey) ||
                    (method === "totp" && loginResponse.totp) ||
                    (method === "recovery" && loginResponse.recovery) ||
                    method === "bypass"
                option.classList.toggle("d-none", !isAvailable)
            }
        }
    }

    // State transition handlers
    for (const button of cancelButtons)
        button.addEventListener("click", () => setState("credentials"))
    for (const button of tryAnotherMethodButtons)
        button.addEventListener("click", () => setState("method-select"))
    for (const option of methodOptions) {
        option.addEventListener("click", () => {
            const method = option.dataset.method
            if (method === "passkey") startPasskey2FA()
            else if (method === "totp") setState("totp")
            else if (method === "recovery") setState("recovery")
            else if (method === "bypass") {
                bypass2faInput.value = "true"
                loginForm.requestSubmit()
            }
        })
    }

    const startPasskey2FA = async () => {
        assert(submittedFormData)
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
        (response) => {
            if (!response) {
                navigateOnSuccess()
                return
            }
            loginResponse = response
            if (loginResponse.passkey) {
                console.info("onLoginFormPasskeyRequired")
                startPasskey2FA()
                return
            }
            if (loginResponse.totp) {
                console.info("onLoginFormTOTPRequired")
                setState("totp")
                return
            }
            navigateOnSuccess()
        },
        {
            removeEmptyFields: true,
            protobuf: LoginResponseSchema,
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
                        return result
                    }
                    formData.set("passkey", result)
                }
                return null
            },
        },
    )

    const requestSubmitPasswordless = () => {
        passwordless = true
        displayNameInput.required = false
        passwordInput.required = false
        loginForm.requestSubmit()
    }

    // Passkey button triggers form submit with passkey auth method (Mode 1)
    passkeyButton.addEventListener("click", requestSubmitPasswordless)

    // Fallback button handler (Mode 2)
    passkeyRetryButton.addEventListener("click", startPasskey2FA)

    // Conditional mediation: passkey autofill
    const initConditionalMediation = async () => {
        conditionalMediationAbort = new AbortController()
        const assertion = await startConditionalMediation(
            conditionalMediationAbort.signal,
        )
        if (!assertion) return
        conditionalMediationAssertion = assertion
        requestSubmitPasswordless()
    }

    // Start conditional mediation based on context
    const loginModal = document.getElementById("loginModal")
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
    const onAutofillButtonClick = ({ target }: Event) => {
        const dataset = (target as HTMLElement).dataset
        console.debug("onAutofillButtonClick", dataset)

        displayNameInput.value = dataset.login!
        passwordInput.value = dataset.password!
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
    )!
    navbarLoginButton.removeAttribute("data-bs-target")
    navbarLoginButton.removeAttribute("data-bs-toggle")
    navbarLoginButton.addEventListener("click", () => {
        window.location.reload()
    })
})
