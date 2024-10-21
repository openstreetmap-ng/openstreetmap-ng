import { configureStandardForm } from "../_standard-form.js"

const userProfileBody = document.querySelector("body.user-profile-body")
if (userProfileBody) {
    const avatarForm = userProfileBody.querySelector("form.avatar-form")
    const avatarDropdown = avatarForm.querySelector(".dropdown")

    // if editing features available
    if (avatarDropdown) {
        const avatars = document.querySelectorAll("img.avatar")
        const avatarTypeInput = avatarForm.elements.avatar_type
        const avatarFileInput = avatarForm.elements.avatar_file
        const uploadAvatarButton = avatarForm.querySelector("button.upload-btn")
        const useGravatarButton = avatarForm.querySelector("button.gravatar-btn")
        const removeAvatarButton = avatarForm.querySelector("button.remove-btn")

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
        const onAvatarFormSuccess = ({ avatar_url }) => {
            console.debug("onAvatarFormSuccess", avatar_url)
            for (const avatar of avatars) {
                avatar.src = avatar_url
            }
        }

        // Listen for events
        configureStandardForm(avatarForm, onAvatarFormSuccess)
        avatarFileInput.addEventListener("change", onAvatarFileChange)
        uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
        useGravatarButton.addEventListener("click", onUseGravatarClick)
        removeAvatarButton.addEventListener("click", onRemoveAvatarClick)

        const backgroundForm = userProfileBody.querySelector("form.background-form")
        const background = backgroundForm.querySelector("img.background")
        const backgroundFileInput = backgroundForm.elements.background_file
        const uploadBackgroundButton = backgroundForm.querySelector("button.upload-btn")
        const removeBackgroundButton = backgroundForm.querySelector("button.remove-btn")

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
        const onBackgroundFormSuccess = ({ background_url }) => {
            console.debug("onBackgroundFormSuccess", background_url)
            if (background_url) {
                background.src = background_url
            } else {
                background.removeAttribute("src")
            }
        }

        // Listen for events
        configureStandardForm(backgroundForm, onBackgroundFormSuccess)
        backgroundFileInput.addEventListener("change", onBackgroundFileChange)
        uploadBackgroundButton.addEventListener("click", onUploadBackgroundClick)
        removeBackgroundButton.addEventListener("click", onRemoveBackgroundClick)

        const descriptionForm = userProfileBody.querySelector("form.description-form")

        // On form success, reload the page
        const onDescriptionFormSuccess = () => {
            console.debug("onDescriptionFormSuccess")
            window.location.reload()
        }

        configureStandardForm(descriptionForm, onDescriptionFormSuccess)
    }
}
