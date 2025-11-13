import { Collapse } from "bootstrap"
import i18next from "i18next"
import { activityTracking } from "../lib/config"
import { mount } from "../lib/mount"
import { type APIDetail, configureStandardForm } from "../lib/standard-form"

mount("signup-body", (body) => {
    const signupForm = body.querySelector("form.signup-form")
    const displayNameInput = signupForm.elements.namedItem(
        "display_name",
    ) as HTMLInputElement
    const displayNameBlacklist = displayNameInput.dataset.blacklist
    const passwordInput = signupForm.querySelector(
        "input[type=password][data-name=password]",
    )
    const passwordConfirmInput = signupForm.querySelector(
        "input[type=password][data-name=password_confirm]",
    )

    const trackingInput = signupForm.elements.namedItem("tracking") as HTMLInputElement
    trackingInput.value = activityTracking.toString()

    configureStandardForm(
        signupForm,
        ({ redirect_url }) => {
            console.debug("onSignupFormSuccess", redirect_url)
            window.location.href = redirect_url
        },
        {
            clientValidationCallback: () => {
                const result: APIDetail[] = []

                // Validate name for blacklisted characters
                const displayNameChars = new Set(displayNameInput.value)
                if (
                    displayNameBlacklist.split("").some((c) => displayNameChars.has(c))
                ) {
                    const msg = i18next.t("validations.url_characters", {
                        characters: displayNameBlacklist,
                        interpolation: { escapeValue: false },
                    })
                    result.push({ type: "error", loc: ["", "display_name"], msg })
                }

                // Validate passwords equality
                if (passwordInput.value !== passwordConfirmInput.value) {
                    const msg = i18next.t("validation.passwords_missmatch")
                    result.push({ type: "error", loc: ["", "password"], msg })
                    result.push({ type: "error", loc: ["", "password_confirm"], msg })
                }

                return result
            },
        },
    )

    // Collapse/expand password confirmation based on password presence
    const confirmCollapse = new Collapse(passwordConfirmInput.closest(".collapse"), {
        toggle: false,
    })

    const updateConfirmVisibility = () => {
        if (passwordInput.value.length) confirmCollapse.show()
        else confirmCollapse.hide()
    }

    passwordInput.addEventListener("input", updateConfirmVisibility)
    updateConfirmVisibility()
})
