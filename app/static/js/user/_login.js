import { qsParse } from "../_qs.js"
import { configureStandardForm } from "../_standard-form.js"

const loginBody = document.querySelector("body.login-body")
if (loginBody) {
    const loginForm = loginBody.querySelector("form.login-form")

    const onLoginSuccess = () => {
        // Redirect to refer from query string and hash
        // Referrer must start with '/' to avoid open redirect
        const params = qsParse(location.search.substring(1))
        let referer = (params.referer ?? "/") + location.hash
        if (!referer.startsWith("/")) referer = "/"
        location.href = referer
    }

    configureStandardForm(loginForm, onLoginSuccess)
}
