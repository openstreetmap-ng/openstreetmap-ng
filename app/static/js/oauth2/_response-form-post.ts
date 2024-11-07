const body = document.querySelector("body.oauth-response-form-post-body")
if (body) {
    console.info("Submitting oauth response form_post form")
    const form = body.querySelector("form.response-form-post-form")
    form.requestSubmit()
}
