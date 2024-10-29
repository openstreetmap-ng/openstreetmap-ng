import { decode } from "@mapbox/polyline"
import { renderAnimatedTrace, renderTrace } from "../_trace-svg"

for (const tracesList of document.querySelectorAll("ul.traces-list")) {
    const tracesLinesLens: number[] = JSON.parse(tracesList.dataset.linesLens)
    const tracesCoords = decode(tracesList.dataset.line, 0)
    for (const pair of tracesCoords) pair[0] += 60
    const svgs: NodeListOf<SVGElement> = tracesList.querySelectorAll("svg")
    const resultActions = tracesList.querySelectorAll(".social-action")

    console.debug("Rendering", svgs.length, "trace SVGs")
    let tracesLinesLensSum = 0
    for (let i = 0; i < svgs.length; i++) {
        const svg = svgs[i]
        const coords = tracesCoords.slice(tracesLinesLensSum, tracesLinesLensSum + tracesLinesLens[i])
        tracesLinesLensSum += tracesLinesLens[i]
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
