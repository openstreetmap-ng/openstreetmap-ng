import { polylineDecode } from "@lib/polyline"
import { renderAnimatedTrace, renderTrace } from "./_svg"

const configureTracesListElement = (tracesList: HTMLUListElement) => {
  const linesElement = tracesList.querySelector("li.traces-lines")
  if (!linesElement) return
  const tracesLines = linesElement.dataset.lines!.split(";")
  linesElement.remove()

  const svgs = tracesList.querySelectorAll("svg")
  if (!svgs.length) return

  const resultActions = tracesList.querySelectorAll(".social-entry.clickable")

  console.debug("TraceList: Rendering trace SVGs", svgs.length)
  for (let i = 0; i < svgs.length; i++) {
    const svg = svgs[i]
    const coords = polylineDecode(tracesLines[i], 0)
    renderTrace(svg, coords)

    let svgAnimated: SVGElement | undefined

    // On action enter, show animated trace
    const resultAction = resultActions[i]
    resultAction.addEventListener("mouseenter", () => {
      if (!svgAnimated) {
        svgAnimated = svg.cloneNode() as SVGElement
        renderAnimatedTrace(svgAnimated, coords)
      }
      svg.replaceWith(svgAnimated)
    })

    // On action leave, show static trace
    resultAction.addEventListener("mouseleave", () => {
      svgAnimated!.replaceWith(svg)
    })
  }
}

export const configureTracesList = (root: ParentNode = document) => {
  if (root instanceof HTMLUListElement && root.classList.contains("traces-list")) {
    configureTracesListElement(root)
    return
  }
  for (const tracesList of root.querySelectorAll("ul.traces-list")) {
    configureTracesListElement(tracesList)
  }
}
