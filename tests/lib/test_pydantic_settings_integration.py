from app.lib.pydantic_settings_integration import pydantic_settings_integration

IN_NIX_SHELL: str | None = None


def test_pydantic_settings_integration():
    assert IN_NIX_SHELL is None
    pydantic_settings_integration(__name__, globals())
    assert IN_NIX_SHELL is not None
