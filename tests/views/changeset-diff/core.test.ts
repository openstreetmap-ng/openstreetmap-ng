import { expect, test } from "bun:test"
import {
  loadChangesetDiff,
  DiffTooLargeError,
  MAX_DIFF_ELEMENTS,
  type DiffVersion,
} from "../../../app/views/index/_changeset-diff"
import type { DataValid as ChangesetData } from "@proto/changeset_pb"
import type { DataValid as ElementData } from "@proto/element_pb"
import { ElementType } from "@proto/shared_pb"
import { polylineEncode } from "@utils/polyline"

const changeset = (nodes: object[] = [], ways: object[] = []) =>
  ({ nodes, ways, relations: [] }) as unknown as ChangesetData
const response = (ref: DiffVersion): ElementData =>
  ({
    ref,
    visible: true,
    context: {
      render: {
        nodes:
          ref.type === ElementType.node
            ? [
                { id: ref.id, location: { lon: Number(ref.version), lat: 1 } },
                { id: 999n, location: { lon: 0, lat: 0 } },
              ]
            : [],
        ways:
          ref.type === ElementType.way
            ? [
                {
                  id: ref.id,
                  line: polylineEncode(
                    [
                      [1, 1],
                      [Number(ref.version), 2],
                    ],
                    6,
                  ),
                  isArea: false,
                },
              ]
            : [],
      },
    },
  }) as unknown as ElementData

test("before/after exact versions, duplicate edit grouping, create/delete and way geometry", async () => {
  const calls: DiffVersion[] = []
  const data = changeset(
    [
      { id: 1n, version: 1n, visible: true },
      { id: 2n, version: 4n, visible: true },
      { id: 2n, version: 3n, visible: true },
      { id: 3n, version: 5n, visible: false },
    ],
    [{ id: 4n, version: 2n, visible: true }],
  )
  const result = await loadChangesetDiff(
    data,
    async (ref) => {
      calls.push(ref)
      return response(ref)
    },
    new AbortController().signal,
  )
  expect(calls.map((r) => `${r.type}/${r.id}/${r.version}`).sort()).toEqual([
    "0/1/1",
    "0/2/2",
    "0/2/4",
    "0/3/4",
    "1/4/1",
    "1/4/2",
  ])
  expect(result.features).toHaveLength(6)
  expect(result.features.filter((f) => f.properties?.phase === "before")).toHaveLength(3)
  expect(result.features.some((f) => f.properties?.id === "999")).toBe(false)
  expect(result.features.find((f) => f.id === "0/2/before/0")?.geometry).toEqual({
    type: "Point",
    coordinates: [2, 1],
  })
  expect(result.features.find((f) => f.id === "1/4/after/0")?.geometry.type).toBe("LineString")
})

test("large request rejects before network, never truncates silently", async () => {
  let calls = 0
  const data = changeset(
    Array.from({ length: MAX_DIFF_ELEMENTS + 1 }, (_, id) => ({
      id: BigInt(id + 1),
      version: 1n,
      visible: true,
    })),
  )
  await expect(
    loadChangesetDiff(
      data,
      async (ref) => {
        calls++
        return response(ref)
      },
      new AbortController().signal,
    ),
  ).rejects.toBeInstanceOf(DiffTooLargeError)
  expect(calls).toBe(0)
})

test("read concurrency stays at four", async () => {
  let pending = 0,
    max = 0
  const data = changeset(
    Array.from({ length: 12 }, (_, id) => ({ id: BigInt(id + 1), version: 1n, visible: true })),
  )
  const result = await loadChangesetDiff(
    data,
    async (ref) => {
      max = Math.max(max, ++pending)
      await Bun.sleep(5)
      pending--
      return response(ref)
    },
    new AbortController().signal,
  )
  expect(max).toBe(4)
  expect(result.features).toHaveLength(12)
})

test("pre-aborted request does not read versions", async () => {
  const controller = new AbortController()
  controller.abort()
  let calls = 0
  await expect(
    loadChangesetDiff(
      changeset(),
      async (ref) => {
        calls++
        return response(ref)
      },
      controller.signal,
    ),
  ).rejects.toThrow()
  expect(calls).toBe(0)
})

test("missing or mismatched geometry is an error, not an incomplete success", async () => {
  const data = changeset([{ id: 1n, version: 2n, visible: true }])
  await expect(
    loadChangesetDiff(
      data,
      async (ref) => ({ ...response(ref), visible: ref.version !== 2n }),
      new AbortController().signal,
    ),
  ).rejects.toThrow()
  await expect(
    loadChangesetDiff(
      data,
      async (ref) => response({ ...ref, version: 99n }),
      new AbortController().signal,
    ),
  ).rejects.toThrow("Mismatched")
})

test("restoration has no before geometry when the previous version is a tombstone", async () => {
  const result = await loadChangesetDiff(
    changeset([{ id: 1n, version: 3n, visible: true }]),
    async (ref) =>
      ref.version === 2n
        ? ({
            ...response(ref),
            visible: false,
            context: { render: { nodes: [], ways: [] } },
          } as unknown as ElementData)
        : response(ref),
    new AbortController().signal,
  )
  expect(result.features).toHaveLength(1)
  expect(result.features[0]?.properties?.phase).toBe("after")
  expect(result.features[0]?.properties?.version).toBe("3")
})

test("objects created and deleted in the same changeset have no endpoint geometry", async () => {
  let calls = 0
  const result = await loadChangesetDiff(
    changeset([
      { id: 1n, version: 1n, visible: true },
      { id: 1n, version: 2n, visible: false },
    ]),
    async (ref) => {
      calls++
      return response(ref)
    },
    new AbortController().signal,
  )
  expect(result.features).toHaveLength(0)
  expect(calls).toBe(0)
})
