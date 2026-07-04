from chatbot import auth


def test_demo_login_succeeds():
    info = auth._verify("demo", "demo1234")
    assert info is not None
    assert "viewer" in info["roles"]


def test_wrong_password_fails():
    assert auth._verify("demo", "wrong-password") is None


def test_unknown_user_fails():
    assert auth._verify("ghost", "whatever") is None
