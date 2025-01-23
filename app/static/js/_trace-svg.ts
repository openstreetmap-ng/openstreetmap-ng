/** Render a static trace to the given SVG element */
export const renderTrace = (svg: SVGElement, latLons: [number, number][]): void => {
    if (!latLons.length) return
    const ds: string[] = [`M${latLons[0][1]},${latLons[0][0]}`]
    for (const pair of latLons.slice(1)) ds.push(`L${pair[1]},${pair[0]}`)

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
    path.setAttribute("d", ds.join(" "))
    path.setAttribute("fill", "none")
    path.setAttribute("stroke", "var(--bs-body-color)")
    path.setAttribute("stroke-width", "1.8")
    path.setAttribute("stroke-linecap", "round")
    svg.appendChild(path)
}

/** Render an animated trace to the given SVG element */
export const renderAnimatedTrace = (svg: SVGElement, latLons: [number, number][]) => {
    if (!latLons.length) return
    const ds: string[] = [`M${latLons[0][1]},${latLons[0][0]}`]
    for (const pair of latLons.slice(1)) ds.push(`L${pair[1]},${pair[0]}`)

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
    path.setAttribute("d", ds.join(" "))
    path.setAttribute("fill", "none")
    path.setAttribute("stroke", "#aaa")
    path.setAttribute("stroke-width", "0.45")
    path.setAttribute("stroke-linecap", "round")

    svg.appendChild(path)

    {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
        path.setAttribute("d", ds.join(" "))
        path.setAttribute("fill", "none")
        path.setAttribute("stroke", "var(--bs-body-color)")
        path.setAttribute("stroke-width", "2.2")
        path.setAttribute("stroke-linecap", "round")

        const totalLength = path.getTotalLength()
        const segmentLength = 50
        const duration = totalLength / 120

        path.setAttribute("stroke-dasharray", `${segmentLength} ${totalLength}`)

        const animate = document.createElementNS("http://www.w3.org/2000/svg", "animate")
        animate.setAttribute("attributeName", "stroke-dashoffset")
        animate.setAttribute("values", `0;${-totalLength - segmentLength}`)
        animate.setAttribute("dur", `${duration}s`)
        animate.setAttribute("repeatCount", "indefinite")
        animate.setAttribute("fill", "freeze")

        path.appendChild(animate)
        svg.appendChild(path)
    }
}
