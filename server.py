
import os, sys
import gc

from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, jsonify, request, render_template


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import (
    get_services,
    list_folders,
    find_general_meetings_folder,
    find_sheets_recursive,
    meeting_sort_key,
    load_selected_data_frames,
    sort_year,
    term_sort_key,
    YEAR_ORDER,
)

app = Flask(__name__, static_folder="static", template_folder="templates")
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)

load_dotenv()
ROOT_FOLDER_ID = os.environ.get("ROOT_FOLDER_ID")

_drive = None
_sheets_svc = None


def get_svc():
    global _drive, _sheets_svc
    if _drive is None:
        _drive, _sheets_svc = get_services()
    return _drive, _sheets_svc


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/years")
def api_years():
    drive, _ = get_svc()
    years = sorted(
        list_folders(drive, ROOT_FOLDER_ID), key=lambda f: sort_year(f["name"])
    )
    return jsonify(years)


TERM_KEYWORDS = {"fall", "winter", "spring", "summer"}


def _is_term_folder(name: str) -> bool:
    n = name.strip().lower()
    return any(t in n for t in TERM_KEYWORDS)


@app.route("/api/quarters")
def api_quarters():
    year_id = request.args.get("year_id")
    if not year_id:
        return jsonify({"error": "year_id required"}), 400
    drive, _ = get_svc()

    year_folders = list_folders(drive, year_id)

    # 1. Fall/Winter/Spring directly inside the year folder
    direct_terms = [f for f in year_folders if _is_term_folder(f["name"])]
    if direct_terms:
        return jsonify({
            "quarters": sorted(direct_terms, key=lambda f: term_sort_key(f["name"]))
        })

    # 2. Fall/Winter/Spring inside a "General Meetings" sub-folder
    gm = find_general_meetings_folder(year_folders)
    if gm:
        gm_folders = list_folders(drive, gm["id"])
        gm_terms = [f for f in gm_folders if _is_term_folder(f["name"])]
        if gm_terms:
            return jsonify({
                "quarters": sorted(gm_terms, key=lambda f: term_sort_key(f["name"]))
            })
        # GM folder exists but has no term sub-folders — return whatever is inside it
        if gm_folders:
            return jsonify({
                "quarters": sorted(gm_folders, key=lambda f: term_sort_key(f["name"]))
            })

    # Nothing found
    return jsonify({"error": "No Fall / Winter / Spring folders found for this year."}), 404


@app.route("/api/meetings")
def api_meetings():
    quarter_id = request.args.get("quarter_id")
    if not quarter_id:
        return jsonify({"error": "quarter_id required"}), 400
    drive, _ = get_svc()
    sheet_list = find_sheets_recursive(drive, quarter_id)
    return jsonify(sorted(sheet_list, key=lambda f: meeting_sort_key(f["name"])))


@app.route("/api/generate", methods=["POST"])
@limiter.limit("10 per minute")
def api_generate():
    body = request.json or {}
    files = body.get("files", [])
    focus_meeting_name = body.get("focus_meeting_name")

    if not files:
        return jsonify({"error": "No files provided"}), 400

    _, sheets_svc = get_svc()
    df = load_selected_data_frames(sheets_svc, files)

    if df.empty:
        return jsonify({"error": "No data loaded after standardization"}), 400

    per_meeting_lookup = df["__meeting"].value_counts().to_dict()
    per_meeting_counts = [
        {"name": f["name"], "count": int(per_meeting_lookup.get(f["name"], 0))}
        for f in files
    ]

    if focus_meeting_name:
        agg_df = df[df["__meeting"] == focus_meeting_name]
        if agg_df.empty:
            return jsonify({
                "error": f"No data found for meeting: {focus_meeting_name}"
            }), 400
    else:
        agg_df = df

    result = {
        "total": int(len(agg_df)),
        "meetings_count": int(agg_df["__meeting"].nunique()),
        "per_meeting_counts": per_meeting_counts,
        "focus_meeting_name": focus_meeting_name,
    }

    for col in ["Year", "Major"]:
        if col in agg_df.columns:
            counts = agg_df[col].value_counts()
            if col == "Year":
                sorted_pairs = sorted(
                    counts.items(), key=lambda x: YEAR_ORDER.get(x[0], 50)
                )
                result[col.lower()] = {k: int(v) for k, v in sorted_pairs}
            else:
                sorted_pairs = sorted(counts.items(), key=lambda x: -x[1])
                result[col.lower()] = {k: int(v) for k, v in sorted_pairs}
    del df, agg_df
    gc.collect()

    return jsonify(result)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(debug=debug_mode, port=port, host=host)
