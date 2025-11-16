import { mount } from "../lib/mount"
import { qsParse } from "../lib/qs"
import { configureStandardForm } from "../lib/standard-form"

const loginForm = document.querySelector("form.login-form")
if (loginForm) {
    const defaultReferrer = `${window.location.pathname}${window.location.search}`
    const params = qsParse(window.location.search)
    let referrer = params.referer ?? defaultReferrer
    // Referrer must start with '/' to avoid open redirect
    if (!referrer.startsWith("/")) referrer = defaultReferrer

    const totpCodeSection = loginForm.querySelector(".totp-code-section")
    const totpDigitInputs = loginForm.querySelectorAll(
        ".totp-digit",
    ) as NodeListOf<HTMLInputElement>
    const totpCodeInput = loginForm.querySelector(
        "input[name=totp_code]",
    ) as HTMLInputElement

    // Configure 6-input TOTP field with auto-focus, auto-paste, and auto-submit
    const configureTOTPInputs = (): void => {
        if (totpDigitInputs.length !== 6) return

        // Helper to get all digit values as a string
        const getTOTPCode = (): string => {
            return Array.from(totpDigitInputs)
                .map((input) => input.value)
                .join("")
        }

        // Helper to update hidden input and check if complete
        const updateHiddenInput = (): void => {
            const code = getTOTPCode()
            totpCodeInput.value = code

            // Auto-submit when all 6 digits are filled
            if (code.length === 6 && /^\d{6}$/.test(code)) {
                loginForm.requestSubmit()
            }
        }

        totpDigitInputs.forEach((input, index) => {
            // Handle input - auto-focus next
            input.addEventListener("input", (e) => {
                const target = e.target as HTMLInputElement
                const value = target.value

                // Only allow digits
                if (value && !/^\d$/.test(value)) {
                    target.value = ""
                    return
                }

                // Update hidden input
                updateHiddenInput()

                // Auto-focus next input if digit was entered
                if (value && index < totpDigitInputs.length - 1) {
                    totpDigitInputs[index + 1].focus()
                    totpDigitInputs[index + 1].select()
                }
            })

            // Handle backspace - focus previous
            input.addEventListener("keydown", (e) => {
                const target = e.target as HTMLInputElement

                if (e.key === "Backspace" && !target.value && index > 0) {
                    totpDigitInputs[index - 1].focus()
                    totpDigitInputs[index - 1].select()
                }

                // Also allow arrow keys for navigation
                if (e.key === "ArrowLeft" && index > 0) {
                    e.preventDefault()
                    totpDigitInputs[index - 1].focus()
                    totpDigitInputs[index - 1].select()
                }
                if (e.key === "ArrowRight" && index < totpDigitInputs.length - 1) {
                    e.preventDefault()
                    totpDigitInputs[index + 1].focus()
                    totpDigitInputs[index + 1].select()
                }
            })

            // Handle paste - distribute digits across inputs
            input.addEventListener("paste", (e) => {
                e.preventDefault()
                const pastedData = e.clipboardData?.getData("text") || ""
                const digits = pastedData.replace(/\D/g, "").slice(0, 6)

                if (digits.length > 0) {
                    // Distribute digits starting from current input
                    for (let i = 0; i < digits.length && index + i < totpDigitInputs.length; i++) {
                        totpDigitInputs[index + i].value = digits[i]
                    }

                    // Focus the next empty input or last input
                    const nextEmptyIndex = index + digits.length
                    if (nextEmptyIndex < totpDigitInputs.length) {
                        totpDigitInputs[nextEmptyIndex].focus()
                    } else {
                        totpDigitInputs[totpDigitInputs.length - 1].focus()
                    }

                    updateHiddenInput()
                }
            })

            // Select all on focus for easy replacement
            input.addEventListener("focus", () => {
                input.select()
            })
        })
    }

    // Initialize TOTP inputs when section becomes visible
    const observer = new MutationObserver(() => {
        if (totpCodeSection && !totpCodeSection.classList.contains("d-none")) {
            configureTOTPInputs()
            // Focus first input when section shows
            totpDigitInputs[0]?.focus()
            observer.disconnect()
        }
    })

    if (totpCodeSection) {
        observer.observe(totpCodeSection, { attributes: true, attributeFilter: ["class"] })
    }

    // On successful login (or 2FA required), handle appropriately
    configureStandardForm(
        loginForm,
        (data) => {
            // Check if 2FA is required
            if (data && typeof data === "object" && "requires_2fa" in data && data.requires_2fa) {
                console.debug("2FA required, showing code input")
                // Show TOTP code section
                totpCodeSection?.classList.remove("d-none")
                // Focus on TOTP input
                totpCodeInput?.focus()
                // Don't redirect - let user enter 2FA code
                return
            }

            // Normal login success - redirect
            console.debug("onLoginFormSuccess", referrer)
            if (referrer !== defaultReferrer) {
                window.location.href = `${window.location.origin}${referrer}`
            } else {
                window.location.reload()
            }
        },
    )

    // Propagate referer to auth providers forms
    const authProvidersForms = document.querySelectorAll(".auth-providers form")
    for (const form of authProvidersForms) {
        const referrerInput = form.elements.namedItem("referer") as HTMLInputElement
        if (referrerInput) referrerInput.value = referrer
    }

    // Autofill buttons are present in development environment
    const onAutofillButtonClick = ({ target }: Event): void => {
        const dataset = (target as HTMLButtonElement).dataset
        console.debug("onAutofillButtonClick", dataset)

        const loginInput = loginForm.elements.namedItem(
            "display_name_or_email",
        ) as HTMLInputElement
        loginInput.value = dataset.login

        const passwordInput = loginForm.querySelector(
            "input[type=password][data-name=password]",
        ) as HTMLInputElement
        passwordInput.value = dataset.password

        const rememberInput = loginForm.elements.namedItem(
            "remember",
        ) as HTMLInputElement
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
