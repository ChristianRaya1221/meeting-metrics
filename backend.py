from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_httplib2 import AuthorizedHttp
import os
from dotenv import load_dotenv
load_dotenv()

import httplib2
import random
import re
import socket
import ssl
import threading
import time
import pandas as pd


# -------- Drive/API Setup --------------
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

ALIASES = {
    "year": ["grade level", "grade", "year", "academic year", "class standing", "standing"],
    "gender": ["gender", "gender identity", "what is your gender", "pronouns"],
    "major": ["major", "major/department", "what is your major", "field of study", "department"],
}

YEAR_ORDER = {
    "First Year": 1,
    "Second Year": 2,
    "Third Year": 3,
    "Fourth Year": 4,
    "Fifth Year": 5,
    "Transfer Student": 6,
    "(blank)": 99,
}

TERM_ORDER = {
    "fall": 1,
    "winter": 2,
    "spring": 3,
    "summer": 4,
}

_google_lock = threading.RLock()
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


def execute_with_retries(request, max_attempts: int = 6):
    last_err = None

    for attempt in range(1, max_attempts + 1):
        try:
            return request.execute()

        except (ssl.SSLEOFError, ssl.SSLError, OSError) as e:
            last_err = e
        except (socket.timeout, ConnectionResetError, ConnectionAbortedError) as e:
            last_err = e
        except httplib2.ServerNotFoundError as e:
            last_err = e
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in RETRYABLE_HTTP_STATUS:
                last_err = e
            else:
                raise  # non-retryable

        if attempt == max_attempts:
            raise last_err

        time.sleep((2 ** (attempt - 1)) + random.random())


def get_services():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    # fresh transport (helps prevent stale SSL connections)
    authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=60))

    drive = build("drive", "v3", http=authed_http, cache_discovery=False)
    sheets = build("sheets", "v4", http=authed_http, cache_discovery=False)
    return drive, sheets


def list_folders(drive, parent_folder_id: str):
    query = (
        f"'{parent_folder_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    out, page_token = [], None
    while True:
        with _google_lock:
            resp = execute_with_retries(
                drive.files().list(
                    q=query,
                    fields="nextPageToken, files(id,name)",
                    pageToken=page_token,
                )
            )

        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return sorted(out, key=lambda x: x["name"].lower())


def list_sheets(drive, parent_folder_id: str):
    query = (
        f"'{parent_folder_id}' in parents and "
        "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    )
    out, page_token = [], None
    while True:
        with _google_lock:
            resp = execute_with_retries(
                drive.files().list(
                    q=query,
                    fields="nextPageToken, files(id,name)",
                    pageToken=page_token,
                )
            )

        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return out


def find_sheets_recursive(drive, folder_id: str):
    found = []
    found.extend(list_sheets(drive, folder_id))
    for sub in list_folders(drive, folder_id):
        found.extend(find_sheets_recursive(drive, sub["id"]))
    return found


def find_general_meetings_folder(folders):
    targets_exact = {"general meeting", "general meetings", "gm"}

    for f in folders:
        name = f["name"].strip().lower()

        if name in targets_exact:
            return f
        if "general meeting" in name:
            return f
        if "gm" == name or " gm " in f" {name} ":
            return f

    return None


def meeting_sort_key(name: str):
    name = name.lower()
    m = re.search(r"weeks\s*(\d+)", name)
    if m:
        return (0, int(m.group(1)))

    order_map = {
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
        "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    }
    for word, num in order_map.items():
        if word in name:
            return (1, num)

    return (2, 999, name)


def sort_year(folder_name: str):
    s = folder_name.lower()
    m = re.search(r"(\d{4})(?:\s*[-–]\s*(\d{4}))?", s)
    if not m:
        return (9999, folder_name.lower())

    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    return (-start, -end, folder_name.lower())


def term_sort_key(folder_name: str):
    t = folder_name.strip().lower()
    return (TERM_ORDER.get(t, 99), t)


def normalize_text(s: str):
    return (s or "").strip().lower()


def normalize_year(val: str) -> str:
    v = normalize_text(val)
    mapping = {
        "first year": "First Year", "1st year": "First Year", "year 1": "First Year", "freshman": "First Year",
        "second year": "Second Year", "2nd year": "Second Year", "year 2": "Second Year", "sophomore": "Second Year",
        "third year": "Third Year", "3rd year": "Third Year", "year 3": "Third Year", "junior": "Third Year",
        "fourth year": "Fourth Year", "4th year": "Fourth Year", "year 4": "Fourth Year", "senior": "Fourth Year",
        "fifth year": "Fifth Year", "5th year": "Fifth Year", "year 5": "Fifth Year",
        "transfer student": "Transfer Student", "transfer": "Transfer Student",
    }
    if v == "":
        return "(blank)"
    return mapping.get(v, val.strip())


def normalize_gender(val: str) -> str:
    v = normalize_text(val)
    mapping = {
        "male": "Male", "m": "Male", "man": "Male",
        "female": "Female", "f": "Female", "woman": "Female",
        "nonbinary": "Non-binary", "non-binary": "Non-binary",
        "prefer not to say": "Prefer not to say",
    }
    if v == "":
        return "(blank)"
    return mapping.get(v, val.strip())


def normalize_major(val: str) -> str:
    raw = (val or "").strip()
    if raw == "":
        return "(blank)"

    v = " ".join(raw.split())
    v_low = v.lower()

    major_map = {
        "cs": "Computer Science",
        "computer science": "Computer Science",
        "cse": "Computer Science Engineering",
        "computer science engineering": "Computer Science Engineering",
        "computer engineering": "Computer Science Engineering",
        "swe": "Software Engineering",
        "software engineering": "Software Engineering",
        "biosci": "Biological Sciences",
        "bio sci": "Biological Sciences",
        "civil": "Civil Engineering",
        "meche": "Mechanical Engineering",
        "pharmsci": "Pharmaceutical Sciences",
        "pharm sci": "Pharmaceutical Sciences",
        "quant econ": "Quantitative Economics",
        "quant economics": "Quantitative Economics",
    }

    if v_low in major_map:
        return major_map[v_low]

    return v.title()


def first_tab_name(sheets, spreadsheet_id: str):
    with _google_lock:
        meta = execute_with_retries(
            sheets.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets(properties(title))",
            )
        )
    return meta["sheets"][0]["properties"]["title"]


def find_column(header, keywords):
    for col in header:
        col_norm = normalize_text(col)
        for kw in keywords:
            if kw in col_norm:
                return col
    return None


def sheet_values(sheets, spreadsheet_id: str):
    with _google_lock:
        tab = first_tab_name(sheets, spreadsheet_id)
        resp = execute_with_retries(
            sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{tab}!A:ZZ",
            )
        )
    return resp.get("values", [])


def values_to_dataframe(values: list):
    if not values or len(values) < 2:
        return pd.DataFrame()

    header = values[0]
    rows = values[1:]

    width = len(header)
    rows = [r + [""] * (width - len(r)) for r in rows]

    return pd.DataFrame(rows, columns=header)


def standardized_dataframe_for_sheet(sheets, file):
    values = sheet_values(sheets, file["id"])
    data_frame_raw = values_to_dataframe(values)
    if data_frame_raw.empty:
        return pd.DataFrame()

    header = list(data_frame_raw.columns)
    years_col = find_column(header, ALIASES["year"])
    gender_col = find_column(header, ALIASES["gender"])
    major_col = find_column(header, ALIASES["major"])

    if not years_col and not gender_col and not major_col:
        return pd.DataFrame()

    rename_map = {}
    selected_cols = []

    if years_col:
        selected_cols.append(years_col)
        rename_map[years_col] = "Year"
    if gender_col:
        selected_cols.append(gender_col)
        rename_map[gender_col] = "Gender"
    if major_col:
        selected_cols.append(major_col)
        rename_map[major_col] = "Major"

    df = data_frame_raw[selected_cols].copy().rename(columns=rename_map)

    # Ensure all 3 exist
    if "Year" not in df.columns:
        df["Year"] = "(blank)"
    if "Gender" not in df.columns:
        df["Gender"] = "(blank)"
    if "Major" not in df.columns:
        df["Major"] = "(blank)"

    df["Year"] = df["Year"].apply(normalize_year)
    df["Gender"] = df["Gender"].apply(normalize_gender)
    df["Major"] = df["Major"].apply(normalize_major)

    df["__meeting"] = file["name"]
    return df


def load_selected_data_frames(sheets, selected_files):
    dataframes = []
    for f in selected_files:
        df = standardized_dataframe_for_sheet(sheets, f)
        if not df.empty:
            dataframes.append(df)

    if not dataframes:
        return pd.DataFrame(columns=["Year", "Gender", "Major", "__meeting"])

    return pd.concat(dataframes, ignore_index=True)