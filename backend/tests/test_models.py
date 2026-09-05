from app.models import User, Link, Click


def test_create_user_link_click(db_session):
    user = User(email="a@example.com", name="A", google_sub="sub-1")
    db_session.add(user)
    db_session.flush()

    link = Link(code="abc1234", target_url="https://example.com", owner_id=user.id)
    db_session.add(link)
    db_session.flush()

    click = Click(link_id=link.id, referrer="https://ref.com", user_agent="pytest")
    db_session.add(click)
    db_session.flush()

    assert link.owner.email == "a@example.com"
    assert link.clicks[0].referrer == "https://ref.com"


def test_link_owner_is_optional(db_session):
    link = Link(code="anon001", target_url="https://example.com", owner_id=None)
    db_session.add(link)
    db_session.flush()
    assert link.owner_id is None
