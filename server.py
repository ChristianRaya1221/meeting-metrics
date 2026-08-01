from flask import Flask, jsonify, request, render_template
import os, sys
from dotenv import load_dotenv

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
def api_generate():
    body = request.json or {}
    files = body.get("files", [])
    if not files:
        return jsonify({"error": "No files provided"}), 400

    _, sheets_svc = get_svc()
    df = load_selected_data_frames(sheets_svc, files)

    if df.empty:
        return jsonify({"error": "No data loaded after standardization"}), 400

    result = {
        "total": int(len(df)),
        "meetings_count": int(df["__meeting"].nunique()),
    }

    for col in ["Year", "Gender", "Major"]:
        if col in df.columns:
            counts = df[col].value_counts()
            if col == "Year":
                sorted_pairs = sorted(
                    counts.items(), key=lambda x: YEAR_ORDER.get(x[0], 50)
                )
                result[col.lower()] = {k: int(v) for k, v in sorted_pairs}
            else:
                sorted_pairs = sorted(counts.items(), key=lambda x: -x[1])
                result[col.lower()] = {k: int(v) for k, v in sorted_pairs}

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
