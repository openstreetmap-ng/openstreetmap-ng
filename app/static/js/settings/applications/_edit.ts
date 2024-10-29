import { t } from "i18next"
import { configureStandardForm } from "../../_standard-form"
import { initializeResetSecretControls } from "./_reset-secret-control"

const body = document.querySelector("body.settings-application-edit-body")
if (body) {
    const avatarForm = body.querySelector("form.avatar-form")
    const avatar = avatarForm.querySelector("img.avatar")
    const avatarFileInput = avatarForm.elements.namedItem("avatar_file") as HTMLInputElement

    avatarFileInput.addEventListener("change", () => {
        avatarForm.requestSubmit()
    })

    const uploadAvatarButton = avatarForm.querySelector("button.upload-btn")
    uploadAvatarButton.addEventListener("click", () => {
        avatarFileInput.click()
    })

    const removeAvatarButton = avatarForm.querySelector("button.remove-btn")
    removeAvatarButton.addEventListener("click", () => {
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    })

    configureStandardForm(avatarForm, ({ avatar_url }) => {
        // On successful avatar upload, update avatar image
        console.debug("onAvatarFormSuccess", avatar_url)
        avatar.src = avatar_url
    })

    const editForm = body.querySelector("form.edit-form")
    const clientSecretControl = editForm.querySelector(".client-secret-control")
    const isConfidentialRadios = editForm.elements.namedItem("is_confidential") as RadioNodeList
    const revokeAllAuthorizationsCheckbox = editForm.elements.namedItem("revoke_all_authorizations") as HTMLInputElement

    const onIsConfidentialChange = ({ target }: Event) => {
        const radio = target as HTMLInputElement
        console.debug("onIsConfidentialChange", radio.value)
        clientSecretControl.classList.toggle("d-none", radio.value === "false")
    }
    for (const radio of isConfidentialRadios) radio.addEventListener("change", onIsConfidentialChange)

    configureStandardForm(
        editForm,
        () => {
            // On success callback, uncheck revoke all authorizations
            console.debug("onEditFormSuccess")
            revokeAllAuthorizationsCheckbox.checked = false
            revokeAllAuthorizationsCheckbox.dispatchEvent(new Event("change"))
        },
        null,
        { formAppend: true },
    )

    const deleteForm = body.querySelector("form.delete-form")
    configureStandardForm(deleteForm, ({ redirect_url }) => {
        // On success callback, navigate to my applications
        console.debug("onDeleteFormSuccess", redirect_url)
        window.location.href = redirect_url
    })

    // On delete button click, request confirmation
    const deleteButton = deleteForm.querySelector("button[type=submit]")
    deleteButton.addEventListener("click", (event: Event) => {
        if (!confirm(t("settings.delete_this_application_question"))) {
            event.preventDefault()
        }
    })

    // Finally, initialize reset secret controls
    initializeResetSecretControls()
}
