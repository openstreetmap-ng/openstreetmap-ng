from collections.abc import Sequence

from fastapi import Depends, params

from app.lib.exceptions_context import raise_for
from app.lib.xmltodict import XMLToDict
from app.middlewares.request_context_middleware import get_request


def xml_body(path: str) -> params.Depends:
    """
    Returns a dependency for extracting XML data from the request body.
    """
    parts: list[str] = path.split('/')
    bad_xml_name = parts[-1]
    bad_xml_message = f"XML doesn't contain an {path} element."

    # backwards compatibility
    if bad_xml_name == 'gpx_file':
        bad_xml_name = 'trace'

    def dependency() -> dict | Sequence:
        xml = get_request()._body  # noqa: SLF001
        data = XMLToDict.parse(xml)

        for part in parts:
            if not isinstance(data, dict):
                raise_for.bad_xml(bad_xml_name, bad_xml_message, xml)

            data = data.get(part)
            if data is None:
                raise_for.bad_xml(bad_xml_name, bad_xml_message, xml)

        # don't allow empty dicts or lists
        if not data:
            raise_for.bad_xml(bad_xml_name, bad_xml_message, xml)

        return data

    return Depends(dependency)
