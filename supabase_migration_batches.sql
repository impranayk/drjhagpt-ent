-- DrJhaGPT Pro - migration: batches, per-person sharing, session links.
--
-- Run this ONCE in the Supabase SQL Editor, after supabase_schema.sql.
-- Safe to re-run: every statement is guarded.
--
-- What it adds:
--   * dj_batches         - course batches with an auto-generated code
--                          (CATEGORY-YYMM-NN, e.g. VMW-2607-01)
--   * dj_library.people      - share an item with named people
--   * dj_library.batch_code  - share an item with everyone on a batch
--   * dj_library.video_url   - recording / YouTube links (one per line)
--   (dj_library.meeting already exists and now carries the meeting invite JSON)

create table if not exists dj_batches (
  code        text primary key,
  name        text not null,
  track_code  text references dj_tracks(code),
  course      text,
  trainer     text,
  starts_on   date,
  ends_on     date,
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);
create index if not exists dj_batches_track_idx on dj_batches (track_code);

alter table dj_library add column if not exists people      jsonb default '[]'::jsonb;
alter table dj_library add column if not exists batch_code  text;
alter table dj_library add column if not exists video_url   text;

create index if not exists dj_library_batch_idx on dj_library (batch_code);

alter table dj_batches enable row level security;
