from sqlalchemy import text


def test_db_session_executes_query(db_session):
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_redis_roundtrip(fake_redis):
    fake_redis.set("k", "v")
    assert fake_redis.get("k") == "v"
