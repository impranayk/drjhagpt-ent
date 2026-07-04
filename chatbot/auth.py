"""Open-source login gate via streamlit-authenticator (Phase 2).

Cookie-based login with bcrypt-hashed passwords and per-user roles, configured in
`.streamlit/auth.yaml`. Fully open-source (Apache-2.0), no license, no server.
Degrades gracefully to open access if disabled or the library is unavailable.
"""
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _authenticator():
    import yaml
    import streamlit_authenticator as stauth

    with open(config.AUTH_CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return stauth.Authenticate(
        cfg["credentials"],
        cfg["cookie"]["name"],
        cfg["cookie"]["key"],
        cfg["cookie"]["expiry_days"],
    )


def gate():
    """Render login if needed. Returns (authenticated, username, roles).

    With auth disabled, returns (True, 'anonymous', ['admin']).
    """
    import streamlit as st

    if not config.ENABLE_AUTH:
        return True, "anonymous", ["admin"]

    try:
        _authenticator().login(location="main")
    except Exception as exc:
        st.warning(f"Login unavailable ({exc}); continuing without auth.")
        return True, "anonymous", ["admin"]

    status = st.session_state.get("authentication_status")
    if status:
        return True, st.session_state.get("username"), (st.session_state.get("roles") or [])
    if status is False:
        st.error("Username or password is incorrect.")
    else:
        st.info("Please log in to use DrJhaGPT Enterprise.  ·  demo user → **demo / demo1234**")
    return False, None, []


def render_logout():
    """Render a logout button in the sidebar (best-effort)."""
    try:
        _authenticator().logout(location="sidebar")
    except Exception:
        pass
