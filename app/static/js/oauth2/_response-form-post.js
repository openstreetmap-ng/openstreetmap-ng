const body = document.querySelector("body.oauth-response-form-post-body")
if (body) {
    const form = body.querySelector("form")
    form.requestSubmit()
}
