import { configureStandardForm } from "../_standard-form"
import { configureStandardPagination } from "../_standard-pagination"

const body = document.querySelector("body.diary-details-body")
if (body) {
    const comments = document.getElementById("comments")
    configureStandardPagination(comments)

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
