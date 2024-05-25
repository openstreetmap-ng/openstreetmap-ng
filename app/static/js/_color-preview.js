/**
 * Discover and render tag color previews.
 * @return {void}
 */
export const renderColorPreviews = () => {
    const elements = document.querySelectorAll(".color-preview[data-color]")
    for (const element of elements) {
        const color = element.dataset.color
        element.style.background = color
        element.removeAttribute("data-color")
    }
}
