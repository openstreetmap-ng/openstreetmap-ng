const actionSidebars = document.querySelectorAll(".action-sidebar")
const searchForms = document.querySelectorAll(".action-sidebar .search-form")
const routingForms = document.querySelectorAll(".action-sidebar .routing-form")

/**
 * Get the action sidebar with the given class name
 * @param {string} className Class name of the sidebar
 * @returns {HTMLDivElement} Action sidebar
 */
export const getActionSidebar = (className) => document.querySelector(`.action-sidebar.${className}`)

/**
 * Switch the action sidebar with the given class name
 * @param {string} className Class name of the sidebar
 * @returns {void}
 */
export const switchActionSidebar = (className) => {
    // Reset all search and routing forms
    for (const searchForm of searchForms) searchForm.reset()
    for (const routingForm of routingForms) routingForm.reset()

    // Toggle all action sidebars
    for (const sidebar of actionSidebars) {
        sidebar.classList.toggle("d-none", !sidebar.classList.contains(className))
    }
}

/**
 * Configure action sidebars
 * @param {object} router Router object
 * @returns {void}
 */
export const configureActionSidebars = (router) => {
    // On sidebar close button click, navigate to index
    const onSidebarCloseClick = () => router.navigate("/")
    for (const sidebarCloseButton of document.querySelectorAll(".sidebar-close-btn")) {
        sidebarCloseButton.addEventListener("click", onSidebarCloseClick)
    }
}
