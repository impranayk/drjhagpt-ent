"""Session-based login gate with bcrypt-hashed passwords + roles.

Two backends, tried in order:
  1. Supabase `app_users` - when the shared library is configured. This is where
     people, roles and tracks live once more than one trainer uses the studio.
  2. `.streamlit/auth.yaml` - the built-in file, and the fallback that keeps a
     single-trainer install working with no database at all.

Deliberately dependency-light (bcrypt + PyYAML) and cookie-free, so it works
reliably on any host - including Streamlit Community Cloud, where cookie/JWT auth
libraries misbehave. It fails to a login form, never to open access.

`AUTH_PROVIDER` is the seam for a future SSO backend: add a branch in
`authenticate()` and nothing else in the app changes. For production SSO today,
front the app with Keycloak/Authentik (OIDC) - see DEPLOYMENT.md.
"""
import base64
from functools import lru_cache

from . import config, store

SESSION_KEY = "dj_auth"


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
def _file_users():
    import yaml

    try:
        with open(config.AUTH_CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    except OSError:
        return {}
    return (cfg.get("credentials") or {}).get("usernames", {}) or {}


def _check(password: str, hashed: str) -> bool:
    import bcrypt

    try:
        return bcrypt.checkpw((password or "").encode("utf-8"),
                              (hashed or "").encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _session_from_db(row: dict) -> dict:
    """Turn an app_users row into the session dict the app reads."""
    username = (row.get("username") or "").strip().lower()
    role = row.get("role") or config.ROLE_TRAINER
    if username in config.ADMIN_USERS:
        role = config.ROLE_ADMIN
    return {
        "username": username,
        "name": row.get("name") or username,
        "roles": [role],
        "track": row.get("track_code") or config.DEFAULT_TRACK,
        "can_share_all": bool(row.get("can_share_all")),
        "email": row.get("email") or "",
        "allowed_tools": row.get("allowed_tools") or None,
        "allowed_models": row.get("allowed_models") or None,
        "must_change_password": bool(row.get("must_change_password")),
        "source": "db",
    }


def _verify(identifier: str, password: str):
    """Return a session dict on success, else None.

    Accepts a username or an email address. The database is authoritative when
    configured; auth.yaml is the fallback so the studio still opens if Supabase
    is unreachable.
    """
    ident = (identifier or "").strip()
    if not ident or not password:
        return None

    if store.enabled():
        try:
            row = (store.get_user_by_email(ident) if "@" in ident
                   else store.get_user(ident))
            if row and row.get("active", True) and _check(password, row.get("password_hash")):
                return _session_from_db(row)
            if row:
                return None          # the account exists; the password is wrong
        except Exception:
            pass                     # database down -> fall through to the file

    user = _file_users().get(ident.lower())
    if user and _check(password, user.get("password", "")):
        roles = user.get("roles") or [config.ROLE_TRAINER]
        if ident.lower() in config.ADMIN_USERS:
            roles = [config.ROLE_ADMIN]
        return {
            "username": ident.lower(),
            "name": user.get("name", ident),
            "roles": roles,
            "track": user.get("track") or config.DEFAULT_TRACK,
            "can_share_all": bool(user.get("can_share_all")),
            "email": user.get("email", ""),
            "allowed_tools": user.get("allowed_tools"),
            "allowed_models": user.get("allowed_models"),
            "must_change_password": False,
            "source": "file",
        }
    return None


def authenticate(identifier: str, password: str):
    """Dispatcher for the configured auth backend (the SSO seam)."""
    if config.AUTH_PROVIDER in ("local", "", None):
        return _verify(identifier, password)
    raise NotImplementedError(
        f"AUTH_PROVIDER='{config.AUTH_PROVIDER}' is not implemented yet. "
        "Set AUTH_PROVIDER=local, or front the app with an OIDC proxy.")


# --- Session helpers ---------------------------------------------------------
def session() -> dict:
    import streamlit as st

    return st.session_state.get(SESSION_KEY) or {}


def roles() -> list:
    if not config.ENABLE_AUTH:
        return [config.ROLE_ADMIN]
    return session().get("roles") or [config.ROLE_TRAINER]


def role() -> str:
    r = roles()
    return r[0] if r else config.ROLE_TRAINER


def is_admin() -> bool:
    return config.ROLE_ADMIN in roles()


def is_lead() -> bool:
    """Admins and lead trainers set the shared agenda."""
    return bool({config.ROLE_ADMIN, config.ROLE_LEAD} & set(roles()))


def can_publish() -> bool:
    """Who may put material into the shared library."""
    return is_lead() or config.ROLE_TRAINER in roles()


def track() -> str:
    return session().get("track") or config.DEFAULT_TRACK


def publish_targets() -> list:
    """Track codes this user may publish to."""
    codes = store.track_codes()
    if is_lead() or session().get("can_share_all"):
        return ["all"] + codes
    own = track()
    return [own] if own in codes else codes[:1]


# --- The gate ----------------------------------------------------------------
def _request_access_form():
    """Let someone ask for an account, when the database is available."""
    import streamlit as st

    if not store.enabled():
        return
    with st.expander("Request access"):
        with st.form("dj_access_req", clear_on_submit=True):
            name = st.text_input("Your name")
            email = st.text_input("Work email")
            wanted = st.text_input("Preferred username")
            note = st.text_area("What will you use the studio for?", height=80)
            sent = st.form_submit_button("Send request", use_container_width=True)
        if sent:
            if not (name or "").strip():
                st.error("Please enter your name.")
                return
            try:
                store.create_access_request(name=name, email=email,
                                            username=(wanted or "").strip().lower(),
                                            note=note)
                st.success("Request sent. You'll hear back once it's reviewed.")
            except Exception as exc:
                st.error(f"Couldn't send the request: {exc}")


def gate():
    """Render a login form if needed. Returns (authenticated, username, roles).

    With auth disabled, returns (True, 'anonymous', ['admin']).
    """
    import streamlit as st

    if not config.ENABLE_AUTH:
        return True, "anonymous", [config.ROLE_ADMIN]

    sess = st.session_state.get(SESSION_KEY)
    if sess:
        return True, sess["username"], sess["roles"]

    logo = _logo_data_uri()
    img = f'<img src="{logo}" class="dj-login-logo" alt="logo">' if logo else ""
    with st.container(key="dj_login_card"):
        st.markdown(
            f"""
            <div class="dj-login-head">
              {img}
              <div>
                <div class="dj-login-word">DrJha<span class="accent">GPT</span><span class="dj-login-pro">PRO</span></div>
                <div class="dj-login-eyebrow">{config.BRAND_STUDIO_EYEBROW}</div>
              </div>
            </div>
            <hr class="dj-login-rule">
            <div class="dj-login-title">Sign in</div>
            <div class="dj-login-sub">Enter your credentials to access the studio.</div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("dj_login", clear_on_submit=False):
            username = st.text_input("Username or email", placeholder="username")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            info = authenticate((username or "").strip(), password or "")
            if info:
                st.session_state[SESSION_KEY] = info
                store.log_event(info["username"], "login", track=info.get("track"))
                st.rerun()
            st.error("Username or password is incorrect.")
        _request_access_form()
        st.markdown(
            f'<div class="dj-login-foot">Secured access · '
            f'<a href="{config.WEBSITE_URL}" target="_blank">drpranayjha.com</a></div>',
            unsafe_allow_html=True,
        )
    return False, None, []


def force_password_change():
    """Block the studio until a DB user replaces an admin-issued password.

    Returns True when the app should stop and let the user set a new one.
    """
    import streamlit as st

    sess = session()
    if not sess.get("must_change_password") or sess.get("source") != "db":
        return False

    st.warning("Your password was set by an administrator. "
               "Please choose a new one to continue.")
    with st.form("dj_pwchange"):
        p1 = st.text_input("New password", type="password")
        p2 = st.text_input("Confirm new password", type="password")
        ok = st.form_submit_button("Set password", use_container_width=True)
    if ok:
        if len(p1 or "") < 10:
            st.error("Use at least 10 characters.")
        elif p1 != p2:
            st.error("The two passwords don't match.")
        else:
            try:
                store.update_user(sess["username"], password=p1,
                                  must_change_password=False)
                st.session_state[SESSION_KEY]["must_change_password"] = False
                store.log_event(sess["username"], "password_change")
                st.success("Password updated.")
                st.rerun()
            except Exception as exc:
                st.error(f"Couldn't update the password: {exc}")
    return True


def render_logout():
    """Render a logout button (call inside the sidebar context)."""
    import streamlit as st

    if st.button("Log out", use_container_width=True):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()
