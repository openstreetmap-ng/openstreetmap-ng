import { qsEncode } from "../_qs.js"
import { routerNavigateStrict } from "./_router.js"

const searchForm = document.querySelector(".search-form")
if (searchForm) {
    const onSubmit = (e) => {
        e.preventDefault()
        const query = searchForm.elements.q.value
        if (query) routerNavigateStrict(`/search?${qsEncode({ q: query })}`)
    }

    searchForm.addEventListener("submit", onSubmit)
}
