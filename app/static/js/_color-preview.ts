export const renderColorPreviews = (): void => {
    const elements = document.querySelectorAll(".color-preview[data-color]") as NodeListOf<HTMLElement>
    for (const element of elements) {
        element.style.background = element.dataset.color
        element.removeAttribute("data-color")
    }
}
