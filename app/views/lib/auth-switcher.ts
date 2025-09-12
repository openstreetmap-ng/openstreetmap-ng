const roots = document.querySelectorAll<HTMLElement>(".auth-switcher")
console.debug("Initializing", roots.length, "auth switchers")

for (const root of roots) {
    const cta = root.nextElementSibling
    const toProviders = cta.querySelector("button[data-auth-switcher-target=providers]")
    const toEmail = cta.querySelector("button[data-auth-switcher-target=email]")

    const updateCta = (): void => {
        const providersState = root.dataset.state === "providers"
        toProviders.classList.toggle("d-none", providersState)
        toEmail.classList.toggle("d-none", !providersState)
    }

    const onResize = (): void => {
        root.scrollLeft = root.clientWidth + 1
    }

    toProviders.addEventListener("click", (): void => {
        root.dataset.state = "providers"
        root.scrollTo({ left: root.clientWidth + 1, behavior: "smooth" })
        updateCta()
        window.addEventListener("resize", onResize)
    })

    toEmail.addEventListener("click", (): void => {
        root.dataset.state = "email"
        root.scrollTo({ left: 0, behavior: "smooth" })
        updateCta()
        window.removeEventListener("resize", onResize)
    })
}
