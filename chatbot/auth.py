"""Session-based login gate with bcrypt-hashed passwords + roles (Phase 2).

Reads users from `.streamlit/auth.yaml`. Deliberately dependency-light (bcrypt +
PyYAML) and cookie-free, so it works reliably on any host — including Streamlit
Community Cloud, where cookie/JWT-based auth libraries can misbehave. It fails to
a login form, never to open access.

For production SSO/RBAC, front the app with Keycloak/Authentik (OIDC) — see
DEPLOYMENT.md.
"""
import base64
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    """Base64 logo for the login card (empty string if the asset is missing)."""
    try:
        if config.LOGO_PATH.exists():
            b64 = base64.b64encode(config.LOGO_PATH.read_bytes()).decode()
            return f"data:image/png;base64,{b64}"
    except Exception:
        pass
    return ""


@lru_cache(maxsize=1)
def _users():
    import yaml

    with open(config.AUTH_CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("credentials", {}).get("usernames", {})


def _verify(username: str, password: str):
    """Return {name, roles} on success, else None."""
    import bcrypt

    user = _users().get(username)
    if not user:
        return None
    try:
        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            return {"name": user.get("name", username), "roles": user.get("roles", [])}
    except Exception:
        return None
    return None


def gate():
    """Render a login form if needed. Returns (authenticated, username, roles).

    With auth disabled, returns (True, 'anonymous', ['admin']).
    """
    import streamlit as st

    if not config.ENABLE_AUTH:
        return True, "anonymous", ["admin"]

    session = st.session_state.get("dj_auth")
    if session:
        return True, session["username"], session["roles"]

    logo = _logo_data_uri()
    img = f'<img src="{logo}" class="dj-login-logo" alt="logo">' if logo else ""
    with st.container(key="dj_login_card"):
        st.markdown(
            f"""
            <div class="dj-login-head">
              {img}
              <div>
                <div class="dj-login-word">DrJha<span class="accent">GPT</span><span class="dj-login-pro">PRO</span></div>
                <div class="dj-login-eyebrow">{config.BRAND_EYEBROW}</div>
              </div>
            </div>
            <hr class="dj-login-rule">
            <div class="dj-login-title">Sign in</div>
            <div class="dj-login-sub">Enter your credentials to access the workspace.</div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("dj_login", clear_on_submit=False):
            username = st.text_input("Username", placeholder="username")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            info = _verify((username or "").strip(), password or "")
            if info:
                st.session_state["dj_auth"] = {
                    "username": (username or "").strip(),
                    "roles": info["roles"],
                    "name": info["name"],
                }
                st.rerun()
            st.error("Username or password is incorrect.")
        st.markdown(
            f'<div class="dj-login-foot">Secured access · '
            f'<a href="{config.WEBSITE_URL}" target="_blank">drpranayjha.com</a></div>',
            unsafe_allow_html=True,
        )
    return False, None, []


def render_logout():
    """Render a logout button (call inside the sidebar context)."""
    import streamlit as st

    if st.button("Log out", use_container_width=True):
        st.session_state.pop("dj_auth", None)
        st.rerun()
