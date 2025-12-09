const roots = document.querySelectorAll<HTMLElement>(".auth-switcher")
console.debug("Initializing", roots.length, "auth switchers")

for (const root of roots) {
    const cta = root.nextElementSibling
    const toProviders = cta?.querySelector(
        "button[data-auth-switcher-target=providers]",
    )
    const toEmail = cta?.querySelector("button[data-auth-switcher-target=email]")
    if (!(toProviders && toEmail)) continue

    const updateCta = () => {
        const providersState = root.dataset.state === "providers"
        toProviders.classList.toggle("d-none", providersState)
        toEmail.classList.toggle("d-none", !providersState)
    }

    const onResize = () => {
        root.scrollLeft = 999999
    }

    toProviders.addEventListener("click", () => {
        root.dataset.state = "providers"
        root.scrollTo({ left: 999999, behavior: "smooth" })
        updateCta()
        window.removeEventListener("resize", onResize)
        window.addEventListener("resize", onResize)
    })

    toEmail.addEventListener("click", () => {
        root.dataset.state = "email"
        root.scrollTo({ left: 0, behavior: "smooth" })
        updateCta()
        window.removeEventListener("resize", onResize)
    })
}
