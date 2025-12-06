import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"

mount("reset-password-token-body", (body) => {
    const resetForm = body.querySelector("form.reset-form")!
    configureStandardForm(resetForm, () => {
        // On successful reset request, update the form state
        resetForm.reset()
        resetForm.querySelector(".before")!.remove()
        resetForm.querySelector(".after")!.classList.remove("d-none")
    })
})
