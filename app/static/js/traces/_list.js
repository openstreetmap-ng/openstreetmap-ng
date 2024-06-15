import { renderAnimatedTrace, renderTrace } from "../_svg.js"

for (const tracesList of document.querySelectorAll(".traces-list")) {
    const coordsStr = tracesList.dataset.coords
    if (!coordsStr) continue

    const coordsAll = JSON.parse(coordsStr)
    const svgs = tracesList.querySelectorAll("svg")
    const resultActions = tracesList.querySelectorAll(".social-action")

    console.debug("Rendering", svgs.length, "trace SVGs")
    for (let i = 0; i < svgs.length; i++) {
        const coords = coordsAll[i]
        const svg = svgs[i]
        const resultAction = resultActions[i]
        renderTrace(svg, coords)

        let svgAnimated = null

        const onResultMouseover = () => {
            if (!svgAnimated) {
                svgAnimated = svg.cloneNode(true)
                svgAnimated.innerHTML = ""
                renderAnimatedTrace(svgAnimated, coords)
            }
            svg.parentElement.replaceChild(svgAnimated, svg)
        }

        const onResultMouseout = () => {
            if (!svgAnimated) return
            svgAnimated.parentElement.replaceChild(svg, svgAnimated)
        }

        // Listen for events
        resultAction.addEventListener("mouseover", onResultMouseover)
        resultAction.addEventListener("mouseout", onResultMouseout)
    }
}
