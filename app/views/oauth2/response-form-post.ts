import { mount } from "@lib/mount"

mount("oauth-response-form-post-body", (body) => {
    console.info("Submitting oauth response form_post form")
    const form = body.querySelector("form.response-form-post-form")
    form.requestSubmit()
})
