import { mount } from "../lib/mount"
import { configureStandardForm } from "../lib/standard-form"

mount("follows-body", (body) => {
    // Handle follow/unfollow/follow-back forms
    const forms = body.querySelectorAll("form.unfollow-form, form.follow-back-form")
    for (const form of forms) {
        configureStandardForm(form, () => {
            // On success, reload the page to update the lists
            console.debug("onFollowActionSuccess")
            window.location.reload()
        })
    }
})
