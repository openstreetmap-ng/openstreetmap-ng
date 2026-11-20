import { create, fromBinary, toBinary } from "@bufbuild/protobuf"
import { signal } from "@preact/signals"
import { Service } from "@proto/element_pb"
import { render } from "preact"
import i18next from "i18next"
import maplibregl from "maplibre-gl"
import { ChangesetDiffControl } from "../../../app/views/index/_changeset-diff-control"
import translations from "@diff-translations"
import { polylineEncode } from "@utils/polyline"

i18next.init({ lng: "en", resources: { en: { translation: translations } }, initImmediate: false })
window.calls = []
window.fail = false
window.delay = 0
window.aborted = 0
window.loadVersion = async (request, { signal: abort }) => {
  const wire = toBinary(Service.method.get.input, create(Service.method.get.input, request))
  const parsed = fromBinary(Service.method.get.input, wire)
  const ref = parsed.ref.value
  window.calls.push({ id: String(ref.id), version: String(ref.version), type: ref.type })
  await new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, window.delay)
    abort.addEventListener(
      "abort",
      () => {
        clearTimeout(timer)
        window.aborted++
        reject(new Error("aborted"))
      },
      { once: true },
    )
  })
  if (window.fail) throw new Error("synthetic read failure")
  const body = create(Service.method.get.output, {
    element: {
      ref,
      visible: true,
      tags: {},
      context: {
        members: [],
        parents: [],
        render: {
          nodes:
            ref.type === 0
              ? [
                  {
                    id: ref.id,
                    location: {
                      lon: -0.12 + Number(ref.id) * 0.01 + Number(ref.version) * 0.002,
                      lat: 51.5 + Number(ref.id) * 0.003,
                    },
                  },
                ]
              : [],
          ways:
            ref.type === 1
              ? [
                  {
                    id: ref.id,
                    line: polylineEncode(
                      [
                        [-0.115 + Number(ref.version) * 0.001, 51.498],
                        [-0.102 + Number(ref.version) * 0.001, 51.509],
                      ],
                      6,
                    ),
                    isArea: false,
                  },
                ]
              : [],
        },
      },
      changeset: { id: 22n, createdAt: 1n, commentRich: "" },
    },
  })
  return fromBinary(Service.method.get.output, toBinary(Service.method.get.output, body))
}
window.map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {},
    layers: [{ id: "background", type: "background", paint: { "background-color": "#f0f3f1" } }],
  },
  center: [-0.1, 51.5],
  zoom: 12,
  canvasContextAttributes: { preserveDrawingBuffer: true },
  attributionControl: false,
})
window.active = signal(false)
window.mount = (large = false) => {
  render(
    <ChangesetDiffControl
      key={String(large)}
      data={{
        id: 22n,
        nodes: large
          ? Array.from({ length: 201 }, (_, i) => ({
              id: BigInt(i + 1),
              version: 1n,
              visible: true,
            }))
          : [
              { id: 1n, version: 2n, visible: true },
              { id: 2n, version: 3n, visible: false },
              { id: 3n, version: 1n, visible: true },
            ],
        ways: large ? [] : [{ id: 4n, version: 2n, visible: true }],
        relations: [{ id: 9n }],
      }}
      map={window.map}
      active={window.active}
    />,
    document.querySelector("main"),
  )
}
window.unmount = () => render(null, document.querySelector("main"))
window.map.on("load", () => window.mount())
