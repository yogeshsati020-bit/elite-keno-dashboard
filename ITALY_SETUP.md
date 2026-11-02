# Italy 10eLotto 20/90 dashboard

Dashboard path: `/italy/`

## Automatic import setup

The scheduled importer uses the Lottevo API for game code `IT-012`. The API requires an account key with the `draws:read` scope and entitlement to `IT-012`. The provider's documentation says its free trial excludes games drawn every 30 minutes or more often, so the 5-minute game may require a paid plan.

1. Create a Lottevo API key with `draws:read` and the `IT-012` game entitlement.
2. In this GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Set the secret name to `LOTTEVO_API_KEY` and paste the key as its value. Never put the key in HTML, source files, issues, or chat.
4. Open **Actions** and enable workflows if GitHub asks.
5. Run **Italy 10eLotto 20/90 automatic import** once with **Run workflow** to test the key.
6. Enable GitHub Pages for this repository if it is not already enabled: **Settings → Pages → Deploy from a branch → main → /(root)**.

The workflow checks every five minutes (GitHub scheduled runs can be delayed). It fetches the latest 25 API records, accepts only game `IT-012` with exactly 20 distinct integer numbers from 1 to 90 and a timezone-aware draw timestamp, then merges without duplicate IDs. It does not fabricate records. Existing draw history is retained up to the newest 5,000 draws.

The dashboard reads `data/italy-draws.json` and refreshes its view every five minutes. If the API key is missing, expired, lacks entitlement, or the API is unavailable, the workflow fails without changing stored draw data.

## Data source

Primary source remains the official Lotto Italia results page. The scheduled machine-readable fallback is Lottevo's authenticated API. This is a third-party data provider, not the lottery operator.
