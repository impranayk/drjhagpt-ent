"""Shared library and people store, on Supabase via the PostgREST API over httpx.

Entirely optional. With SUPABASE_URL / SUPABASE_KEY unset, `enabled()` is False:
the studio runs as a single-trainer tool, logins fall back to
`.streamlit/auth.yaml`, and the Library / Admin Console simply don't appear.

Tables (SQL in SUPABASE_SETUP.md). Every name is prefixed with `config.DB_PREFIX`
(default `dj_`) so this app can share a Supabase project with another one without
fighting over generic names like `app_users` or `events`:

    dj_tracks(code, name, focus, active)
    dj_app_users(username, name, password_hash, role, track_code, can_share_all,
                 active, email, mobile, photo, auth_sub, allowed_tools,
                 allowed_models, must_change_password)
    dj_library(id, created_at, author, tool, title, content_md, tracks jsonb,
               course, cohort, tech_area, product_version, tags, attachment_url,
               meeting, status)
    dj_access_requests(id, created_at, name, email, username, role, track_code,
                       note, status, decided_by, decided_at)
    dj_events(id, created_at, actor, action, detail, track)
"""
from typing import List, Optional

from . import config


def enabled() -> bool:
    return config.LIBRARY_ENABLED


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def table_name(table: str) -> str:
    """The physical table name for a logical one ('library' -> 'dj_library')."""
    prefix = config.DB_PREFIX or ""
    return table if table.startswith(prefix) else prefix + table


def _rest(table: str) -> str:
    return f"{config.SUPABASE_URL.rstrip('/')}/rest/v1/{table_name(table)}"


def _get(table, params):
    import httpx
    r = httpx.get(_rest(table), headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _insert(table, row):
    import httpx
    r = httpx.post(_rest(table),
                   headers={**_headers(), "Prefer": "return=representation"},
                   json=row, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data[0] if isinstance(data, list) and data else data


def _patch(table, match, fields):
    import httpx
    r = httpx.patch(_rest(table),
                    headers={**_headers(), "Prefer": "return=representation"},
                    params=match, json=fields, timeout=20)
    r.raise_for_status()
    return r.json()


def _delete(table, match):
    import httpx
    r = httpx.delete(_rest(table), headers=_headers(), params=match, timeout=20)
    r.raise_for_status()


def _hash_pw(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


# =============================================================================
#  Tracks
# =============================================================================
def list_tracks() -> List[dict]:
    return _get("tracks", {"select": "*", "order": "name.asc"})


def create_track(code: str, name: str, focus: str = None) -> dict:
    row = {"code": code.strip().upper(), "name": name.strip(), "active": True}
    if focus:
        row["focus"] = focus.strip()
    try:
        return _insert("tracks", row)
    except Exception:
        if "focus" in row:          # tolerate a DB without the optional column
            row.pop("focus")
            return _insert("tracks", row)
        raise


def set_track_active(code: str, active: bool) -> None:
    _patch("tracks", {"code": f"eq.{code}"}, {"active": bool(active)})


def track_codes() -> List[str]:
    """Track codes from the database, falling back to the TRACKS setting."""
    if enabled():
        try:
            rows = [t for t in list_tracks() if t.get("active", True)]
            if rows:
                return [t["code"] for t in rows]
        except Exception:
            pass
    return list(config.TRACKS)


def track_label_map() -> dict:
    labels = dict(config.TRACK_LABELS)
    if enabled():
        try:
            for t in list_tracks():
                labels[t["code"]] = t.get("name") or t["code"]
        except Exception:
            pass
    return labels


# =============================================================================
#  People
# =============================================================================
def list_users() -> List[dict]:
    return _get("app_users", {"select": "*", "order": "name.asc"})


def get_user(username: str) -> Optional[dict]:
    rows = _get("app_users", {"select": "*",
                              "username": f"eq.{(username or '').strip().lower()}",
                              "limit": "1"})
    return rows[0] if rows else None


def get_user_by_email(email: str) -> Optional[dict]:
    """Look a user up by email, so people can sign in with either identifier."""
    # PostgREST treats '*' as a wildcard in `ilike`, so a submitted '*@*' would
    # match the first row in the table. Reject anything that isn't a plain address.
    e = (email or "").strip()
    if not e or any(c in e for c in "*,()"):
        return None
    rows = _get("app_users", {"select": "*", "email": f"ilike.{e}", "limit": "1"})
    return rows[0] if rows else None


def create_user(*, username, name, password, role, track_code=None,
                can_share_all=False, email=None, mobile=None,
                allowed_tools=None, allowed_models=None,
                must_change_password=True) -> dict:
    row = {
        "username": username.strip().lower(), "name": name.strip(),
        "password_hash": _hash_pw(password), "role": role,
        "track_code": track_code, "can_share_all": bool(can_share_all),
        "active": True,
        # An admin chose this password, so it is temporary by definition.
        "must_change_password": bool(must_change_password),
    }
    for key, val in (("email", (email or "").strip()), ("mobile", (mobile or "").strip()),
                     ("allowed_tools", allowed_tools), ("allowed_models", allowed_models)):
        if val:
            row[key] = val
    return _insert("app_users", row)


def update_user(username: str, **fields) -> list:
    if "password" in fields:
        fields["password_hash"] = _hash_pw(fields.pop("password"))
    return _patch("app_users", {"username": f"eq.{username.strip().lower()}"}, fields)


# =============================================================================
#  Access requests
# =============================================================================
def create_access_request(*, name, email=None, username=None, role=None,
                          track_code=None, note=None) -> dict:
    row = {"name": name.strip(), "status": "pending"}
    for key, val in (("email", email), ("username", username), ("role", role),
                     ("track_code", track_code), ("note", note)):
        if val:
            row[key] = str(val).strip()
    return _insert("access_requests", row)


def list_access_requests(status: str = None, limit: int = 200) -> List[dict]:
    params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    if status:
        params["status"] = f"eq.{status}"
    return _get("access_requests", params)


def update_access_request(req_id, **fields) -> list:
    return _patch("access_requests", {"id": f"eq.{req_id}"}, fields)


# =============================================================================
#  Audit log
# =============================================================================
def log_event(actor: str, action: str, detail: str = None, track: str = None) -> None:
    """Best-effort audit line. Never raises - logging must not break the studio."""
    if not enabled():
        return
    try:
        row = {"actor": actor or "anon", "action": action}
        if detail:
            row["detail"] = str(detail)[:300]
        if track:
            row["track"] = track
        _insert("events", row)
    except Exception:
        pass


def list_events(limit: int = 200) -> List[dict]:
    return _get("events", {"select": "*", "order": "created_at.desc",
                           "limit": str(limit)})


# =============================================================================
#  Shared library
# =============================================================================
def visible_to(item: dict, track: Optional[str], author: str = None) -> bool:
    """Whether a library item should be shown to someone on `track`."""
    targets = item.get("tracks") or []
    if isinstance(targets, str):
        targets = [targets]
    if "all" in targets:
        return True
    if track and track in targets:
        return True
    return bool(author) and item.get("author") == author


def publish(*, author, tool, title, content_md, tracks, course=None, cohort=None,
            tech_area=None, product_version=None, tags=None, attachment_url=None,
            meeting=None, status="published") -> dict:
    row = {
        "author": author, "tool": tool, "title": (title or "Untitled")[:200],
        "content_md": content_md, "tracks": list(tracks or []), "status": status,
    }
    for key, val in (("course", course), ("cohort", cohort),
                     ("tech_area", tech_area), ("product_version", product_version),
                     ("tags", tags), ("attachment_url", attachment_url),
                     ("meeting", meeting)):
        if val:
            row[key] = val
    return _insert("library", row)


def list_library(*, tool: str = None, course: str = None, limit: int = 200) -> List[dict]:
    params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    if tool:
        params["tool"] = f"eq.{tool}"
    if course:
        params["course"] = f"eq.{course}"
    return _get("library", params)


def update_item(item_id, **fields) -> list:
    return _patch("library", {"id": f"eq.{item_id}"}, fields)


def delete_item(item_id) -> None:
    _delete("library", {"id": f"eq.{item_id}"})


def upload_file(data: bytes, filename: str) -> Optional[str]:
    """Put a file in the 'studio' storage bucket and return its public URL.

    Returns None (rather than raising) when storage isn't set up, so attaching a
    file is always optional.
    """
    if not enabled() or not data:
        return None
    import re
    import httpx

    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename or "file").strip("-")[:80]
    # PostgREST rows carry no clock, and the studio must not call time.time() for
    # a name that has to be stable across a rerun - the row id is added by the
    # caller instead, so collisions resolve with upsert.
    path = f"uploads/{safe}"
    url = f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/studio/{path}"
    headers = {"apikey": config.SUPABASE_KEY,
               "Authorization": f"Bearer {config.SUPABASE_KEY}",
               "x-upsert": "true"}
    try:
        r = httpx.post(url, headers=headers, content=data, timeout=60)
        if r.status_code >= 400:
            return None
        return (f"{config.SUPABASE_URL.rstrip('/')}"
                f"/storage/v1/object/public/studio/{path}")
    except Exception:
        return None


def post_to_website(*, title: str, html: str, category: str = "post",
                    status: str = "draft") -> Optional[str]:
    """Push an article to drpranayjha.com as a draft, if the bridge is configured.

    Returns the created post's edit URL, or None when the bridge is off.
    """
    if not config.WEBSITE_POST_READY:
        return None
    import httpx

    try:
        r = httpx.post(config.WEBSITE_POST_URL,
                       params={"token": config.WEBSITE_POST_TOKEN},
                       json={"title": title, "content": html,
                             "category": category, "status": status},
                       timeout=45)
        if r.status_code >= 400:
            raise RuntimeError(f"Website returned {r.status_code}: {r.text[:200]}")
        data = r.json()
        return data.get("edit_url") or data.get("link") or "ok"
    except Exception as exc:
        raise RuntimeError(str(exc))
