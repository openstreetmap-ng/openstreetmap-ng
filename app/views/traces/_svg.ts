/** Render a static trace to the given SVG element */
export const renderTrace = (svg: SVGElement, coords: [number, number][]) => {
    if (!coords.length) return
    const pathData = generatePathData(coords)
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
    path.setAttribute("d", pathData)
    path.setAttribute("fill", "none")
    path.setAttribute("stroke", "var(--bs-body-color)")
    path.setAttribute("stroke-width", "1.8")
    path.setAttribute("stroke-linecap", "round")
    svg.appendChild(path)
}

/** Render an animated trace to the given SVG element */
export const renderAnimatedTrace = (svg: SVGElement, coords: [number, number][]) => {
    if (!coords.length) return
    const pathData = generatePathData(coords)
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
    path.setAttribute("d", pathData)
    path.setAttribute("fill", "none")
    path.setAttribute("stroke", "#aaa")
    path.setAttribute("stroke-width", "0.45")
    path.setAttribute("stroke-linecap", "round")

    svg.appendChild(path)

    {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
        path.setAttribute("d", pathData)
        path.setAttribute("fill", "none")
        path.setAttribute("stroke", "var(--bs-body-color)")
        path.setAttribute("stroke-width", "2.2")
        path.setAttribute("stroke-linecap", "round")

        const totalLength = path.getTotalLength()
        const duration = totalLength / 120
        const segmentLength = 50

        path.setAttribute("stroke-dasharray", `${segmentLength} ${totalLength}`)

        const animate = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "animate",
        )
        animate.setAttribute("attributeName", "stroke-dashoffset")
        animate.setAttribute("values", `0;${-totalLength - segmentLength}`)
        animate.setAttribute("dur", `${duration}s`)
        animate.setAttribute("repeatCount", "indefinite")
        animate.setAttribute("fill", "freeze")

        path.appendChild(animate)
        svg.appendChild(path)
    }
}

/** Generate a path data string from coordinates in [x, y] pairs */
const generatePathData = (coords: [number, number][]) => {
    let d = `M${coords[0][0]},${coords[0][1]}`
    for (let i = 1; i < coords.length; i++) d += ` L${coords[i][0]},${coords[i][1]}`
    return d
}
