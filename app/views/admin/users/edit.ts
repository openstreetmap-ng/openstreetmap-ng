import { Collapse } from "bootstrap"
import i18next from "i18next"
import { mount } from "../../lib/mount"
import { type APIDetail, configureStandardForm } from "../../lib/standard-form"

mount("admin-user-edit-body", (body) => {
    // Accordion toggling for application/token previews (read-only)
    const accordionButtons = body.querySelectorAll("button.accordion-button")
    for (const button of accordionButtons) {
        const collapse = document.querySelector(button.dataset.bsTarget)
        const collapseInstance = Collapse.getOrCreateInstance(collapse, {
            toggle: false,
        })
        // @ts-expect-error
        collapseInstance._triggerArray.push(button)

        // On accordion button click, toggle the collapse if target is not a link
        button.addEventListener("click", ({ target }: Event) => {
            const tagName = (target as HTMLElement).tagName
            if (tagName === "A") return
            collapseInstance.toggle()
        })
    }

    const accountForm = body.querySelector("form.account-form")
    const newPasswordInput = accountForm.querySelector(
        "input[type=password][data-name=new_password]",
    )
    const newPasswordConfirmInput = accountForm.querySelector(
        "input[type=password][data-name=new_password_confirm]",
    )
    const roleCheckboxes = accountForm.querySelectorAll("input.role-checkbox")

    const originalRoles = new Set<string>()
    for (const checkbox of roleCheckboxes) {
        if (checkbox.checked) {
            originalRoles.add(checkbox.value)
        }
    }
    configureStandardForm(
        accountForm,
        () => {
            console.debug("onAccountFormSuccess")
            originalRoles.clear()
            for (const checkbox of roleCheckboxes) {
                if (checkbox.checked) {
                    originalRoles.add(checkbox.value)
                }
            }
            newPasswordInput.value = ""
            newPasswordConfirmInput.value = ""
        },
        {
            validationCallback: () => {
                const result: APIDetail[] = []

                const currentRoles = new Set<string>()
                for (const checkbox of roleCheckboxes) {
                    if (checkbox.checked) {
                        currentRoles.add(checkbox.value)
                    }
                }

                const addedRoles: string[] = []
                const removedRoles: string[] = []

                for (const role of currentRoles) {
                    if (!originalRoles.has(role)) {
                        addedRoles.push(role)
                    }
                }

                for (const role of originalRoles) {
                    if (!currentRoles.has(role)) {
                        removedRoles.push(role)
                    }
                }

                for (const role of removedRoles) {
                    const message = `Remove ${role} role from this user?`
                    if (!confirm(message)) return ""
                }

                for (const role of addedRoles) {
                    const message = `Grant ${role} role to this user?`
                    if (!confirm(message)) return ""
                }

                if (newPasswordInput.value || newPasswordConfirmInput.value) {
                    if (newPasswordInput.value !== newPasswordConfirmInput.value) {
                        const msg = i18next.t("validation.passwords_missmatch")
                        result.push({ type: "error", loc: ["", "new_password"], msg })
                        result.push({
                            type: "error",
                            loc: ["", "new_password_confirm"],
                            msg,
                        })
                    }
                }

                return result
            },
            formAppend: true,
            removeEmptyFields: true,
        },
    )

    const impersonateForm = body.querySelector("form.impersonate-form")
    impersonateForm.addEventListener("submit", (e) => {
        if (
            !confirm(
                "Login as this user? You will need to re-authenticate to regain admin access.",
            )
        ) {
            e.preventDefault()
        }
    })

    const reset2FAForm = body.querySelector("form.reset-2fa-form")
    configureStandardForm(
        reset2FAForm,
        () => {
            console.debug("onReset2FAFormSuccess")
            window.location.reload()
        },
        {
            validationCallback: () =>
                confirm(
                    "Reset two-factor authentication for this user?\n\n" +
                        "This will remove:\n" +
                        "• All passkeys\n" +
                        "• Authenticator app",
                )
                    ? null
                    : "Operation cancelled by user",
        },
    )
})
