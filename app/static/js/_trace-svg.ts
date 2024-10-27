/**
 * Render a static trace to the given SVG element.
 */
export const renderTrace = (svg: SVGElement, coords: [number, number][]): void => {
    const ds: string[] = []
    for (let j = 0; j < coords.length; j += 2) {
        const x = coords[j]
        const y = coords[j + 1]
        const prefix = j === 0 ? "M" : "L"
        ds.push(`${prefix}${x},${y}`)
    }

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
    path.setAttribute("d", ds.join(" "))
    path.setAttribute("fill", "none")
    path.setAttribute("stroke", "black")
    path.setAttribute("stroke-width", "2")
    path.setAttribute("stroke-linecap", "round")
    svg.appendChild(path)
}

/**
 * Render an animated trace to the given SVG element.
 */
export const renderAnimatedTrace = (svg: SVGElement, coords: [number, number][]) => {
    console.debug("Rendering animated trace SVG")
    const ds: string[] = []
    for (let i = 0; i < coords.length; i += 2) {
        const x = coords[i]
        const y = coords[i + 1]
        const prefix = i === 0 ? "M" : "L"
        ds.push(`${prefix}${x},${y}`)
    }

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
    path.setAttribute("d", ds.join(" "))
    path.setAttribute("fill", "none")
    path.setAttribute("stroke", "#aaa")
    path.setAttribute("stroke-width", "0.5")
    path.setAttribute("stroke-linecap", "round")

    svg.appendChild(path)

    {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
        path.setAttribute("d", ds.join(" "))
        path.setAttribute("fill", "none")
        path.setAttribute("stroke", "black")
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
