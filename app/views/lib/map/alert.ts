/** Get the map alert element */
export const getMapAlert = (name: string): HTMLElement => {
    const alert = document.querySelector(`.map-alert.${name}`) as HTMLElement
    if (!alert) console.error("Map alert", name, "not found")
    return alert
}
