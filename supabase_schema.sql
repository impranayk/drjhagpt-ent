-- DrJhaGPT Pro - studio schema for Supabase.
--
-- Paste this whole file into the Supabase SQL Editor and run it once.
-- Walkthrough and troubleshooting: SUPABASE_SETUP.md
--
-- Every table is prefixed `dj_` on purpose. Names like `app_users`, `events`
-- and `access_requests` are exactly what another app would also choose - and
-- `create table if not exists` against an existing one silently does nothing,
-- which would leave two apps reading each other's people. The prefix means this
-- app can safely share a Supabase project with another one. If you change
-- DB_PREFIX in the app config, change these names to match.

-- Tracks: the practice a trainer belongs to, and the unit material is shared to.
create table if not exists dj_tracks (
  code        text primary key,
  name        text not null,
  focus       text,
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);

-- People. `password_hash` is a bcrypt hash written by the app - never a password.
create table if not exists dj_app_users (
  username              text primary key,
  name                  text not null,
  password_hash         text not null,
  role                  text not null default 'trainer',
  track_code            text references dj_tracks(code),
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
create unique index if not exists dj_app_users_email_key
  on dj_app_users (lower(email)) where email is not null;

-- The shared library of published material.
create table if not exists dj_library (
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
create index if not exists dj_library_created_idx on dj_library (created_at desc);

-- Self-serve access requests, reviewed in the Admin Console.
create table if not exists dj_access_requests (
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
create table if not exists dj_events (
  id          bigserial primary key,
  created_at  timestamptz not null default now(),
  actor       text not null,
  action      text not null,
  detail      text,
  track       text
);
create index if not exists dj_events_created_idx on dj_events (created_at desc);

-- The app talks to PostgREST with the secret (service_role) key, which bypasses
-- RLS. RLS is still enabled so a leaked publishable/anon key reads nothing.
alter table dj_tracks           enable row level security;
alter table dj_app_users        enable row level security;
alter table dj_library          enable row level security;
alter table dj_access_requests  enable row level security;
alter table dj_events           enable row level security;

-- Tracks. Edit these to match how you actually organise your training.
insert into dj_tracks (code, name, focus) values
  ('VMW', 'VMware & Private Cloud',  'vSphere, VCF, vSAN, NSX'),
  ('CLD', 'Public Cloud',            'AWS, Azure, GCP'),
  ('K8S', 'Kubernetes & Containers', 'Kubernetes, OpenShift, Docker'),
  ('AUT', 'Automation & DevOps',     'Terraform, Ansible, PowerCLI, CI/CD'),
  ('AIX', 'AI Infrastructure',       'GPU sizing, Private AI, RAG platforms')
on conflict (code) do nothing;


-- ---------------------------------------------------------------------------
-- Your admin account.
--
-- Generate the hash on your own machine so the password never travels:
--     python scripts/make_hash.py "the-password-you-want"
--
-- Paste the output in place of PASTE_HASH_HERE, uncomment, and run. After this
-- you can sign in and manage everyone else from the Admin Console instead.
--
-- must_change_password is false because you chose this password yourself.
-- ---------------------------------------------------------------------------
-- insert into dj_app_users
--   (username, name, password_hash, role, track_code, can_share_all,
--    email, must_change_password)
-- values
--   ('pranay', 'Dr. Pranay Jha', 'PASTE_HASH_HERE', 'admin', 'VMW', true,
--    'contact@drpranayjha.com', false)
-- on conflict (username) do update
--   set password_hash = excluded.password_hash,
--       role          = 'admin',
--       active        = true;
