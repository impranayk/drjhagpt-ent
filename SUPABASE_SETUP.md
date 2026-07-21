# Shared library & multi-trainer setup (Supabase)

Everything here is **optional**. Without it, DrJhaGPT Pro is a complete
single-trainer studio: every generator works, logins come from
`.streamlit/auth.yaml`, and the Library and Admin Console simply don't appear.

Turn it on when you want:

- more than one person using the studio, with roles and per-track access,
- a **shared library** so material published by one trainer is available to the
  others on their track,
- self-serve **access requests** that you approve from the Admin Console,
- an **audit log** of who generated, published and changed what.

It takes about ten minutes and costs nothing on Supabase's free tier.

---

## 1. Create the project

1. Sign up at <https://supabase.com> and create a project (pick a region near
   you — `ap-south-1` if you're in India).
2. Wait for it to finish provisioning.

## 2. Run the SQL

Open **SQL Editor → New query**, paste all of this, and run it.

```sql
-- Tracks: the practice a trainer belongs to, and the unit material is shared to.
create table if not exists tracks (
  code        text primary key,
  name        text not null,
  focus       text,
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);

-- People. `password_hash` is a bcrypt hash written by the app - never a password.
create table if not exists app_users (
  username              text primary key,
  name                  text not null,
  password_hash         text not null,
  role                  text not null default 'trainer',
  track_code            text references tracks(code),
  can_share_all         boolean not null default false,
  active                boolean not null default true,
  email                 text,
  mobile                text,
  photo                 text,
  auth_sub              text,
  allowed_tools         jsonb,
  allowed_models        jsonb,
  must_change_password  boolean not null default true,
  created_at            timestamptz not null default now()
);
create unique index if not exists app_users_email_key
  on app_users (lower(email)) where email is not null;

-- The shared library of published material.
create table if not exists library (
  id               bigserial primary key,
  created_at       timestamptz not null default now(),
  author           text not null,
  tool             text not null,
  title            text not null,
  content_md       text not null,
  tracks           jsonb not null default '[]'::jsonb,
  course           text,
  cohort           text,
  tech_area        text,
  product_version  text,
  tags             text,
  attachment_url   text,
  meeting          text,
  status           text not null default 'published'
);
create index if not exists library_created_idx on library (created_at desc);

-- Self-serve access requests, reviewed in the Admin Console.
create table if not exists access_requests (
  id          bigserial primary key,
  created_at  timestamptz not null default now(),
  name        text not null,
  email       text,
  username    text,
  role        text,
  track_code  text,
  note        text,
  status      text not null default 'pending',
  decided_by  text,
  decided_at  timestamptz
);

-- Audit log.
create table if not exists events (
  id          bigserial primary key,
  created_at  timestamptz not null default now(),
  actor       text not null,
  action      text not null,
  detail      text,
  track       text
);
create index if not exists events_created_idx on events (created_at desc);

-- The app talks to PostgREST with the service_role key, which bypasses RLS.
-- RLS is still enabled so that a leaked anon/publishable key reads nothing.
alter table tracks           enable row level security;
alter table app_users        enable row level security;
alter table library          enable row level security;
alter table access_requests  enable row level security;
alter table events           enable row level security;

-- Seed your tracks (edit to match how you actually organise your training).
insert into tracks (code, name, focus) values
  ('VMW', 'VMware & Private Cloud', 'vSphere, VCF, vSAN, NSX'),
  ('CLD', 'Public Cloud',           'AWS, Azure, GCP'),
  ('K8S', 'Kubernetes & Containers','Kubernetes, OpenShift, Docker'),
  ('AUT', 'Automation & DevOps',    'Terraform, Ansible, PowerCLI, CI/CD'),
  ('AIX', 'AI Infrastructure',      'GPU sizing, Private AI, RAG platforms')
on conflict (code) do nothing;
```

## 3. Add the secrets

**Project Settings → API**, then copy:

- the **Project URL** → `SUPABASE_URL`
- the **`service_role`** key (the secret one, not `anon`) → `SUPABASE_KEY`

Add both to the Streamlit app's **Settings → Secrets** (and to your local `.env`
if you run it on your machine):

```toml
SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
SUPABASE_KEY = "sb_secret_..."
ADMIN_USERS  = "pranay"
```

> The `service_role` key can read and write everything. It belongs only in
> server-side secrets — never in a repo, a URL, or anything sent to a browser.

Reboot the app. The sidebar **Status** panel should now show
`Shared library — connected`.

## 4. Bootstrap yourself as admin

`ADMIN_USERS` (default `pranay`) is the bootstrap: whoever signs in with that
username is treated as an admin regardless of what the database says, so you can
never lock yourself out.

1. Sign in with the account in `.streamlit/auth.yaml`, or add yourself there
   first (`python scripts/make_hash.py "your-password"` generates the hash).
2. Open **Admin Console → People → Add someone** and create your real account
   with role **Admin**.
3. Add your co-trainers. Each gets a temporary password they must replace at
   first sign-in.

## 5. Optional — file attachments

To attach files to published material, create a **public** storage bucket named
`studio` (Storage → New bucket → name `studio`, Public ✓). Without it,
publishing still works; the attachment is skipped with a warning.

## 6. Optional — post articles to drpranayjha.com

If you want the **Article Draft** tool to be able to create a *draft* WordPress
post directly, set:

```toml
WEBSITE_POST_URL   = "https://drpranayjha.com/wp-json/drjhagpt/v1/post"
WEBSITE_POST_TOKEN = "a-long-random-string"
```

The endpoint must accept `{title, content, category, status}` and authenticate on
the `?token=` query parameter. With these unset, the option doesn't appear.

---

## Roles

| Role | Tools | Publishing | Admin Console |
|---|---|---|---|
| **Admin** | everything | all tracks | yes |
| **Lead Trainer** | everything | all tracks | no |
| **Trainer** | everything except Course Outline and Study Plan | own track | no |
| **Associate** | as Trainer, minus Article Draft | own track | no |

Per-user `allowed_tools` and `allowed_models` (set in the database) override
these defaults for one person without changing their role.

## Troubleshooting

**"Couldn't reach the library"** — check `SUPABASE_URL` for a typo. It is easy to
transpose characters in the project ref, and a wrong host fails exactly like a
network error.

**Everything reads empty but writes appear to work** — you're using the `anon`
key. RLS blocks it. Use `service_role`.

**A free-tier project pauses after inactivity** — Supabase pauses projects with
no traffic for a week. A daily ping (cron-job.org against the REST endpoint) keeps
it awake.
