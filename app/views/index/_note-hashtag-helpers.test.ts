import { expect, mock, test } from "bun:test"

mock.module("@utils/config", () => ({ NOTE_COMMENT_BODY_MAX_LENGTH: 2000 }))
mock.module("i18next", () => ({ t: (key: string) => key }))

const { buildNoteBody, buildNoteTagUpdate } = await import("./_note-hashtag-helpers")

test("combines committed and pending hashtags without duplicates", () => {
  expect(buildNoteBody("Road", ["#survey", "survey;osm-ng"])).toBe("Road\n#survey #osm-ng")
  expect(buildNoteBody("Road #survey", ["survey"])).toBe("Road #survey")
  expect(buildNoteBody("Road", [""])).toBe("Road")
})

test("accepts Unicode hashtags and preserves URL fragments", () => {
  expect(buildNoteBody("Road", ["العربية;नमस्ते;𐐀"])).toBe("Road\n#العربية #नमस्ते #𐐀")
  expect(buildNoteBody("See https://example.org/#survey", ["survey"])).toBe(
    "See https://example.org/#survey\n#survey",
  )
})

test("matches Python hashtag boundaries rather than JavaScript whitespace", () => {
  expect(buildNoteBody("Road\u0085#survey", ["survey"])).toBe("Road\u0085#survey")
  expect(buildNoteBody("Road\u001c#survey", ["survey"])).toBe("Road\u001c#survey")
  expect(buildNoteBody("Road\ufeff#survey", ["survey"])).toBe("Road\ufeff#survey\n#survey")
})

test("rejects tokens the storage extractor cannot preserve as hashtags", () => {
  for (const value of ["#", "#---", "#\u0301", "a/b", "<script>"]) {
    expect(() => buildNoteBody("Road", [value])).toThrow("note.hashtags_invalid")
  }
})

test("enforces the combined storage limit including description hashtags", () => {
  expect(buildNoteBody("R", ["a".repeat(254)])).toBe(`R\n#${"a".repeat(254)}`)
  expect(() => buildNoteBody("R", ["a".repeat(255)])).toThrow("note.hashtags_too_long")
  expect(() => buildNoteBody(`#${"a".repeat(250)}`, ["more"])).toThrow("note.hashtags_too_long")
})

test("enforces the RPC body limit using Unicode code points", () => {
  expect([...buildNoteBody("a".repeat(1997), ["b"])]).toHaveLength(2000)
  expect([...buildNoteBody("𐐀".repeat(1997), ["b"])]).toHaveLength(2000)
  expect(() => buildNoteBody("a".repeat(1998), ["b"])).toThrow(
    "note.description_and_hashtags_too_long",
  )
})

test("explicit hashtag updates retain other tags and never mutate current state", () => {
  const current = { source: "survey", hashtags: "#old" }
  expect(buildNoteTagUpdate(current, ["new", "#new", "pending"])).toEqual({
    source: "survey",
    hashtags: "#new;#pending",
  })
  expect(current).toEqual({ source: "survey", hashtags: "#old" })
})

test("clearing hashtags removes the key while retaining unrelated tags", () => {
  expect(
    buildNoteTagUpdate({ source: "survey", hashtags: "#old" }, [""]),
  ).toEqual({
    source: "survey",
  })
  expect(buildNoteTagUpdate({ hashtags: "#old" }, [])).toEqual({})
})

test("explicit updates validate pending tokens and Unicode value length", () => {
  expect(() => buildNoteTagUpdate({}, ["a/b"])).toThrow("note.hashtags_invalid")
  expect(() => buildNoteTagUpdate({}, ["a".repeat(255)])).toThrow(
    "note.hashtags_too_long",
  )
  expect(buildNoteTagUpdate({}, ["العربية;𐐀"])).toEqual({
    hashtags: "#العربية;#𐐀",
  })
})
