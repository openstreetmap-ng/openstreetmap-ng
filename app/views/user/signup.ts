import { activityTracking, URLSAFE_BLACKLIST } from "@lib/config"
import { mount } from "@lib/mount"
import { type APIDetail, configureStandardForm } from "@lib/standard-form"
import { Collapse } from "bootstrap"
import i18next from "i18next"

mount("signup-body", (body) => {
    const signupForm = body.querySelector("form.signup-form")!
    const displayNameInput = signupForm.querySelector("input[name=display_name]")!
    const passwordInput = signupForm.querySelector(
        "input[type=password][data-name=password]",
    )!
    const passwordConfirmInput = signupForm.querySelector(
        "input[type=password][data-name=password_confirm]",
    )!

    const trackingInput = signupForm.querySelector("input[name=tracking]")!
    trackingInput.value = activityTracking.toString()

    configureStandardForm(
        signupForm,
        ({ redirect_url }) => {
            console.debug("onSignupFormSuccess", redirect_url)
            window.location.href = redirect_url
        },
        {
            validationCallback: () => {
                const result: APIDetail[] = []

                // Validate name for blacklisted characters
                const displayNameChars = new Set(displayNameInput.value)
                if (URLSAFE_BLACKLIST.split("").some((c) => displayNameChars.has(c))) {
                    const msg = i18next.t("validations.url_characters", {
                        characters: URLSAFE_BLACKLIST,
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
    const confirmCollapse = new Collapse(passwordConfirmInput.closest(".collapse")!, {
        toggle: false,
    })

    const updateConfirmVisibility = () => {
        if (passwordInput.value.length) confirmCollapse.show()
        else confirmCollapse.hide()
    }

    passwordInput.addEventListener("input", updateConfirmVisibility)
    updateConfirmVisibility()
})
