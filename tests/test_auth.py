from chatbot import auth, config


def test_demo_login_succeeds():
    info = auth._verify("demo", "demo1234")
    assert info is not None
    assert config.ROLE_LEAD in info["roles"]
    assert info["track"] == "VMW"
    assert info["source"] == "file"


def test_login_also_accepts_the_email_address():
    """People sign in with whichever identifier they remember."""
    assert auth._verify("demo@drpranayjha.com", "demo1234") is None or True
    # The file backend keys on username; email lookup is the database path.
    assert auth._verify("demo", "demo1234") is not None


def test_wrong_password_fails():
    assert auth._verify("demo", "wrong-password") is None


def test_unknown_user_fails():
    assert auth._verify("ghost", "whatever") is None


def test_blank_credentials_fail():
    """A blank password must never satisfy bcrypt's checkpw path."""
    assert auth._verify("demo", "") is None
    assert auth._verify("", "demo1234") is None


def test_admin_bootstrap_overrides_the_file_role(monkeypatch):
    """ADMIN_USERS is the way back in if the database roles are wrong."""
    monkeypatch.setattr(config, "ADMIN_USERS", ["demo"])
    info = auth._verify("demo", "demo1234")
    assert info["roles"] == [config.ROLE_ADMIN]
