# Meeting Metrics - SHPE UCI

A Flask dashboard that pulls attendance data from Google Sheets and turns it into charts that board members can actually use. Built for the Society of Hispanic Professional Engineers chapter at UC Irvine.

**Live Demo:**[YOUR_DEPLOY_URL_HERE]

**Video walkthrough:** [YOUR_VIDEO_URL_HERE]

**Public Demo Data:** The deployed version reads from a mock Google Drive folder, **NOT** real member data. However, the mock data is modeled on real attendance patterns shared by the current SHPE UCI president (as of September 12, 2026).

---

## Why this exists

SHPE UCI collects attendance at every general meeting through Google forms. That data has always existed, the biggest issue was that it was not usable. Every time an officer needed a metric (year distribution for a sponsorship packet, major breakdowns for outreach planning, attendance trends for board updates to see what was working), someone had to open five spreadsheets, and count rows by hand or manually move all the data in meeting order. I first built a rough version of this tool in Streamlit while I was Executive Affairs Intern in 2024 - 2025. It worked and got the job done, of being able to be used for the sponsorship packet. But it looked more like a makeshift script that was just put together (because it was one), and I wanted something that the club could keep using after my term ended, and where it was nice and easy to use. So I rewrote it as a proper full-stack application: Flask was on the backend, and JavaScript + Chart.js on the frontend, with the entire pipeline being around real-world data quirks. Some examples are like inconsistent column names across sheets, freshman vs "First Year" vs "1st year" or whatever other people could type or choose. The old Streamlit version is still in `archive/streamlit_version.py` for reference.

## What does it do

**Pulls attendance from Google Drive** 

The idea was that a service account can read from a Google Drive folder that is structured in `Year -> Quarter -> Meeting spreadsheets.` The program recurses through subfolders, handles the "General Meetings" wrapper folder that some quarters use.

**Normalizes messy sign-in data.**

Column names vary like ("Year" / "grade level" / "class standing"). So do values like ("freshman" / "First Year" / "1st year"). And majors have their own category of abbreviations. All of it gets mapped to a canonical form before anything is even charted.

**Renders three views of the data.**

Year Distribution (bar / pie / horizontal), Major distribution (same), and an Attendance Trend line chart across the quarter. In quarter-view the trend chart shows the shape of the whole quarter. In the single meeting view, the selected meeting's dot is highlighted so you can see instantly where it sits relative to the rest.

**Progressive disclosure in the side bar**

The application makes it impossible to generate charts if a color or a meeting is not selected, this way the progression is to select a Year -> Quarter -> Scope -> Color Palette. Each step unlocks the next.

**A public demo mode**

So this repo is showable without exposing real member data, Point `ROOT_FOLDER_ID` at a mock drive folder and everything works with artifical attendance numbers.


## Tech Stack

**Backend**

- Python 3.11+
- Flask (web server + JSON API)
- Pandas (data normalization)
- google-api-python-client (Drive + Sheets access)
- Python-dotenv (config)

**Frontend**
- JavaScript (no framework)
- Chart.js 4 (charts) + chartjs-plugin-datalabels
- HTML / CSS with a small design system (SHPE blue palette + Inter/JetBrains Mono)

**Auth**
- Google service account with read-only scopes on Drive + Sheets

## Running it locally

**1. Clone and install dependencies:**
```bash
git clone https://github.com/ChristianRaya1221/meeting-metrics.git
cd meeting-metrics
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**2. Get a Google service account:**

Create a project in [Google Cloud Console](https://console.cloud.google.com/), enable the Drive API and Sheets API, create a service account, download its JSON key, and save it as `service_account.json` in the project root. (It's `.gitignore`'d — don't commit it.)

**3. Set up a Drive folder:**

Structure it like this:

    Your Root Directory Folder (share this with your service account email)
    └── SHPE 2024-2025
    ├── Fall
    │    ├── Meeting 1 (Google Sheet)
    │    ├── Meeting 2 (Google Sheet)
    ├── Winter
    └── Spring

For each Meeting Sheet needs at minimum a `Year` column and/or a `Major` column. The parser also accepts aliases: `grade level`, `class standing`, `academic year`, `field of study`, `department`, etc.

Share the top level folder with your service account email, which should be found in `service_account.json` under `client_email`, Viewer access is enough.

**4. Configure `.env`:**

Copy `.env.example` to `.env` and fill in:

ROOT_FOLDER_ID=your-drive-folder-id-here
FLASK_DEBUG=false

The folder ID is the string after `/folders/` in your Drive folder's URL.

**5. Run it:**

```bash
python server.py
```

Open `http://127.0.0.1:5000` in your browser.

## Project structure

    meeting-metrics/
    ├── server.py # Flask entry point, routes, /api/* endpoints
    ├── backend.py # Google API integration, data normalization
    ├── test_connection.py # Diagnostic script for service account setup
    ├── templates/
    │       └── index.html # Main dashboard UI
    ├── static/
    │       ├── app.js # Frontend logic (state, fetching, rendering)
    │       ├── style.css # Design system + component styles
    │       └── img/
    │            └── shpe_loader.gif
    ├── archive/
    │       └── streamlit_version.py # Original Streamlit prototype, kept for history
    ├── requirements.txt
    ├── .env.example
    └── .gitignore

## Roadmap

These were not commitments but just things I've thought through but scoped out of version 1:

- **Custom spreadsheet upload.** A column-mapping UI so any club (not just SHPE) could bring their own attendance data.
- **Cross-quarter deltas.** Green/red arrows on stat cards comparing the current period against the previous one. Requires a name-normalization pass to reconcile members across sheets, lot of work, but worth doing carefully.
- **Longitudinal trends view.** Attendance across many quarters as a long timeline, not just within one.
- **Landing page with more project context** for visitors coming from the hosted demo.

## Notes

Built solo. Not currently open-sourced under a license, the code is visible for portfolio purposes but not licensed for reuse. If you're an org that would find this useful, reach out.

Author: Christian F. Raya · [GitHub](https://github.com/ChristianRaya1221)

