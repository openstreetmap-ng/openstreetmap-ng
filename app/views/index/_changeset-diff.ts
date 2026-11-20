import { convertRenderElementsData, renderObjects } from "@map/render-objects"
import type { DataValid as ChangesetData } from "@proto/changeset_pb"
import type { DataValid as ElementData } from "@proto/element_pb"
import { ElementType } from "@proto/shared_pb"
import type { FeatureCollection } from "geojson"

export const MAX_DIFF_ELEMENTS = 200
export type DiffVersion = { type: ElementType; id: bigint; version: bigint }
type VersionLoader = (ref: DiffVersion, signal: AbortSignal) => Promise<ElementData>
export class DiffTooLargeError extends Error {
  override name = "DiffTooLargeError"
}

export const loadChangesetDiff = async (
  data: ChangesetData,
  load: VersionLoader,
  signal: AbortSignal,
): Promise<FeatureCollection> => {
  signal.throwIfAborted()
  const controller = new AbortController()
  const requestSignal = AbortSignal.any([signal, controller.signal])
  const groups = new Map<string, { first: DiffVersion; last: DiffVersion; visible: boolean }>()
  for (const [elements, type] of [
    [data.nodes, ElementType.node],
    [data.ways, ElementType.way],
  ] as const) {
    for (const element of elements) {
      const key = `${type}/${element.id}`
      const ref = { type, id: element.id, version: element.version }
      const group = groups.get(key)
      if (!group) groups.set(key, { first: ref, last: ref, visible: element.visible })
      else {
        if (ref.version < group.first.version) group.first = ref
        if (ref.version >= group.last.version) {
          group.last = ref
          group.visible = element.visible
        }
      }
    }
  }
  if (groups.size > MAX_DIFF_ELEMENTS) throw new DiffTooLargeError()
  const jobs: { ref: DiffVersion; phase: "before" | "after" }[] = []
  for (const group of groups.values()) {
    if (group.first.version > 1n)
      jobs.push({ ref: { ...group.first, version: group.first.version - 1n }, phase: "before" })
    if (group.visible) jobs.push({ ref: group.last, phase: "after" })
  }
  const results: FeatureCollection["features"][] = new Array(jobs.length)
  let index = 0
  const worker = async () => {
    while (index < jobs.length) {
      requestSignal.throwIfAborted()
      const i = index++
      const { ref, phase } = jobs[i]!
      const response = await load(ref, requestSignal)
      requestSignal.throwIfAborted()
      if (
        response.ref.type !== ref.type ||
        response.ref.id !== ref.id ||
        response.ref.version !== ref.version
      )
        throw new Error("Mismatched version response")
      const objects = convertRenderElementsData(response.context.render).filter(
        (object) => object.type === ElementType[ref.type] && object.id === ref.id,
      )
      if (!response.visible || !objects.length) throw new Error("Missing version geometry")
      results[i] = renderObjects(objects, { renderAreas: false }).features.map((feature, n) => ({
        ...feature,
        id: `${ref.type}/${ref.id}/${phase}/${n}`,
        properties: { ...feature.properties, phase, version: ref.version.toString() },
      }))
    }
  }
  try {
    await Promise.all(Array.from({ length: Math.min(4, jobs.length) }, worker))
  } catch (error) {
    controller.abort()
    throw error
  }
  return { type: "FeatureCollection", features: results.flat() }
}
