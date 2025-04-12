import { configureStandardForm } from "../lib/standard-form"
import { configureStandardPagination } from "../lib/standard-pagination"

const body = document.querySelector("body.diary-details-body")
if (body) {
    configureStandardPagination(document.getElementById("comments"))

    configureStandardForm(body.querySelector("form.subscription-form"), () => {
        // On success callback, reload the page
        console.debug("onSubscriptionFormSuccess")
        window.location.reload()
    })

    configureStandardForm(body.querySelector("form.comment-form"), () => {
        // On success callback, reload the page
        console.debug("onCommentFormSuccess")
        window.location.reload()
    })
}
