"""The shared library and the Admin Console.

Both are gated on `store.enabled()` - with no Supabase configured the studio is a
single-trainer tool and neither appears. Every consequential action (creating a
person, disabling an account, deleting shared material) sits behind an explicit
confirm and writes an audit line.
"""
import html as _html

import streamlit as st
import streamlit.components.v1 as components

from . import auth, config, render, store, studio


def _chip(text, kind="n"):
    return f'<span class="dj-chip dj-chip-{kind}">{_html.escape(str(text))}</span>'


def _role_chip(role):
    kind = {"admin": "a", "lead": "l", "trainer": "t"}.get(role, "n")
    return _chip(config.ROLE_LABELS.get(role, role), kind)


def _needs_db():
    st.info("The shared library and Admin Console need a database. Add "
            "`SUPABASE_URL` and `SUPABASE_KEY` to your secrets — see "
            "`SUPABASE_SETUP.md` for the SQL and the five-minute setup.")


# =============================================================================
#  Shared library
# =============================================================================
def tool_library():
    st.markdown('<p class="dj-tool-blurb">Course material published to your track '
                'by the team.</p>', unsafe_allow_html=True)
    if not store.enabled():
        _needs_db()
        return

    try:
        items = store.list_library()
    except Exception as exc:
        st.error(f"Couldn't reach the library: {exc}")
        return

    me = auth.session().get("username", "")
    my_track = auth.track()
    visible = [i for i in items if store.visible_to(i, my_track, me)]
    if not visible:
        st.caption("Nothing has been shared with your track yet.")
        return

    labels = store.track_label_map()
    c1, c2, c3 = st.columns([2, 2, 3])
    tool_opts = ["All types"] + sorted({i.get("tool") for i in visible if i.get("tool")})
    pick_tool = c1.selectbox("Type", tool_opts,
                             format_func=lambda t: studio.TOOL_LABELS.get(t, t))
    course_opts = ["All courses"] + sorted({i.get("course") for i in visible
                                            if i.get("course")})
    pick_course = c2.selectbox("Course", course_opts)
    query = c3.text_input("Search", placeholder="title, tag or topic")

    rows = visible
    if pick_tool != "All types":
        rows = [i for i in rows if i.get("tool") == pick_tool]
    if pick_course != "All courses":
        rows = [i for i in rows if i.get("course") == pick_course]
    if (query or "").strip():
        q = query.lower().strip()
        rows = [i for i in rows
                if q in " ".join(str(i.get(f) or "") for f in
                                 ("title", "tags", "course", "cohort", "tech_area")).lower()]

    st.caption(f"{len(rows)} item(s)")
    for item in rows[:60]:
        title = item.get("title") or "Untitled"
        meta = " · ".join(x for x in [
            studio.TOOL_LABELS.get(item.get("tool"), item.get("tool")),
            item.get("course"), item.get("cohort"), item.get("product_version"),
            (item.get("created_at") or "")[:10]] if x)
        with st.expander(f"{title}  —  {meta}"):
            targets = item.get("tracks") or []
            st.markdown(
                "".join(_chip("All tracks" if t == "all" else labels.get(t, t), "t")
                        for t in targets)
                + (_chip(item.get("tags"), "n") if item.get("tags") else ""),
                unsafe_allow_html=True)
            body = item.get("content_md") or ""
            for kind, val in render.doc_segments(body, studio._logo_uri(), None,
                                                 config.BRAND_FULL):
                if kind == "mermaid":
                    components.html(render.mermaid_frame(val), height=470,
                                    scrolling=True)
                else:
                    st.markdown(val, unsafe_allow_html=True)

            if item.get("attachment_url"):
                st.markdown(f'<a class="dj-share-a" href="{item["attachment_url"]}" '
                            'target="_blank" rel="noopener">Download attachment</a>',
                            unsafe_allow_html=True)

            b1, b2, b3 = st.columns(3)
            with b1:
                st.download_button(
                    "Word",
                    render.download_html(body, title, studio._logo_uri(),
                                         eyebrow=config.BRAND_FULL),
                    file_name=f"{title[:50]}.doc", mime="application/msword",
                    key=f"lw::{item['id']}", use_container_width=True)
            with b2:
                st.download_button("Markdown", body, file_name=f"{title[:50]}.md",
                                   mime="text/markdown", key=f"lm::{item['id']}",
                                   use_container_width=True)
            with b3:
                components.html(studio.copy_button(body, key=f"L{item['id']}"),
                                height=44)

            if auth.is_lead() or item.get("author") == me:
                if st.checkbox("Remove this from the library",
                               key=f"ldel::{item['id']}"):
                    if st.button("Confirm removal", key=f"ldc::{item['id']}"):
                        try:
                            store.delete_item(item["id"])
                            store.log_event(me, "unpublish", detail=str(item["id"]))
                            st.success("Removed.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Couldn't remove it: {exc}")


# =============================================================================
#  Admin Console
# =============================================================================
def tool_admin():
    st.markdown('<p class="dj-tool-blurb">People, tracks, access requests and '
                'activity.</p>', unsafe_allow_html=True)
    if not auth.is_admin():
        st.warning("The Admin Console is available to administrators only.")
        return
    if not store.enabled():
        _needs_db()
        return

    try:
        pending = len(store.list_access_requests(status="pending"))
    except Exception:
        pending = 0
    tabs = st.tabs(["People", "Tracks", f"Requests ({pending})", "Activity"])

    with tabs[0]:
        _people_tab()
    with tabs[1]:
        _tracks_tab()
    with tabs[2]:
        _requests_tab()
    with tabs[3]:
        _activity_tab()


def _track_picker(label, key, current=None, allow_none=True):
    codes = store.track_codes()
    labels = store.track_label_map()
    opts = (["—"] if allow_none else []) + codes
    idx = opts.index(current) if current in opts else 0
    return st.selectbox(label, opts, index=idx, key=key,
                        format_func=lambda c: "—" if c == "—" else labels.get(c, c))


def _people_tab():
    try:
        users = store.list_users()
    except Exception as exc:
        st.error(f"Couldn't load people: {exc}")
        users = []

    labels = store.track_label_map()
    if users:
        st.markdown(
            '<div class="dj-people">' + "".join(
                f'<div class="dj-person"><div><b>{_html.escape(u.get("name") or "")}</b>'
                f'<span class="dj-person-u">@{_html.escape(u.get("username") or "")}</span></div>'
                f'<div>{_role_chip(u.get("role"))}'
                f'{_chip(labels.get(u.get("track_code"), u.get("track_code") or "no track"), "t")}'
                f'{_chip("active" if u.get("active", True) else "disabled", "s" if u.get("active", True) else "d")}'
                "</div></div>" for u in users) + "</div>",
            unsafe_allow_html=True)
    else:
        st.caption("No one is set up yet. Add the first person below.")

    with st.expander("Add someone"):
        with st.form("adm_add_user", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name")
            username = c2.text_input("Username", help="Lowercase, no spaces.")
            c3, c4 = st.columns(2)
            email = c3.text_input("Email (they can sign in with this too)")
            mobile = c4.text_input("Mobile (optional)")
            c5, c6 = st.columns(2)
            role = c5.selectbox("Role", config.ALL_ROLES,
                                index=config.ALL_ROLES.index(config.ROLE_TRAINER),
                                format_func=lambda r: config.ROLE_LABELS[r])
            with c6:
                track = _track_picker("Track", "adm_add_track")
            share_all = st.checkbox("May publish to all tracks", value=False)
            pwd = st.text_input("Temporary password", type="password",
                                help="They must replace it at first sign-in.")
            go = st.form_submit_button("Create account", use_container_width=True)
        if go:
            if not (name.strip() and username.strip() and len(pwd or "") >= 10):
                st.error("Name, username and a password of at least 10 characters "
                         "are required.")
            else:
                try:
                    store.create_user(
                        username=username, name=name, password=pwd, role=role,
                        track_code=None if track == "—" else track,
                        can_share_all=share_all, email=email, mobile=mobile)
                    store.log_event(auth.session().get("username"), "create_user",
                                    detail=username.strip().lower())
                    st.success(f"Created @{username.strip().lower()}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Couldn't create the account: {exc}")

    if not users:
        return
    with st.expander("Edit someone"):
        who = st.selectbox("Person", [u["username"] for u in users],
                           format_func=lambda u: next(
                               (x.get("name") or u for x in users
                                if x["username"] == u), u))
        row = next((u for u in users if u["username"] == who), {})
        with st.form("adm_edit_user"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name", value=row.get("name") or "")
            email = c2.text_input("Email", value=row.get("email") or "")
            c3, c4 = st.columns(2)
            role = c3.selectbox(
                "Role", config.ALL_ROLES,
                index=config.ALL_ROLES.index(row.get("role"))
                if row.get("role") in config.ALL_ROLES else 2,
                format_func=lambda r: config.ROLE_LABELS[r])
            with c4:
                track = _track_picker("Track", "adm_edit_track",
                                      current=row.get("track_code"))
            share_all = st.checkbox("May publish to all tracks",
                                    value=bool(row.get("can_share_all")))
            active = st.checkbox("Account active", value=bool(row.get("active", True)))
            newpwd = st.text_input("Reset password to (optional)", type="password")
            confirm = st.checkbox("I mean it — save these changes")
            go = st.form_submit_button("Save", use_container_width=True)
        if go:
            if not confirm:
                st.warning("Tick the confirm box to save.")
            else:
                fields = {"name": name, "email": email, "role": role,
                          "track_code": None if track == "—" else track,
                          "can_share_all": share_all, "active": active}
                if newpwd:
                    if len(newpwd) < 10:
                        st.error("Use at least 10 characters.")
                        return
                    fields["password"] = newpwd
                    fields["must_change_password"] = True
                try:
                    store.update_user(who, **fields)
                    store.log_event(auth.session().get("username"), "update_user",
                                    detail=who)
                    st.success("Saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Couldn't save: {exc}")


def _tracks_tab():
    try:
        tracks = store.list_tracks()
    except Exception as exc:
        st.error(f"Couldn't load tracks: {exc}")
        tracks = []

    if tracks:
        st.markdown(
            '<div class="dj-people">' + "".join(
                f'<div class="dj-person"><div><b>{_html.escape(t.get("name") or "")}</b>'
                f'<span class="dj-person-u">{_html.escape(t.get("code") or "")}</span></div>'
                f'<div>{_chip(t.get("focus") or "—", "n")}'
                f'{_chip("active" if t.get("active", True) else "archived", "s" if t.get("active", True) else "d")}'
                "</div></div>" for t in tracks) + "</div>",
            unsafe_allow_html=True)
    else:
        st.caption("No tracks in the database yet — the studio is using the "
                   "`TRACKS` setting: " + ", ".join(config.TRACKS))

    with st.form("adm_add_track", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        code = c1.text_input("Code", placeholder="VMW",
                             help="Short and permanent — it is what gets stored.")
        name = c2.text_input("Name", placeholder="VMware & Private Cloud")
        focus = st.text_input("Focus (optional)",
                              placeholder="vSphere, VCF, vSAN, NSX")
        go = st.form_submit_button("Add track", use_container_width=True)
    if go:
        if not (code.strip() and name.strip()):
            st.error("A code and a name are required.")
        else:
            try:
                store.create_track(code, name, focus)
                store.log_event(auth.session().get("username"), "create_track",
                                detail=code.strip().upper())
                st.success("Track added.")
                st.rerun()
            except Exception as exc:
                st.error(f"Couldn't add the track: {exc}")


def _requests_tab():
    try:
        reqs = store.list_access_requests(status="pending")
    except Exception as exc:
        st.error(f"Couldn't load requests: {exc}")
        return
    if not reqs:
        st.caption("No pending access requests.")
        return

    for r in reqs:
        with st.expander(f"{r.get('name')} — {r.get('email') or 'no email'}"):
            if r.get("note"):
                st.markdown(f"> {_html.escape(r['note'])}")
            with st.form(f"req::{r['id']}"):
                c1, c2 = st.columns(2)
                username = c1.text_input("Username",
                                         value=r.get("username") or "",
                                         key=f"ru::{r['id']}")
                role = c2.selectbox("Role", config.ALL_ROLES,
                                    index=config.ALL_ROLES.index(config.ROLE_TRAINER),
                                    format_func=lambda x: config.ROLE_LABELS[x],
                                    key=f"rr::{r['id']}")
                with c1:
                    track = _track_picker("Track", f"rt::{r['id']}")
                pwd = c2.text_input("Temporary password", type="password",
                                    key=f"rp::{r['id']}")
                a1, a2 = st.columns(2)
                approve = a1.form_submit_button("Approve", use_container_width=True)
                reject = a2.form_submit_button("Reject", use_container_width=True)
            actor = auth.session().get("username")
            if approve:
                if not (username.strip() and len(pwd or "") >= 10):
                    st.error("A username and a 10+ character password are required.")
                    continue
                try:
                    store.create_user(username=username, name=r.get("name") or username,
                                      password=pwd, role=role,
                                      track_code=None if track == "—" else track,
                                      email=r.get("email"))
                    store.update_access_request(r["id"], status="approved",
                                                decided_by=actor)
                    store.log_event(actor, "approve_request", detail=username)
                    st.success(f"Approved — @{username.strip().lower()} can sign in.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Couldn't approve: {exc}")
            if reject:
                try:
                    store.update_access_request(r["id"], status="rejected",
                                                decided_by=actor)
                    store.log_event(actor, "reject_request", detail=str(r["id"]))
                    st.info("Rejected.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Couldn't reject: {exc}")


def _activity_tab():
    try:
        events = store.list_events(limit=150)
    except Exception as exc:
        st.error(f"Couldn't load the activity log: {exc}")
        return
    if not events:
        st.caption("No activity recorded yet.")
        return
    header = "| When | Who | Action | Detail |\n|---|---|---|---|\n"
    body = "\n".join(
        f"| {(e.get('created_at') or '')[:16].replace('T', ' ')} "
        f"| {e.get('actor') or ''} | {e.get('action') or ''} "
        f"| {(e.get('detail') or '')[:60]} |" for e in events)
    st.markdown(header + body)
