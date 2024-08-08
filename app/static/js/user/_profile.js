import { configureStandardForm } from "../_standard-form.js"

const userProfileBody = document.querySelector("body.user-profile-body")
if (userProfileBody) {
    const editDropdown = userProfileBody.querySelector("div.edit-dropdown")
    const avatarForm = userProfileBody.querySelector("form.avatar-form")
    const avatarTypeInput = avatarForm.elements.avatar_type
    const avatarFileInput = avatarForm.elements.avatar_file
    const uploadAvatarButton = editDropdown.querySelector("button.upload-avatar")
    const useGravatarButton = editDropdown.querySelector("button.use-gravatar")
    const removeAvatarButton = editDropdown.querySelector("button.remove-avatar")
    const avatars = document.querySelectorAll("img.avatar")

    const onAvatarFileChange = () => {
        avatarTypeInput.value = "custom"
        avatarForm.requestSubmit()
    }

    const onUploadAvatarClick = () => {
        avatarFileInput.click()
    }

    const onUseGravatarClick = () => {
        avatarTypeInput.value = "gravatar"
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    const onRemoveAvatarClick = () => {
        avatarTypeInput.value = "default"
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    // On successful avatar upload, update avatar images
    const onAvatarFormSuccess = (data) => {
        for (const avatar of avatars) avatar.src = data.avatar_url
    }

    configureStandardForm(avatarForm, onAvatarFormSuccess)

    // Listen for events
    avatarFileInput.addEventListener("change", onAvatarFileChange)
    uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
    useGravatarButton.addEventListener("click", onUseGravatarClick)
    removeAvatarButton.addEventListener("click", onRemoveAvatarClick)
}
