const tracesIndexBody = document.querySelector("body.traces-index-body")
if (tracesIndexBody) {
    const tracesList = tracesIndexBody.querySelector(".traces-list")
    const coordsAll = JSON.parse(tracesList.dataset.coords)
    const svgs = tracesList.querySelectorAll("svg")

    console.debug("Rendering", svgs.length, "trace SVGs")
    for (let i = 0; i < svgs.length; i++) {
        const coords = coordsAll[i]
        const svg = svgs[i]

        const ds = []
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
}
