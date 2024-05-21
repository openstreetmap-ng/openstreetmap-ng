from app.lib.snowflake import snowflake_id


def test_snowflake_unique():
    assert snowflake_id() != snowflake_id()


def test_snowflake_63_bits():
    assert snowflake_id() < 0x80000000_00000000
