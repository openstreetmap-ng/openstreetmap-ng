import { mount } from "@lib/mount"
import { type LoginResponse, LoginResponseSchema } from "@lib/proto/shared_pb"
import { qsParse } from "@lib/qs"
import { configureStandardForm } from "@lib/standard-form"
import { NON_DIGIT_RE } from "@lib/utils"
import { getPasskeyAssertion, startConditionalMediation } from "@lib/webauthn"
import { assertExists } from "@std/assert"
import { Modal } from "bootstrap"

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
    const displayNameInput = loginForm.querySelector(
        "input[name=display_name_or_email]",
    )!
    const passwordInput = loginForm.querySelector("input[data-name=password]")!
    const rememberInput = loginForm.querySelector("input[name=remember]")!

    let conditionalMediationAbort: AbortController | undefined
    let passkeyAssertion: Blob | null = null
    let passkey: boolean | "passwordless" = false
    let loginResponse: LoginResponse | undefined

    const setLoginState = (state: LoginState) => {
        console.debug("Login: State changed", state)
        loginForm.dataset.loginState = state
        switch (state) {
            case "totp":
                createTOTPInputs()
                totpInputTemplate.focus()
                totpCodeInput.value = ""
                break
            case "recovery":
                recoveryCodeInput.value = ""
                recoveryCodeInput.focus()
                break
            case "method-select":
                assertExists(loginResponse)
                for (const option of loginForm.querySelectorAll(
                    "button[data-action^='method-']",
                )) {
                    const action = option.dataset.action
                    const isAvailable =
                        (action === "method-passkey" && loginResponse.passkey) ||
                        (action === "method-totp" && loginResponse.totp) ||
                        (action === "method-recovery" && loginResponse.recovery) ||
                        action === "method-bypass"
                    option.classList.toggle("d-none", !isAvailable)
                }
                break
        }
    }
    setLoginState("credentials")

    const tryTOTPSubmit = () => {
        assertExists(loginResponse)
        const inputs = totpInputGroup.children as HTMLCollectionOf<HTMLInputElement>
        const code = Array.from(inputs, (input) => input.value).join("")
        if (code.length !== loginResponse.totp) return false

        totpCodeInput.value = code
        loginForm.requestSubmit()
        return true
    }

    const createTOTPInputs = () => {
        assertExists(loginResponse)
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
                if (
                    input.value.length !== 1 ||
                    input.value < "0" ||
                    input.value > "9"
                ) {
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

    const requestSubmitPasswordless = () => {
        passkey = "passwordless"
        displayNameInput.required = false
        passwordInput.required = false
        loginForm.requestSubmit()
    }

    const requestSubmitPasskey = () => {
        passkey = true
        loginForm.requestSubmit()
    }

    // Configure login form with unified passkey/password flow
    configureStandardForm(
        loginForm,
        (response) => {
            if (!response) {
                window.location.href = referrer
                return
            }
            loginResponse = response
            if (loginResponse.passkey) {
                requestSubmitPasskey()
                return
            }
            if (loginResponse.totp) {
                setLoginState("totp")
                return
            }
            window.location.href = referrer
        },
        {
            removeEmptyFields: true,
            protobuf: LoginResponseSchema,
            validationCallback: async (formData) => {
                conditionalMediationAbort?.abort()
                if (!passkey) return null

                const isPasswordless = passkey === "passwordless"
                passkey = false

                // Restore required attributes
                if (isPasswordless) {
                    displayNameInput.required = true
                    passwordInput.required = true
                }

                // Consume passkey assertion or request a new one
                const result =
                    passkeyAssertion ??
                    (await getPasskeyAssertion(
                        formData,
                        isPasswordless ? "required" : "discouraged",
                    ))
                passkeyAssertion = null

                if (typeof result === "string") {
                    if (!isPasswordless) setLoginState("passkey")
                    return isPasswordless ? result : null
                }

                formData.set("passkey", result)
                return null
            },
        },
    )

    // Delegated click handler for login UI actions
    loginForm.addEventListener("click", (e: Event) => {
        const target = (e.target as Element).closest("button[data-action]")
        if (!target) return

        const action = target.dataset.action!
        switch (action) {
            case "passkey-login":
                requestSubmitPasswordless()
                break
            case "cancel-2fa":
                setLoginState("credentials")
                break
            case "another-method":
                setLoginState("method-select")
                break
            case "method-passkey":
                requestSubmitPasskey()
                break
            case "method-totp":
                setLoginState("totp")
                break
            case "method-recovery":
                setLoginState("recovery")
                break
            case "method-bypass":
                bypass2faInput.value = "true"
                loginForm.requestSubmit()
                break
        }
    })

    // Conditional mediation: passkey autofill
    const initConditionalMediation = async () => {
        conditionalMediationAbort = new AbortController()
        const assertion = await startConditionalMediation(
            conditionalMediationAbort.signal,
        )
        if (!assertion) return
        passkeyAssertion = assertion
        requestSubmitPasswordless()
    }

    // Start conditional mediation based on context
    const loginModal = document.getElementById("loginModal")
    if (loginModal) {
        // Modal: defer until it opens
        loginModal.addEventListener(Modal.Events.show, initConditionalMediation, {
            once: true,
        })
    } else {
        // Embedded: start shortly after
        setTimeout(initConditionalMediation, 100)
    }

    // Propagate referer to auth providers forms
    for (const input of document.querySelectorAll(
        ".auth-providers input[name=referer]",
    )) {
        input.value = referrer
    }

    // Autofill buttons
    for (const btn of document.querySelectorAll("button[data-login][data-password]")) {
        btn.addEventListener("click", () => {
            displayNameInput.value = btn.dataset.login!
            passwordInput.value = btn.dataset.password!
            rememberInput.checked = true
            loginForm.requestSubmit()
        })
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
