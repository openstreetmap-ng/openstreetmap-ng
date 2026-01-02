import { mount } from "@lib/mount"

mount("oauth-response-form-post-body", (body) => {
  console.info("OAuthResponseFormPost: Submitting form_post")
  const form = body.querySelector("form.response-form-post-form")!
  form.requestSubmit()
})
