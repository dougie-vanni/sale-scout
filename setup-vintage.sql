-- Run this in the Supabase SQL Editor
-- Adds vintage support and new retailers

-- 1. Add vintage column to retailers table
alter table retailers add column if not exists vintage boolean default false;

-- 2. Add regular AU retailers
insert into retailers (id, name, base_url, type, enabled, region, currency, shipping_aud, vintage)
values
  ('providence', 'Providence Clothing Co', 'https://providenceclothingco.com.au', 'shopify', true, 'AU', 'AUD', 10, false),
  ('styleroom',  'Styleroom',              'https://www.styleroom.com.au',         'shopify', true, 'AU', 'AUD', 10, false)
on conflict (id) do update set
  name = excluded.name,
  base_url = excluded.base_url,
  enabled = excluded.enabled,
  vintage = excluded.vintage;

-- 3. Add vintage AU retailers
insert into retailers (id, name, base_url, type, enabled, region, currency, shipping_aud, vintage, vendor_allow)
values
  ('vintagemarketplace', 'Vintage Marketplace', 'https://vintagemarketplace.com.au', 'shopify', true, 'AU', 'AUD', 10, true,
   'polo ralph lauren, ralph lauren, tommy hilfiger, brooks brothers, lacoste, pendleton, woolrich, izod, j.crew'),
  ('midwesttrader', 'Midwest Trader', 'https://midwesttrader.shop', 'shopify', true, 'AU', 'AUD', 10, true, null),
  ('retrostar', 'RetroStar', 'https://retrostar.com.au', 'shopify', true, 'AU', 'AUD', 10, true,
   'polo ralph lauren, ralph lauren, tommy hilfiger, brooks brothers, lacoste, pendleton, woolrich, izod, j.crew, lands end, l.l. bean')
on conflict (id) do update set
  name = excluded.name,
  base_url = excluded.base_url,
  enabled = excluded.enabled,
  vintage = excluded.vintage,
  vendor_allow = excluded.vendor_allow;
