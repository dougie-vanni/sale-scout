# SaleScout

Daily sweep of trad/Ivy menswear retailers for sale items in your size,
style-scored by Claude, with AUD landed cost. Free to run.

Three free services do the work:
- **Supabase** — the database holding items and your verdicts
- **GitHub** — stores the code, runs the daily sweep, hosts the web app
- **Anthropic API** — style-scores items (optional, ~$1–3/month)

Follow the steps in order. ~30 minutes total.

---

## STEP 1 — Supabase (the database)

1. Go to https://supabase.com → **Start your project** → sign up (GitHub
   login is easiest since you'll need a GitHub account anyway).
2. Click **New project**. Name: `salescout`. Set any database password
   (you won't need it again). Region: Sydney. Click **Create new project**
   and wait ~2 minutes for it to provision.
3. In the left sidebar click the **SQL Editor** icon (looks like a page
   with `>_` on it).
4. Click **New query**, paste ALL of the SQL below into the box, then
   click **Run** (bottom right). You should see "Success. No rows returned".

```sql
create table items (
  item_key text primary key,
  retailer_id text not null,
  retailer_name text,
  region text,
  category text,
  title text,
  vendor text,
  variant_title text,
  currency text,
  price numeric,
  compare_at numeric,
  discount_pct numeric,
  url text,
  image text,
  price_aud numeric,
  shipping_aud numeric,
  gst_aud numeric,
  landed_aud numeric,
  landed_full_aud numeric,
  landed_discount_pct numeric,
  score int,
  score_reason text,
  status text not null default 'new',
  created_at timestamptz default now()
);

create table muted_retailers (
  retailer_id text primary key,
  created_at timestamptz default now()
);

alter table items enable row level security;
alter table muted_retailers enable row level security;

create policy "read items" on items for select using (true);
create policy "update status" on items for update using (true)
  with check (status in ('new','approved','rejected','too_expensive'));
create policy "read muted" on muted_retailers for select using (true);
create policy "add muted" on muted_retailers for insert with check (true);
```

5. Now collect three values. Left sidebar → **Project Settings** (gear
   icon) → **API** (under "Configuration"). Copy these somewhere temporary,
   like a notes app:
   - **Project URL** — looks like `https://abcdefgh.supabase.co`
   - **anon public** key — long string starting `eyJ...`
   - **service_role** key — click "Reveal" to see it. Also starts `eyJ...`.
     This one is secret; it only ever goes into GitHub secrets, never the
     web app.

Supabase is done. You never need to touch it again.

---

## STEP 2 — Put the code on GitHub

1. Go to https://github.com → sign up if you haven't.
2. Top right **+** → **New repository**. Name: `sale-scout`. Set it to
   **Private**. Do NOT tick "Add a README". Click **Create repository**.
3. Get the code in. Easiest way without installing anything:
   - On the empty-repo page, click the **"uploading an existing file"** link.
   - Unzip `sale-scout.zip` on your computer. Open the unzipped
     `sale-scout` folder.
   - Drag its CONTENTS (the `config`, `scout`, `docs`, `.github` folders
     and the loose files — not the `sale-scout` folder itself) into the
     GitHub upload box.
   - **Catch:** browsers often skip the hidden `.github` folder when
     dragging. After uploading, check the repo file list. If `.github` is
     missing: click **Add file → Create new file**, type
     `.github/workflows/daily.yml` as the filename (the slashes create the
     folders), paste in the contents of that file from your unzipped copy,
     and click **Commit changes**.
   - Click **Commit changes** on the upload page itself too.

   (If you install Claude Code or already use git, `git init`, commit, and
   push instead — but the drag-and-drop works fine.)

---

## STEP 3 — Give GitHub the keys (secrets)

1. In your repo: **Settings** tab → left sidebar **Secrets and variables**
   → **Actions**.
2. Click **New repository secret**. Add these three, one at a time
   (Name exactly as written, Value from your notes):

   | Name                   | Value                                  |
   |------------------------|----------------------------------------|
   | `SUPABASE_URL`         | your Project URL from step 1.5         |
   | `SUPABASE_SERVICE_KEY` | the service_role key from step 1.5     |
   | `ANTHROPIC_API_KEY`    | see below                              |

3. For the Anthropic key: go to https://console.anthropic.com → sign up →
   **API keys** → **Create key** → copy it (starts `sk-ant-`). New accounts
   get US$5 free credit, which runs this for a month or two. You can skip
   this secret entirely; the sweep still works, just with dumber filtering.

---

## STEP 4 — Test the retailer feeds (probe)

1. In your repo click the **Actions** tab. If it asks you to enable
   workflows, click the green enable button.
2. Left sidebar → **daily-sweep** → right side **Run workflow** dropdown →
   tick **"Run feed probe instead of the sweep"** → green **Run workflow**
   button.
3. Wait ~1 minute, click the run that appears, click **sweep**, expand
   **Probe feeds**. You'll see a line per retailer: `OK` means it works,
   anything else means cull it or fix the URL.
4. To disable a dead retailer: in the repo go to
   `config/retailers.json`, click the pencil icon (Edit), change that
   retailer's `"enabled": true` to `false`, **Commit changes**. (All config
   editing works this way — no software needed.)

---

## STEP 5 — The web app

1. In the repo, open `docs/index.html` and click the pencil to edit.
   Near the top find:
   ```
   const SUPABASE_URL = 'https://YOUR-PROJECT.supabase.co';
   const SUPABASE_ANON_KEY = 'YOUR-ANON-KEY';
   ```
   Replace with your Project URL and the **anon** key (NOT service_role).
   Commit changes.
2. **Settings** tab → **Pages** (left sidebar) → under "Build and
   deployment": Source = **Deploy from a branch**, Branch = **main**,
   folder = **/docs** → **Save**.
3. Wait 2–3 minutes. The page will show your URL, like
   `https://yourname.github.io/sale-scout/`. Open it — you should see the
   SaleScout header and "Nothing new today".
4. On your phone, open that URL and add it to your home screen.

Note: with a private repo, the Pages site itself is still publicly
reachable by anyone who guesses the URL. It only exposes sale listings and
your verdicts, nothing sensitive, but if that bothers you the fix is a
Supabase login layer (a later upgrade).

---

## STEP 6 — First sweep

Actions tab → daily-sweep → Run workflow → leave the probe box UNTICKED →
Run. This first one is the big one: it scores the entire current sale
backlog (a few minutes, maybe US$0.50–1 of API credit). When it finishes,
refresh your web app. From now on it runs itself every morning at 6am AEST
and only scores genuinely new items (cents per day).

---

## Daily use

Open the web app. For each card:
- **Want it** → moves to Saved tab (and you go buy it)
- **Pass** → never see it again
- **Cheaper** → hidden until that exact item drops a further 5%+
- **Mute [shop]** → that retailer is skipped in all future sweeps

## Tuning

- Sizes, colours, thresholds, the style brief Claude scores against:
  edit `config/preferences.json` in GitHub.
  **The shoe sizes are placeholders — fix them before trusting shoe alerts.**
- Add a retailer: append an entry to `config/retailers.json`. Any Shopify
  store works with `"type": "shopify"`. Re-run the probe to check.
- O'Connell's, Brooks Brothers, J.Press, Kamakura, BEAMS, END., Mercer are
  stubbed (`"type": "custom", "enabled": false`) pending custom scrapers.

## If something breaks

Actions tab → click the failed run → read the log. The most common issues:
a retailer changed platforms (disable it), or a secret was pasted with a
trailing space (re-create it).
