# The ASRE Weekly Support Report

Weekly automation that compiles the support report for Amy Stockberger Real Estate agents, generates a podcast in Amy's voice, commits the result, and emails the team.

## What runs and when

- `compile.yml` runs Sundays at 11:00 UTC (6 AM Central during DST). It pulls four web sources and three Google Drive items, summarizes them with Gemini, generates the podcast through ElevenLabs, and commits `reports/reports.json` plus a new mp3 to `reports/audio/`.
- `send-email.yml` runs Sundays at 18:00 UTC (1 PM Central during DST). It reads the newest report from `reports.json`, renders the branded HTML email, and sends to the agent list through Microsoft 365 SMTP.

## Required GitHub secrets

Add these under Settings, Secrets and variables, Actions, Repository secrets.

| Secret | Where it comes from |
| --- | --- |
| `GEMINI_API_KEY` | Google AI Studio at aistudio.google.com (free tier) |
| `ELEVENLABS_API_KEY` | elevenlabs.io profile page |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Cloud Console service account key, full JSON pasted in |
| `OUTLOOK_APP_PASSWORD` | Microsoft 365 security settings, app password for amy@amystockberger.com |
| `ARTIFACT_URL` | The Claude artifact share URL agents bookmark |

The Google service account email needs viewer access on each of these:

- HST Partner Spotlight Doc
- Client Events Doc
- SF Market Stats folder
- Parent folder

IDs are hardcoded in `lib/config.py`.

## Manual reruns

Both workflows expose `workflow_dispatch`. Open the Actions tab, pick a workflow, click Run workflow.

For the email workflow there is an optional input `recipient_override`. Fill in any address and the email goes only to that recipient. Leave blank to send to the agent list.

To test compile without burning a Sunday slot, run Compile Weekly Support Report manually, then run Send Weekly Support Report Email manually with `recipient_override` set to your own address.

## Local development

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set the same env vars locally and run:

```
python compile.py
python send_email.py
```

## Failure handling

- Each source pull is wrapped in try/except. A failed source becomes a placeholder so the report still publishes.
- ElevenLabs failure sets `podcastUrl` to null. The artifact handles null.
- A total compile failure exits non-zero so the workflow shows red in the Actions tab.

## Voice and brand reminders

- Spell out Amy Stockberger Real Estate in full every time
- Use Home Support Partners, never HST or vendors alone
- Lifetime Home Support is trademarked
- Sign-off line: Serve. Serve. Serve. Sell.
