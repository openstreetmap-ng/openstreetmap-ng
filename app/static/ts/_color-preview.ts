export const renderColorPreviews = (searchElement: Element): void => {
    const elements = searchElement.querySelectorAll(".color-preview[data-color]") as NodeListOf<HTMLElement>
    for (const element of elements) {
        element.style.background = element.dataset.color
        element.removeAttribute("data-color")
    }
    console.debug("Rendered", elements.length, "color previews")
}
