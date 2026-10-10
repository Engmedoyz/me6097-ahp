# ME6097 AHP survey (public web version)

Public survey for maintenance officers (no login) plus a private researcher page. Every response goes
into the Google Sheet **"ME6097 AHP Responses"** through a Google Apps Script web app.

| File | Purpose |
|---|---|
| `index.html` | Survey (Arabic/English, light/dark, 3D solar-plus-storage scene). Sends the answers to the Sheet; if that fails, it shows WhatsApp and the answer code instead. |
| `admin.html` | Researcher page (not linked from the survey, `noindex`). Asks for the admin key, shows the officers, group weights and CSV, adds codes pasted from WhatsApp and deletes rows. |
| `apps_script/Code.gs` | The Apps Script code to paste into the Sheet's script editor. |
| `dev/mock_server.py` | Local stand-in for the Apps Script (for testing only). |
| `dev/flow_test.py`, `dev/shots.py`, `dev/shots_extra.py` | End-to-end checks and screenshots (Playwright with installed Edge). |

`SUBMIT_URL` at the top of the script in **both** `index.html` and `admin.html` must hold the Apps Script web-app URL.

## Setting up the Google side (needs your Google account, about 10 minutes)

1. Open https://sheets.new and rename the new spreadsheet to **ME6097 AHP Responses**.
2. Menu **Extensions → Apps Script**. Delete what is in `Code.gs`, paste the whole content of
   `apps_script/Code.gs` from this folder, and press **Save** (disk icon).
3. In the function list at the top choose **setup** and press **Run**. Google asks for permission:
   *Review permissions → your account → Advanced → Go to (unsafe) → Allow* (it is your own script).
   The execution log then shows `ADMIN_KEY = ...`. That key is your password for `admin.html`.
   It is stored only in **Project Settings (gear) → Script Properties → ADMIN_KEY**; never put it in the HTML or in GitHub.
4. **Deploy → New deployment → gear → Web app**. Description: `ME6097 survey`. *Execute as:* **Me**.
   *Who has access:* **Anyone**. Press **Deploy**, then copy the **Web app URL** (ends in `/exec`).
5. Paste that URL in place of `PASTE_APPS_SCRIPT_WEB_APP_URL_HERE` in `index.html` and `admin.html`
   (or send it to Claude Code to do it and run the checks).

If you later change `Code.gs`, use **Deploy → Manage deployments → edit (pencil) → Version: New version → Deploy**
so the URL stays the same.

## Publishing on GitHub Pages

1. On github.com create a new **public** repository named `me6097-ahp` (no README).
2. In this folder:
   ```
   git remote add origin https://github.com/<your-user>/me6097-ahp.git
   git push -u origin main
   ```
3. Repository **Settings → Pages → Build and deployment → Source: Deploy from a branch → main / (root) → Save**.
   After a minute the survey is at `https://<your-user>.github.io/me6097-ahp/` and the researcher page at
   `https://<your-user>.github.io/me6097-ahp/admin.html`.

## Testing locally

```
python dev/mock_server.py          # http://localhost:8765/index.html, admin key "devkey"
python dev/flow_test.py            # 30 checks; against the real Apps Script: python dev/flow_test.py https://<user>.github.io/me6097-ahp <ADMIN_KEY>
python dev/shots.py                # screenshots into screenshots/
```
