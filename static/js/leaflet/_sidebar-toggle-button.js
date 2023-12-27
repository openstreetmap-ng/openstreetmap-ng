import * as L from "leaflet"

export const sidebarToggleButton = (options, className, buttonTitle) => {
    const control = L.control(options)

    control.onAdd = () => {
        // Find corresponding sidebar
        const sidebar = document.querySelector(`.sidebar.leaflet-sidebar.${className}`)
        if (!sidebar) console.error(`Sidebar ${className} not found`)

        // Create container
        const container = document.createElement("div")

        // Create button
        const input = document.createElement("input")
        input.type = "radio"
        input.name = "sidebar-toggle"
        input.id = `sidebar-toggle-${className}`
        input.className = "btn-check"

        const label = document.createElement("label")
        label.className = "control-button"
        label.title = I18n.t(buttonTitle)
        label.innerHTML = `<span class='icon ${className}'></span>`
        label.htmlFor = input.id

        // Add button to container
        container.appendChild(input)
        container.appendChild(label)

        // Listen for events
        const onChange = () => {
            if (input.checked) {
                sidebar.classList.remove("d-none")
            } else {
                sidebar.classList.add("d-none")
            }
        }

        input.addEventListener("change", onChange)

        return container
    }

    return control
}
