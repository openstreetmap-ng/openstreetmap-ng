export const renderColorPreviews = (): void => {
    const elements: NodeListOf<HTMLElement> = document.querySelectorAll(".color-preview[data-color]")
    for (const element of elements) {
        element.style.background = element.dataset.color
        element.removeAttribute("data-color")
    }
}
