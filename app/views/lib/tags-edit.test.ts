import { describe, expect, test } from "bun:test"
import { formatTagsForTextEdit } from "./tags-edit"

describe("formatTagsForTextEdit", () => {
  test("formats raw tags as sorted key-value lines", () => {
    expect(
      formatTagsForTextEdit({
        name: "Central Station",
        amenity: "bus_station",
        "addr:street": "Main Street",
      }),
    ).toBe("addr:street=Main Street\namenity=bus_station\nname=Central Station")
  })
})
