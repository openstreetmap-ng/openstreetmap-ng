import { t } from "i18next"
import { initializeCopyGroups } from "../../_copy-group.js"
import { configureStandardForm } from "../../_standard-form.js"

const body = document.querySelector("body.settings-application-edit-body")
if (body) {
    const avatarForm = body.querySelector("form.avatar-form")
    const avatar = avatarForm.querySelector("img.avatar")
    const avatarFileInput = avatarForm.elements.avatar_file
    const uploadAvatarButton = avatarForm.querySelector("button.upload-btn")
    const removeAvatarButton = avatarForm.querySelector("button.remove-btn")
    const editForm = body.querySelector("form.edit-form")
    const revokeAllAuthorizationsCheckbox = editForm.elements.revoke_all_authorizations
    const resetClientSecretButton = body.querySelector("button.reset-client-secret")
    const resetClientSecretForm = body.querySelector("form.reset-client-secret-form")
    const deleteForm = body.querySelector("form.delete-form")
    const deleteButton = deleteForm.querySelector("button[type=submit]")
    const copyGroups = body.querySelectorAll(".copy-group")

    const onUploadAvatarClick = () => {
        avatarFileInput.click()
    }

    const onRemoveAvatarClick = () => {
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    const onAvatarFileChange = () => {
        avatarForm.requestSubmit()
    }

    // On successful avatar upload, update avatar image
    const onAvatarFormSuccess = ({ avatar_url }) => {
        console.debug("onAvatarFormSuccess", avatar_url)
        avatar.src = avatar_url
    }

    const onEditFormSuccess = () => {
        console.debug("onEditFormSuccess")
        revokeAllAuthorizationsCheckbox.checked = false
        revokeAllAuthorizationsCheckbox.dispatchEvent(new Event("change"))
    }

    const onResetClientSecretClick = () => {
        if (confirm(t("settings.new_client_secret_question"))) {
            resetClientSecretForm.requestSubmit()
        }
    }

    const onResetClientSecretFormSuccess = ({ client_secret }) => {
        console.debug("onResetClientSecretFormSuccess")
        const input = resetClientSecretButton.parentElement.querySelector("input")
        input.value = client_secret
        input.dispatchEvent(new Event("change"))
    }

    // On button click, request confirmation
    const onDeleteClick = (event) => {
        if (!confirm(t("settings.delete_this_application_question"))) {
            event.preventDefault()
        }
    }

    // On success callback, navigate to my traces
    const onDeleteFormSuccess = ({ redirect_url }) => {
        console.debug("onFormSuccess", redirect_url)
        window.location = redirect_url
    }

    // Listen for events
    configureStandardForm(avatarForm, onAvatarFormSuccess)
    avatarFileInput.addEventListener("change", onAvatarFileChange)
    uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
    removeAvatarButton.addEventListener("click", onRemoveAvatarClick)
    configureStandardForm(editForm, onEditFormSuccess, null, { formAppend: true })
    resetClientSecretButton.addEventListener("click", onResetClientSecretClick)
    configureStandardForm(resetClientSecretForm, onResetClientSecretFormSuccess)
    deleteButton.addEventListener("click", onDeleteClick)
    configureStandardForm(deleteForm, onDeleteFormSuccess)
    initializeCopyGroups(copyGroups)
}
