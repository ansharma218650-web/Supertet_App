"""Storage + helper functions. All data lives in JSON files inside /data."""
import csv
import io
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent / "data"
PRACTICE_DIR = BASE / "practice"        # data/practice/<subject>.json
TEST_DIR = BASE / "test_series"         # data/test_series/<series>/<test>.json
RESULTS_FILE = BASE / "results.csv"
for _d in (PRACTICE_DIR, TEST_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ---------- basic helpers ----------
def slugify(text: str) -> str:
    s = re.sub(r"[^\w]+", "_", text.strip().lower()).strip("_")
    return s or "untitled"


def pretty(slug: str) -> str:
    return slug.replace("_", " ").title()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- question validation / parsing ----------
def normalize_question(q: dict) -> dict:
    text = str(q.get("question", "")).strip()
    opts = [str(o).strip() for o in q.get("options", []) if str(o).strip()]
    if not text:
        raise ValueError("question text is empty")
    if len(opts) < 2:
        raise ValueError("at least 2 options are required")
    ans = q.get("answer")
    if isinstance(ans, str):
        a = ans.strip().upper()
        ans = ord(a) - 65 if (len(a) == 1 and a.isalpha()) else int(a)
    if not isinstance(ans, int) or not 0 <= ans < len(opts):
        raise ValueError("answer must be a letter (A-D) or a valid 0-based index")
    return {
        "id": q.get("id") or uuid.uuid4().hex[:8],
        "question": text,
        "options": opts,
        "answer": ans,
        "explanation": str(q.get("explanation", "")).strip(),
    }


def parse_upload(filename: str, raw: bytes):
    """Return (questions, errors) from a .json or .csv upload."""
    questions, errors = [], []
    rows = []
    try:
        if filename.lower().endswith(".json"):
            data = json.loads(raw.decode("utf-8-sig"))
            rows = data["questions"] if isinstance(data, dict) else data
        else:
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            for r in reader:
                r = {(k or "").strip().lower(): (v or "") for k, v in r.items()}
                rows.append({
                    "question": r.get("question", ""),
                    "options": [r.get(f"option_{c}", "") for c in "abcd"],
                    "answer": r.get("answer", ""),
                    "explanation": r.get("explanation", ""),
                })
    except Exception as e:
        return [], [f"Could not read file: {e}"]
    for n, row in enumerate(rows, 1):
        try:
            questions.append(normalize_question(row))
        except Exception as e:
            errors.append(f"Row {n}: {e}")
    return questions, errors


# ---------- practice ----------
def list_subjects():
    out = []
    for p in PRACTICE_DIR.glob("*.json"):
        out.append((p.stem, _read(p).get("subject", pretty(p.stem))))
    return sorted(out, key=lambda x: x[1])


def load_practice(slug: str) -> dict:
    return _read(PRACTICE_DIR / f"{slug}.json")


def add_practice(subject_name: str, questions: list) -> int:
    path = PRACTICE_DIR / f"{slugify(subject_name)}.json"
    data = _read(path) if path.exists() else {"subject": subject_name.strip(), "questions": []}
    data["questions"].extend(questions)
    _write(path, data)
    return len(questions)


# ---------- test series ----------
def list_series():
    return sorted(p.name for p in TEST_DIR.iterdir() if p.is_dir())


def list_tests(series: str):
    out = []
    for p in sorted((TEST_DIR / series).glob("*.json")):
        out.append((p.stem, _read(p).get("title", pretty(p.stem))))
    return out


def load_test(series: str, test: str) -> dict:
    return _read(TEST_DIR / series / f"{test}.json")


def add_test(series_name, test_name, questions, settings=None) -> int:
    path = TEST_DIR / slugify(series_name) / f"{slugify(test_name)}.json"
    if path.exists():
        data = _read(path)
    else:
        s = settings or {}
        data = {
            "title": test_name.strip(),
            "duration_minutes": s.get("duration_minutes", 30),
            "marks_per_question": s.get("marks_per_question", 1),
            "negative_marks": s.get("negative_marks", 0),
            "questions": [],
        }
    data["questions"].extend(questions)
    _write(path, data)
    return len(questions)


# ---------- generic (used by the admin "Manage" tab) ----------
def all_sets():
    """[(label, path)] for every practice subject and every test."""
    sets = []
    for slug, name in list_subjects():
        sets.append((f"Practice › {name}", PRACTICE_DIR / f"{slug}.json"))
    for s in list_series():
        for slug, title in list_tests(s):
            sets.append((f"Test › {pretty(s)} › {title}", TEST_DIR / s / f"{slug}.json"))
    return sets


def read_set(path):
    return _read(Path(path))


def write_set(path, data):
    _write(Path(path), data)


def delete_set(path):
    p = Path(path)
    p.unlink(missing_ok=True)
    if p.parent != PRACTICE_DIR and p.parent.exists() and not any(p.parent.iterdir()):
        p.parent.rmdir()


# ---------- results history ----------
FIELDS = ["time", "series", "test", "score", "max_score", "correct", "wrong", "unattempted"]


def save_result(row: dict) -> None:
    new = not RESULTS_FILE.exists()
    with RESULTS_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), **row})


def load_results():
    if not RESULTS_FILE.exists():
        return []
    with RESULTS_FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))[::-1]
