export const getMapAlert = (name: string) => {
    const alert = document.querySelector(`.map-alert.${name}`) as HTMLElement
    if (!alert) console.error("Map alert", name, "not found")
    return alert
}
