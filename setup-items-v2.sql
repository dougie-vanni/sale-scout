-- Run in Supabase SQL Editor

-- 1. Add vintage flag to items (existing rows default to false)
alter table items add column if not exists vintage boolean default false;

-- 2. Allow 'purchased' status (for "Bought it" button on Saved tab)
drop policy if exists "update status" on items;
create policy "update status" on items for update using (true)
  with check (status in ('new','approved','rejected','too_expensive','purchased'));

-- 3. Add eBay AU retailer (run after adding EBAY_APP_ID + EBAY_CERT_ID as GitHub secrets)
insert into retailers (id, name, base_url, type, enabled, region, currency, shipping_aud, vintage, marketplace, ebay_keywords, ebay_sizes)
values (
  'ebay_au', 'eBay AU', '', 'ebay', true, 'AU', 'AUD', 0, true,
  'EBAY_AU',
  'polo ralph lauren brooks brothers j press pendleton woolrich lacoste izod lands end',
  'L,Large,XL,X-Large'
)
on conflict (id) do update set
  enabled = excluded.enabled,
  ebay_keywords = excluded.ebay_keywords,
  ebay_sizes = excluded.ebay_sizes;

-- Add eBay-specific columns to retailers table if not already present
alter table retailers add column if not exists marketplace text;
alter table retailers add column if not exists ebay_keywords text;
alter table retailers add column if not exists ebay_sizes text;
