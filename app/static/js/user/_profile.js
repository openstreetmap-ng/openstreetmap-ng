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

    const backgroundForm = userProfileBody.querySelector("form.background-form")
    const backgroundFileInput = backgroundForm.elements.background_file
    const uploadBackgroundButton = editDropdown.querySelector("button.upload-background")
    const removeBackgroundButton = editDropdown.querySelector("button.remove-background")
    const backgrounds = document.querySelectorAll("img.background")

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

    const onBackgroundFileChange = () => {
        backgroundForm.requestSubmit()
    }

    const onUploadBackgroundClick = () => {
        backgroundFileInput.click()
    }

    const onRemoveBackgroundClick = () => {
        backgroundFileInput.value = ""
        backgroundForm.requestSubmit()
    }

    // On successful background upload, update background images
    const onBackgroundFormSuccess = (data) => {
        for (const background of backgrounds) {
            if (data.background_url !== null) {
                background.src = data.background_url
            } else {
                background.removeAttribute("src")
            }
        }
    }

    configureStandardForm(avatarForm, onAvatarFormSuccess)
    configureStandardForm(backgroundForm, onBackgroundFormSuccess)

    // Listen for events
    avatarFileInput.addEventListener("change", onAvatarFileChange)
    uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
    useGravatarButton.addEventListener("click", onUseGravatarClick)
    removeAvatarButton.addEventListener("click", onRemoveAvatarClick)
    backgroundFileInput.addEventListener("change", onBackgroundFileChange)
    uploadBackgroundButton.addEventListener("click", onUploadBackgroundClick)
    removeBackgroundButton.addEventListener("click", onRemoveBackgroundClick)
}
