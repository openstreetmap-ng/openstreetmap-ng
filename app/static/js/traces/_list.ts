import { renderAnimatedTrace, renderTrace } from "../_trace-svg"

for (const tracesList of document.querySelectorAll(".traces-list") as NodeListOf<HTMLElement>) {
    const coordsStr = tracesList.dataset.coords
    if (!coordsStr) continue

    const coordsAll: [number, number][][] = JSON.parse(coordsStr)
    const svgs: NodeListOf<SVGElement> = tracesList.querySelectorAll("svg")
    const resultActions = tracesList.querySelectorAll(".social-action")

    console.debug("Rendering", svgs.length, "trace SVGs")
    for (let i = 0; i < svgs.length; i++) {
        const coords = coordsAll[i]
        const svg = svgs[i]
        const resultAction = resultActions[i]
        renderTrace(svg, coords)

        let svgAnimated: SVGElement | null = null

        resultAction.addEventListener("mouseover", () => {
            // On action mouseover, show animated trace
            if (!svgAnimated) {
                svgAnimated = svg.cloneNode(true) as SVGElement
                svgAnimated.innerHTML = ""
                renderAnimatedTrace(svgAnimated, coords)
            }
            svg.parentElement.replaceChild(svgAnimated, svg)
        })
        resultAction.addEventListener("mouseout", () => {
            // On action mouseout, show static trace
            if (!svgAnimated) return
            svgAnimated.parentElement.replaceChild(svg, svgAnimated)
        })
    }
}
