-- Run this in Supabase Dashboard -> SQL Editor -> New query -> Run.
create table if not exists public.articles (
  article_id text primary key,
  title text not null,
  link text not null,
  source text,
  published_at text,
  summary text,
  category text,
  fetched_at timestamptz not null default now()
);

create table if not exists public.saved_articles (
  article_id text primary key references public.articles(article_id) on delete cascade,
  saved_at timestamptz not null default now()
);

alter table public.articles enable row level security;
alter table public.saved_articles enable row level security;

-- Starter policy for a personal demo app using the anon/publishable key.
-- WARNING: this allows public read/write to the shared tables. Use only for a public demo
-- with non-sensitive data. For private multi-user bookmarks, add Supabase Auth and user_id RLS.
drop policy if exists "Public can read articles" on public.articles;
create policy "Public can read articles" on public.articles for select to anon, authenticated using (true);

drop policy if exists "Public can insert articles" on public.articles;
create policy "Public can insert articles" on public.articles for insert to anon, authenticated with check (true);

drop policy if exists "Public can update articles" on public.articles;
create policy "Public can update articles" on public.articles for update to anon, authenticated using (true) with check (true);

drop policy if exists "Public can read saved articles" on public.saved_articles;
create policy "Public can read saved articles" on public.saved_articles for select to anon, authenticated using (true);

drop policy if exists "Public can save articles" on public.saved_articles;
create policy "Public can save articles" on public.saved_articles for insert to anon, authenticated with check (true);

drop policy if exists "Public can remove saved articles" on public.saved_articles;
create policy "Public can remove saved articles" on public.saved_articles for delete to anon, authenticated using (true);
