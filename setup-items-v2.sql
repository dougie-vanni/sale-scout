-- Run in Supabase SQL Editor

-- 1. Add vintage flag to items (existing rows default to false)
alter table items add column if not exists vintage boolean default false;

-- 2. Allow 'purchased' status (for "Bought it" button on Saved tab)
drop policy if exists "update status" on items;
create policy "update status" on items for update using (true)
  with check (status in ('new','approved','rejected','too_expensive','purchased'));
