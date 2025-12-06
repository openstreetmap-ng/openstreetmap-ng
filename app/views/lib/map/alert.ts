export const getMapAlert = (name: string) =>
    document.querySelector<HTMLElement>(`.map-alert.${name}`)!
