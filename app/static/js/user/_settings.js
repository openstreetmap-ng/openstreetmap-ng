import { configureStandardForm } from "../_standard-form.js"

const settingsBody = document.querySelector("body.settings-body")
if (settingsBody) {
    const settingsForm = settingsBody.querySelector("form.settings-form")
    const avatarForm = settingsBody.querySelector("form.avatar-form")

    const avatars = document.querySelectorAll("img.avatar")
    const avatarTypeInput = avatarForm.querySelector("input[name=avatar_type]")
    const avatarFileInput = avatarForm.querySelector("input[name=avatar_file]")
    const uploadAvatarButton = avatarForm.querySelector("button.upload-avatar")
    const useGravatarButton = avatarForm.querySelector("button.use-gravatar")
    const removeAvatarButton = avatarForm.querySelector("button.remove-avatar")

    const onAvatarFileChange = () => {
        console.debug("onAvatarFileChange")
        avatarTypeInput.value = "custom"
        avatarForm.requestSubmit()
    }

    const onUploadAvatarClick = () => {
        console.debug("onUploadAvatarClick")
        avatarFileInput.click()
    }

    const onUseGravatarClick = () => {
        console.debug("onUseGravatarClick")
        avatarTypeInput.value = "gravatar"
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    const onRemoveAvatarClick = () => {
        console.debug("onRemoveAvatarClick")
        avatarTypeInput.value = "default"
        avatarFileInput.value = ""
        avatarForm.requestSubmit()
    }

    const onAvatarFormSuccess = (data) => {
        console.debug("onAvatarFormSuccess", data)
        for (const avatar of avatars) avatar.src = data.avatar_url
    }

    configureStandardForm(settingsForm)
    configureStandardForm(avatarForm, onAvatarFormSuccess)

    // Listen for events
    avatarFileInput.addEventListener("change", onAvatarFileChange)
    uploadAvatarButton.addEventListener("click", onUploadAvatarClick)
    useGravatarButton.addEventListener("click", onUseGravatarClick)
    removeAvatarButton.addEventListener("click", onRemoveAvatarClick)
}
