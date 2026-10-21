import json
import random
import time
import uuid

import streamlit as st

import utils as U

st.set_page_config(page_title="SuperTET PRT Practice", page_icon="📚", layout="wide")
S = st.session_state
NEW = "➕ Create new"


def opt_fmt(opts):
    return lambda k: f"{chr(65 + k)}.  {opts[k]}"


# =====================================================================
# HOME
# =====================================================================
def home_page():
    st.title("📚 SuperTET PRT – Exam Practice")
    st.write("Practice subject-wise MCQs or attempt full timed mock tests.")
    subjects = U.list_subjects()
    series = U.list_series()
    n_q = sum(len(U.load_practice(s)["questions"]) for s, _ in subjects)
    n_t = sum(len(U.list_tests(s)) for s in series)
    c1, c2, c3 = st.columns(3)
    c1.metric("Subjects", len(subjects))
    c2.metric("Practice questions", n_q)
    c3.metric("Mock tests", n_t)
    st.info("👈 Use the sidebar to open **Practice Questions** or **Test Series**. "
            "Add new content from the **Admin** page.")


# =====================================================================
# PRACTICE
# =====================================================================
def _new_practice_state(n, shuffle):
    order = list(range(n))
    if shuffle:
        random.shuffle(order)
    S.p = {"order": order, "i": 0, "picked": {}, "checked": {}, "run": uuid.uuid4().hex[:6]}


def _p_go(d):
    S.p["i"] += d


def practice_page():
    st.header("📝 Practice Questions")
    subjects = U.list_subjects()
    if not subjects:
        st.info("No subjects yet. Add questions from the Admin page.")
        return
    names = dict(subjects)
    c1, c2, c3 = st.columns([3, 1, 1])
    slug = c1.selectbox("Select subject", list(names), format_func=names.get)
    shuffle = c2.checkbox("Shuffle", key="p_shuffle")
    qs = U.load_practice(slug)["questions"]
    if not qs:
        st.warning("This subject has no questions yet.")
        return

    sig = (slug, shuffle, len(qs))
    if S.get("p_sig") != sig:
        S.p_sig = sig
        _new_practice_state(len(qs), shuffle)
    if c3.button("🔄 Restart", use_container_width=True):
        _new_practice_state(len(qs), shuffle)
        st.rerun()

    P = S.p
    n, i = len(P["order"]), P["i"]
    q = qs[P["order"][i]]
    correct = sum(1 for k in P["checked"] if P["picked"][k] == qs[P["order"][k]]["answer"])
    m1, m2, m3 = st.columns(3)
    m1.metric("Attempted", f"{len(P['checked'])}/{n}")
    m2.metric("Correct", correct)
    m3.metric("Wrong", len(P["checked"]) - correct)
    st.progress((i + 1) / n, text=f"Question {i + 1} of {n}")

    st.markdown(f"### Q{i + 1}. {q['question']}")
    checked = i in P["checked"]
    choice = st.radio(
        "Options", list(range(len(q["options"]))), index=P["picked"].get(i),
        format_func=opt_fmt(q["options"]), key=f"p_{P['run']}_{slug}_{i}",
        disabled=checked, label_visibility="collapsed",
    )
    b1, b2, b3 = st.columns(3)
    b1.button("⬅ Previous", disabled=(i == 0), on_click=_p_go, args=(-1,), use_container_width=True)
    if b2.button("✅ Check answer", disabled=checked, type="primary", use_container_width=True):
        if choice is None:
            st.warning("Select an option first.")
        else:
            P["picked"][i] = choice
            P["checked"][i] = True
            st.rerun()
    b3.button("Next ➡", disabled=(i == n - 1), on_click=_p_go, args=(1,), use_container_width=True)

    if checked:
        if P["picked"][i] == q["answer"]:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Wrong. Correct answer: **{chr(65 + q['answer'])}. {q['options'][q['answer']]}**")
        with st.expander("💡 View explanation", expanded=False):
            st.write(q["explanation"] or "No explanation added for this question.")


# =====================================================================
# TEST SERIES
# =====================================================================
def _start_test(series, test):
    d = U.load_test(series, test)
    S.t = {
        "series": series, "test": test, "title": d["title"], "qs": d["questions"],
        "marks": d.get("marks_per_question", 1), "neg": d.get("negative_marks", 0),
        "end": time.time() + d.get("duration_minutes", 30) * 60,
        "answers": {}, "cur": 0, "submitted": False, "saved": False, "run": uuid.uuid4().hex[:6],
    }


def _t_goto(j):
    S.t["cur"] = j


def _t_submit():
    S.t["submitted"] = True


def _t_clear(cur, key):
    S.t["answers"].pop(cur, None)
    S.pop(key, None)


def _t_exit():
    S.t = None


def test_menu():
    series = U.list_series()
    if not series:
        st.info("No test series yet. Add one from the Admin page.")
        return
    s = st.selectbox("Select test series", series, format_func=U.pretty)
    tests = U.list_tests(s)
    if not tests:
        st.warning("This series has no tests yet.")
    for slug, title in tests:
        d = U.load_test(s, slug)
        with st.container(border=True):
            a, b = st.columns([4, 1])
            a.markdown(f"#### {title}")
            a.caption(f"{len(d['questions'])} questions  •  {d.get('duration_minutes', 30)} min  •  "
                      f"+{d.get('marks_per_question', 1)} / -{d.get('negative_marks', 0)} marks")
            b.button("▶ Start", key=f"start_{s}_{slug}", type="primary", use_container_width=True,
                     disabled=not d["questions"], on_click=_start_test, args=(s, slug))
    hist = U.load_results()
    if hist:
        with st.expander("📈 My previous attempts"):
            st.dataframe(hist, use_container_width=True, hide_index=True)


@st.fragment(run_every=1)
def timer_box():
    t = S.t
    left = int(t["end"] - time.time())
    if left <= 0:
        t["submitted"] = True
        st.rerun()  # full app rerun -> shows result
    st.metric("⏱ Time left", f"{left // 60:02d}:{left % 60:02d}")


def test_running():
    t = S.t
    qs, n, cur = t["qs"], len(t["qs"]), t["cur"]
    h1, h2 = st.columns([3, 1])
    h1.subheader(t["title"])
    with h2:
        timer_box()

    main, side = st.columns([3, 1])
    with side:
        st.markdown("**Question palette**")
        cols = st.columns(5)
        for j in range(n):
            mark = "✓" if j in t["answers"] else ""
            cols[j % 5].button(f"{j + 1}{mark}", key=f"pal_{j}", on_click=_t_goto, args=(j,),
                               type="primary" if j == cur else "secondary", use_container_width=True)
        st.caption("✓ = answered")

    with main:
        q = qs[cur]
        st.markdown(f"### Q{cur + 1}. {q['question']}")
        key = f"t_{t['run']}_{cur}"
        choice = st.radio("Options", list(range(len(q["options"]))), index=t["answers"].get(cur),
                          format_func=opt_fmt(q["options"]), key=key, label_visibility="collapsed")
        if choice is not None:
            t["answers"][cur] = choice
        b1, b2, b3, b4 = st.columns(4)
        b1.button("⬅ Previous", disabled=cur == 0, on_click=_t_goto, args=(cur - 1,), use_container_width=True)
        b2.button("🧹 Clear", on_click=_t_clear, args=(cur, key), use_container_width=True)
        b3.button("Next ➡", disabled=cur == n - 1, on_click=_t_goto, args=(cur + 1,), use_container_width=True)
        with b4.popover("📤 Submit test", use_container_width=True):
            st.write(f"Answered **{len(t['answers'])}** of **{n}**.")
            st.button("Yes, submit now", type="primary", on_click=_t_submit)


def test_result():
    t = S.t
    qs, ans = t["qs"], t["answers"]
    correct = sum(1 for j, a in ans.items() if a == qs[j]["answer"])
    wrong = len(ans) - correct
    score = correct * t["marks"] - wrong * t["neg"]
    max_score = len(qs) * t["marks"]
    if not t["saved"]:
        U.save_result({"series": U.pretty(t["series"]), "test": t["title"], "score": round(score, 2),
                       "max_score": max_score, "correct": correct, "wrong": wrong,
                       "unattempted": len(qs) - len(ans)})
        t["saved"] = True

    st.subheader(f"📊 Result – {t['title']}")
    c = st.columns(4)
    c[0].metric("Score", f"{score:g} / {max_score:g}")
    c[1].metric("Correct", correct)
    c[2].metric("Wrong", wrong)
    c[3].metric("Unattempted", len(qs) - len(ans))
    st.progress(max(0.0, min(1.0, score / max_score)) if max_score else 0.0)
    st.button("⬅ Back to test series", on_click=_t_exit)

    st.markdown("### Review & explanations")
    for j, q in enumerate(qs):
        your = ans.get(j)
        status = "⚪ Unattempted" if your is None else ("✅ Correct" if your == q["answer"] else "❌ Wrong")
        with st.expander(f"Q{j + 1}. {q['question'][:90]}  —  {status}"):
            st.markdown(f"**{q['question']}**")
            for k, o in enumerate(q["options"]):
                tag = " ✅ *(correct)*" if k == q["answer"] else ""
                tag += " 👈 *your answer*" if k == your else ""
                st.markdown(f"- {chr(65 + k)}. {o}{tag}")
            st.info(q["explanation"] or "No explanation added.")


def test_page():
    st.header("🧪 Test Series")
    t = S.get("t")
    if t is None:
        test_menu()
    elif t["submitted"]:
        test_result()
    else:
        test_running()


# =====================================================================
# ADMIN
# =====================================================================
def _admin_password():
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return "admin123"


def target_selector(prefix):
    """Pick where questions go. Returns a dict or None."""
    kind = st.radio("Add to", ["Practice (subject-wise)", "Test Series"], horizontal=True, key=f"{prefix}_kind")
    if kind.startswith("Practice"):
        subs = U.list_subjects()
        names = [n for _, n in subs]
        ch = st.selectbox("Subject", names + [NEW], key=f"{prefix}_sub")
        name = st.text_input("New subject name", key=f"{prefix}_subnew") if ch == NEW else ch
        return {"kind": "practice", "subject": name} if name.strip() else None

    series = U.list_series()
    sc = st.selectbox("Test series", series + [NEW], format_func=lambda s: s if s == NEW else U.pretty(s),
                      key=f"{prefix}_ser")
    sname = st.text_input("New test series name", key=f"{prefix}_sernew") if sc == NEW else sc
    if not sname.strip():
        return None
    tmap = dict(U.list_tests(sc)) if sc != NEW else {}
    tc = st.selectbox("Test", list(tmap) + [NEW], format_func=lambda s: s if s == NEW else tmap[s],
                      key=f"{prefix}_test_{sc}")
    settings = None
    if tc == NEW:
        tname = st.text_input("New test name (e.g. Mock Test 1)", key=f"{prefix}_testnew")
        a, b, c = st.columns(3)
        settings = {
            "duration_minutes": a.number_input("Duration (min)", 1, 300, 150, key=f"{prefix}_dur"),
            "marks_per_question": b.number_input("Marks / question", 0.0, 10.0, 1.0, 0.25, key=f"{prefix}_mk"),
            "negative_marks": c.number_input("Negative marks", 0.0, 10.0, 0.0, 0.25, key=f"{prefix}_neg"),
        }
    else:
        tname = tc
    return {"kind": "test", "series": sname, "test": tname, "settings": settings} if tname.strip() else None


def save_to_target(tg, questions):
    if tg["kind"] == "practice":
        return U.add_practice(tg["subject"], questions)
    return U.add_test(tg["series"], tg["test"], questions, tg["settings"])


SAMPLE_CSV = (
    "question,option_a,option_b,option_c,option_d,answer,explanation\n"
    "Capital of India?,Mumbai,New Delhi,Kolkata,Chennai,B,New Delhi is the capital of India.\n"
)
SAMPLE_JSON = json.dumps([{
    "question": "Capital of India?", "options": ["Mumbai", "New Delhi", "Kolkata", "Chennai"],
    "answer": "B", "explanation": "New Delhi is the capital of India."}], indent=2)


def admin_page():
    st.header("⚙️ Admin – Add & Manage Content")
    if not S.get("admin"):
        pw = st.text_input("Admin password", type="password")
        if st.button("Login", type="primary"):
            if pw == _admin_password():
                S.admin = True
                st.rerun()
            else:
                st.error("Wrong password")
        return

    t1, t2, t3 = st.tabs(["➕ Add one question", "📤 Bulk upload", "🗂 Manage"])

    with t1:
        tg = target_selector("one")
        with st.form("add_q", clear_on_submit=True):
            question = st.text_area("Question")
            o = [st.text_input(f"Option {c}") for c in "ABCD"]
            ans = st.selectbox("Correct answer", list("ABCD"))
            expl = st.text_area("Explanation / solution")
            ok = st.form_submit_button("Add question", type="primary")
        if ok:
            if not tg:
                st.error("Choose or type a target subject / test first.")
            else:
                try:
                    q = U.normalize_question({"question": question, "options": o, "answer": ans, "explanation": expl})
                    save_to_target(tg, [q])
                    st.success("Question added ✅")
                except Exception as e:
                    st.error(f"Could not add: {e}")

    with t2:
        st.caption("Upload a CSV or JSON file with many questions at once.")
        d1, d2 = st.columns(2)
        d1.download_button("⬇ CSV template", SAMPLE_CSV, "template.csv", "text/csv")
        d2.download_button("⬇ JSON template", SAMPLE_JSON, "template.json", "application/json")
        tg2 = target_selector("bulk")
        up = st.file_uploader("Upload file", type=["csv", "json"])
        if up:
            qs, errs = U.parse_upload(up.name, up.getvalue())
            st.write(f"Valid questions found: **{len(qs)}**")
            for e in errs:
                st.warning(e)
            if qs and st.button("Import questions", type="primary"):
                if not tg2:
                    st.error("Choose or type a target subject / test first.")
                else:
                    save_to_target(tg2, qs)
                    st.success(f"Imported {len(qs)} questions ✅")

    with t3:
        sets = U.all_sets()
        if not sets:
            st.info("Nothing to manage yet.")
        else:
            labels = [l for l, _ in sets]
            label = st.selectbox("Select set", labels)
            path = dict(sets)[label]
            data = U.read_set(path)
            qs = data["questions"]
            st.write(f"**{len(qs)}** questions")
            st.dataframe([{"No.": i + 1, "Question": q["question"],
                           "Answer": chr(65 + q["answer"])} for i, q in enumerate(qs)],
                         use_container_width=True, hide_index=True)
            st.download_button("⬇ Download backup (JSON)", json.dumps(data, ensure_ascii=False, indent=2),
                               file_name=path.name, mime="application/json")
            if qs:
                a, b = st.columns([1, 1])
                num = a.number_input("Question number to delete", 1, len(qs), 1)
                if b.button("🗑 Delete question"):
                    qs.pop(int(num) - 1)
                    U.write_set(path, data)
                    st.rerun()
            if st.checkbox("I want to delete this entire set"):
                if st.button("❌ Delete set", type="primary"):
                    U.delete_set(path)
                    st.rerun()
    if st.sidebar.button("Logout admin"):
        S.admin = False
        st.rerun()


# =====================================================================
# NAVIGATION
# =====================================================================
PAGES = {"🏠 Home": home_page, "📝 Practice Questions": practice_page,
         "🧪 Test Series": test_page, "⚙️ Admin": admin_page}
st.sidebar.title("SuperTET PRT")
PAGES[st.sidebar.radio("Go to", list(PAGES))]()
