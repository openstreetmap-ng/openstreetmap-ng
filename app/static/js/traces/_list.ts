import { decode } from "@mapbox/polyline"
import { renderAnimatedTrace, renderTrace } from "../_trace-svg"

for (const tracesList of document.querySelectorAll("ul.traces-list")) {
    const tracesLines = tracesList.dataset.lines.split(";")
    const svgs: NodeListOf<SVGElement> = tracesList.querySelectorAll("svg")
    const resultActions = tracesList.querySelectorAll(".social-action")

    console.debug("Rendering", svgs.length, "trace SVGs")
    for (let i = 0; i < svgs.length; i++) {
        const svg = svgs[i]
        const coords = decode(tracesLines[i], 0)
        renderTrace(svg, coords)

        let svgAnimated: SVGElement | null = null

        // On action mouseover, show animated trace
        const resultAction = resultActions[i]
        resultAction.addEventListener("mouseover", () => {
            if (!svgAnimated) {
                svgAnimated = svg.cloneNode(true) as SVGElement
                svgAnimated.innerHTML = ""
                console.debug("Rendering animated trace SVG at", i)
                renderAnimatedTrace(svgAnimated, coords)
            }
            svg.parentElement.replaceChild(svgAnimated, svg)
        })

        // On action mouseout, show static trace
        resultAction.addEventListener("mouseout", () => {
            if (!svgAnimated) return
            svgAnimated.parentElement.replaceChild(svg, svgAnimated)
        })
    }
}
