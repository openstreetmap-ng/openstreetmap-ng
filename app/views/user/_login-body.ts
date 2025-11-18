import { mount } from "../lib/mount"
import { qsParse } from "../lib/qs"
import { configureStandardForm } from "../lib/standard-form"

type LoginState = "login" | "totp" | "recovery"

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
    const cancelBtn = loginForm.querySelector(".cancel-auth-btn")
    const toggleRecoveryBtn = loginForm.querySelector(".toggle-recovery-btn")
    const toggleTotpBtn = loginForm.querySelector(".toggle-totp-btn")
    const totpInputRegex = /^\d$/

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

    // Configure login form
    configureStandardForm(
        loginForm,
        (data) => {
            if (data.totp_required) {
                console.info("onLoginFormTOTPRequired")
                setState("totp")
                return
            }

            console.debug("onLoginFormSuccess", referrer)
            if (referrer !== defaultReferrer) {
                window.location.href = `${window.location.origin}${referrer}`
            } else {
                window.location.reload()
            }
        },
        {
            removeEmptyFields: true,
        },
    )

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

        const loginInput = loginForm.querySelector("input[name=display_name_or_email]")
        loginInput.value = dataset.login

        const passwordInput = loginForm.querySelector("input[data-name=password]")
        passwordInput.value = dataset.password

        const rememberInput = loginForm.querySelector("input[name=remember]")
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
