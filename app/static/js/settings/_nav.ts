import { isHrefCurrentPage } from "../_utils"

// Add active class to current nav-lik
const navLinks: NodeListOf<HTMLAnchorElement> = document.querySelectorAll(".settings-nav .nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}
