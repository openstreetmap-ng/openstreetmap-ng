## Base Element

The base element defines the core attributes shared by all map objects.

| Attribute | Type | Description |
| --- | --- | --- |
| type | String | The type of object (node, way, relation). |
| id | Integer | Unique identifier within its object type. |
| version | Integer | The object's version number. |
| visible | Boolean | Indicates whether the object should be rendered (deleted flag). |
| tags | Map<KeyString, ValueString> | Key-value pairs for additional object properties. |
| created_at | DateTime | Creation timestamp (ISO 8601, UTC). |
| user_id | Integer |  Identifier of the user who created the version. |
| changeset_id | Integer | Identifier of the changeset where this version was created. |

### KeyString, ValueString

KeyString and ValueString are used in an object's tags map for custom properties. Limitations differ slightly depending on the action (writing to the API or reading from the API).

#### Writing to the API

##### KeyString

API 0.7 aims to standardize the character space for tag keys. Making them more predictable and easier to work with. These new restrictions are fully backwards compatible with the current API 0.6.

- **Maximum Length**: 63 unicode characters
- **Allowed Characters**: `[A-Za-z0-9.:_-]`

###### Additional Server Postprocessing

Keys are stripped of leading/trailing whitespace. Tags with empty keys or keys in the **discardable** category are ignored.

###### Rationale

Long keys are difficult to work with, and are more often than not, a result of an error (for example, when key merges with value). The 63 character limit puts a safe upper bound on the length of a key. This limit was determined through <https://taginfo.openstreetmap.org/reports/key_lengths>.

The limited character space was defined through the analysis of <https://taginfo.openstreetmap.org/reports/characters_in_keys>. Keep in mind that the taginfo characters statistics page is slightly outdated as it includes the widely-used '-' (dash) and '.' (dot) characters in the F/Rest category.

The **discardable** category set will be defined through the analysis of iD and JOSM presets. It aims to unify the discardable tags behavior across all editors (even those not implementing such presets).

##### ValueString

- **Maximum Length**: 255 unicode characters
- **Restricted Characters**: `[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\uFFFE\uFFFF]`

Any character not matching the above restricted range is allowed. This pattern is derived primarily from the [XML 1.0](https://www.w3.org/TR/2006/REC-xml-20060816/#charsets) specification and is also used in the API 0.6.

###### Additional Server Postprocessing

Values are stripped of leading/trailing whitespace and NFC-normalized. Tags with empty values are ignored.

###### Rationale

The new NFC-normalization postprocessing step ensures greater consistency in the data and makes the data less bug-prone for data consumers. The normalization does not change the meaning of strings, but it ensures they are represented in a consistent way.

#### Reading from the API

##### KeyString, ValueString

- **Maximum Length**: 255 unicode characters
- **Restricted Characters**: None

The strings must be treated as untrusted user input: they must be escaped before being used in a web page or database query. This behavior is consistent with the current API 0.6.

## Node Element

A point on the map. Inherits from the Base Element.

| Attribute | Type | Description |
| --- | --- | --- |
| lon | Optional\<Decimal> | Longitude (7 decimal places of precision). |
| lat | Optional\<Decimal> | Latitude (7 decimal places of precision). |

**Additional Constraints**

Longitude and latitude are present if and only if the node is visible.

### Example

```json
{
    "type": "node",
    "id": 1,
    "version": 1,
    "visible": true,
    "tags": {
        "amenity": "restaurant",
        "name": "Crab Shack"
    },
    "created_at": "2019-01-01T00:00:00Z",
    "user_id": 15215305,
    "changeset_id": 148023492,
    "lon": 135.1234567,
    "lat": -34.1234567
}
```

## Relation Element

Represents a logical grouping of map objects, associating them with roles. Inherits from the Base Element.

| Attribute | Type | Description |
| --- | --- | --- |
| members | List\<Member> | A list of object references and their roles in the relation. |

**Additional Constraints**

Must contain at least one member if visible.

All members must be visible throughout the relation version's lifespan.

Must not create direct circular references (a relation containing itself).

### Member

The member type is a small structure with the following attributes:

| Attribute | Type | Description |
| --- | --- | --- |
| type | String | The type of the member object (node, way, relation). |
| id | Integer | Unique identifier of the member object. |
| role | String | Describes the member's function within the relation. |

### Example

```json
{
    "type": "relation",
    "id": 1,
    "version": 1,
    "visible": true,
    "tags": {
        "type": "multipolygon",
        "landuse": "residential"
    },
    "created_at": "2019-01-01T00:00:00Z",
    "user_id": 15215305,
    "changeset_id": 148023492,
    "members": [
        {
            "type": "way",
            "id": 1,
            "role": "outer"
        },
        {
            "type": "way",
            "id": 2,
            "role": "inner"
        }
    ]
}
```

## Way Element

An ordered list of nodes representing a linear feature (e.g., road, river, building). Inherits from Relation.

**Additional Constraints**

Must contain at least two members if visible.

All members must refer to nodes and have empty roles.

No consecutive members can have the same id.

### Example

```json
{
    "type": "way",
    "id": 1,
    "version": 1,
    "visible": true,
    "tags": {
        "highway": "residential",
        "name": "Main Street"
    },
    "created_at": "2019-01-01T00:00:00Z",
    "user_id": 15215305,
    "changeset_id": 148023492,
    "members": [
        {
            "type": "node",
            "id": 1,
            "role": ""
        },
        {
            "type": "node",
            "id": 2,
            "role": ""
        }
    ]
}
```
