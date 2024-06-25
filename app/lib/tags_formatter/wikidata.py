import cython

from app.models.tag_format import TagFormat, TagFormatCollection


@cython.cfunc
def _is_wiki_id(s: str) -> cython.char:
    s_len: cython.int = len(s)
    if s_len < 2:
        return False

    s_0 = s[0]
    if s_0 != 'Q' and s_0 != 'q':
        return False

    s_1 = s[1]
    if not ('1' <= s_1 <= '9'):
        return False

    i: cython.int
    for i in range(2, s_len):  # noqa: SIM110
        if not ('0' <= s[i] <= '9'):
            return False

    return True


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_wiki_id(value):
            success = True
            url = f'https://www.wikidata.org/entity/{value}'
            new_styles.append(TagFormat(value, 'url-safe', url))
        else:
            new_styles.append(TagFormat(value))

    if success:
        tag.values = new_styles


def configure_wikidata_format(method_map: dict) -> None:
    method_map['wikidata'] = _format
