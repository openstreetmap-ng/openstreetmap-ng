import type { Polyline } from "@lib/polyline"

export const renderTrace = (svg: SVGElement, line: Polyline) => {
  if (!line.length) return
  const pathData = generatePathData(line)
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path")
  path.setAttribute("d", pathData)
  path.setAttribute("fill", "none")
  path.setAttribute("stroke", "var(--bs-body-color)")
  path.setAttribute("stroke-width", "1.8")
  path.setAttribute("stroke-linecap", "round")
  svg.appendChild(path)
}

export const renderAnimatedTrace = (svg: SVGElement, line: Polyline) => {
  if (!line.length) return
  const pathData = generatePathData(line)
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

const generatePathData = (line: Polyline) => {
  let d = `M${line[0][0]},${line[0][1]}`
  for (let i = 1; i < line.length; i++) d += ` L${line[i][0]},${line[i][1]}`
  return d
}
