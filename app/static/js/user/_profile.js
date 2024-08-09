import { configureStandardForm } from "../_standard-form.js"

const userProfileBody = document.querySelector("body.user-profile-body")
if (userProfileBody) {
    const avatarForm = userProfileBody.querySelector("form.avatar-form")
    const avatarDropdown = avatarForm.querySelector(".dropdown")
    const backgroundForm = userProfileBody.querySelector("form.background-form")
    const backgroundDropdown = backgroundForm.querySelector(".dropdown")

    if (avatarDropdown && backgroundDropdown) {
        const avatars = document.querySelectorAll("img.avatar")
        const avatarTypeInput = avatarForm.elements.avatar_type
        const avatarFileInput = avatarForm.elements.avatar_file
        const uploadAvatarButton = avatarForm.querySelector("button.upload-btn")
        const useGravatarButton = avatarForm.querySelector("button.gravatar-btn")
        const removeAvatarButton = avatarForm.querySelector("button.remove-btn")

        const background = backgroundForm.querySelector("img.background")
        const backgroundFileInput = backgroundForm.elements.background_file
        const uploadBackgroundButton = backgroundForm.querySelector("button.upload-btn")
        const removeBackgroundButton = backgroundForm.querySelector("button.remove-btn")

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

        const onAvatarFileChange = () => {
            avatarTypeInput.value = "custom"
            avatarForm.requestSubmit()
        }

        // On successful avatar upload, update avatar images
        const onAvatarFormSuccess = (data) => {
            for (const avatar of avatars) {
                avatar.src = data.avatar_url
            }
        }

        const onUploadBackgroundClick = () => {
            backgroundFileInput.click()
        }

        const onRemoveBackgroundClick = () => {
            backgroundFileInput.value = ""
            backgroundForm.requestSubmit()
        }

        const onBackgroundFileChange = () => {
            backgroundForm.requestSubmit()
        }

        // On successful background upload, update background images
        const onBackgroundFormSuccess = (data) => {
            if (data.background_url) {
                background.src = data.background_url
            } else {
                background.removeAttribute("src")
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
}
