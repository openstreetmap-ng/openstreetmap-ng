from app.lib.pydantic_settings import register

IN_NIX_SHELL: str | None = None


def test_register():
    assert IN_NIX_SHELL is None
    register(__name__, globals())
    assert IN_NIX_SHELL is not None
