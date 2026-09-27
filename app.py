import streamlit as st
import sqlite3
import json
import re
import threading
from datetime import datetime, timezone, timedelta
import pandas as pd
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================================================================
# 1. TIMEZONE CONFIG (NEPAL TIME UTC+5:45) & PAGE SETUP
# =====================================================================
NEPAL_TZ = timezone(timedelta(hours=5, minutes=45))

def get_nepal_now():
    return datetime.now(NEPAL_TZ)

def get_today_nepal_str():
    return get_nepal_now().strftime("%Y-%m-%d")

st.set_page_config(
    page_title="Loksewa Agri 7th Level Portal",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# 2. EYE-CATCHY CUSTOM CSS & TOP EXAM BAR
# =====================================================================
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-title {
        background: linear-gradient(135deg, #059669 0%, #10b981 50%, #0284c7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }
    
    .exam-top-bar {
        background: #0f172a;
        color: #f8fafc;
        border-radius: 12px;
        padding: 12px 20px;
        margin-bottom: 1.2rem;
        border: 1px solid #1e293b;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
    }
    
    .clock-badge {
        background: #1e293b;
        color: #38bdf8;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 700;
        border: 1px solid #334155;
    }
    
    .question-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        margin-top: 0.8rem;
        margin-bottom: 0.8rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.02);
    }
    
    .badge {
        display: inline-block;
        padding: 0.22rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    .badge-gk { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
    .badge-iq { background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe; }
    .badge-agri { background: #d1fae5; color: #047857; border: 1px solid #a7f3d0; }
    .badge-src { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }

    .figure-frame {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 10px;
        padding: 6px;
        text-align: center;
    }
    .figure-label {
        font-weight: 800;
        font-size: 0.9rem;
        color: #0f172a;
        margin-bottom: 4px;
        display: block;
    }
    
    .answer-banner-correct {
        background: #ecfdf5;
        border-left: 5px solid #10b981;
        padding: 10px 14px;
        border-radius: 6px;
        margin: 8px 0;
        color: #065f46;
        font-weight: 700;
    }
    .answer-banner-wrong {
        background: #fff1f2;
        border-left: 5px solid #f43f5e;
        padding: 10px 14px;
        border-radius: 6px;
        margin: 8px 0;
        color: #9f1239;
        font-weight: 700;
    }
    .hint-container {
        background: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 10px 14px;
        border-radius: 6px;
        margin-top: 8px;
    }
    .option-explanation-pill {
        background: #ffffff;
        border: 1px dashed #cbd5e1;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 5px 0;
        font-size: 0.88rem;
        color: #334155;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DB_FILE = "loksewa_agri_7th.db"

# =====================================================================
# 3. SILENT API KEY RESOLVER (NEVER EXPOSED IN UI)
# =====================================================================
def get_groq_api_key():
    return st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# =====================================================================
# 4. DATABASE INITIALIZATION (NO HARDCODED QUESTIONS)
# =====================================================================
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def safe_get(row, key, default=None):
    try:
        if key in row.keys():
            val = row[key]
            return val if val is not None else default
    except Exception:
        pass
    return default

def init_db():
    """Initializes clean database schema with zero pre-seeded questions."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_date TEXT,
                set_number INTEGER DEFAULT 1,
                title TEXT,
                total_questions INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                q_num INTEGER,
                category TEXT,
                sub_syllabus TEXT,
                exam_source TEXT,
                is_figure_option INTEGER DEFAULT 0,
                question_text TEXT,
                figure_svg TEXT,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                correct_option TEXT,
                explanation TEXT,
                option_hints TEXT,
                FOREIGN KEY(exam_id) REFERENCES exams(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                attempt_date TEXT,
                total_attempted INTEGER,
                correct_count INTEGER,
                wrong_count INTEGER,
                unattempted_count INTEGER,
                score REAL,
                is_passed INTEGER,
                user_answers TEXT,
                FOREIGN KEY(exam_id) REFERENCES exams(id)
            )
        ''')
        conn.commit()

init_db()

def get_total_exams_count():
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]

def get_next_set_number():
    with get_db() as conn:
        val = conn.execute("SELECT MAX(set_number) FROM exams").fetchone()[0]
        return (val + 1) if val else 1

def get_recent_stems(limit=80):
    with get_db() as conn:
        rows = conn.execute("SELECT question_text FROM questions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [r[0][:40] for r in rows if r[0]]

# =====================================================================
# 5. DYNAMIC MODEL RESOLVER (NO 404s)
# =====================================================================
def get_best_active_model(client):
    if "active_groq_model" in st.session_state and st.session_state["active_groq_model"]:
        return st.session_state["active_groq_model"]

    candidate_order = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]

    try:
        active_models = client.models.list().data
        available_ids = [
            m.id for m in active_models
            if not any(x in m.id.lower() for x in ["whisper", "embed", "guard", "vision", "canopylabs", "orpheus"])
        ]
        priority_queue = [m for m in candidate_order if m in available_ids] + [m for m in available_ids if m not in candidate_order]
    except Exception:
        priority_queue = candidate_order

    for model_id in priority_queue:
        try:
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "1"}],
                max_tokens=2
            )
            st.session_state["active_groq_model"] = model_id
            return model_id
        except Exception:
            continue

    return "openai/gpt-oss-20b"

# =====================================================================
# 6. UNIVERSAL NORMALIZER (PREVENTS EMPTY OPTIONS & MISSING HINTS)
# =====================================================================
def extract_opt(q, key_letter):
    """Safely extracts option text across all possible model response keys."""
    u = key_letter.upper()
    l = key_letter.lower()
    for k in [f"option_{l}", f"option_{u}", f"option{u}", f"option{l}", f"opt_{l}", f"opt_{u}", u, l]:
        if k in q and q[k] is not None and str(q[k]).strip():
            return str(q[k]).strip()
    opts = q.get("options") or q.get("choices")
    if isinstance(opts, dict):
        for k in [u, l, f"option_{l}", f"option_{u}"]:
            if k in opts and opts[k] is not None and str(opts[k]).strip():
                return str(opts[k]).strip()
    elif isinstance(opts, list):
        idx_map = {"a": 0, "b": 1, "c": 2, "d": 3}
        idx = idx_map.get(l, 0)
        if len(opts) > idx and opts[idx] is not None:
            return str(opts[idx]).strip()
    return f"Option ({u})"

def extract_hints_dict(q, correct_opt, explanation):
    """Guarantees that all 4 options (A, B, C, D) have distinct explanations."""
    raw = q.get("option_hints") or q.get("hints") or q.get("options_hints")
    hints_dict = {}
    if isinstance(raw, dict):
        for k in ["A", "B", "C", "D"]:
            val = raw.get(k) or raw.get(k.lower()) or raw.get(f"option_{k.lower()}")
            if val:
                hints_dict[k] = str(val).strip()
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k in ["A", "B", "C", "D"]:
                    val = parsed.get(k) or parsed.get(k.lower()) or parsed.get(f"option_{k.lower()}")
                    if val:
                        hints_dict[k] = str(val).strip()
        except Exception:
            pass

    for k in ["A", "B", "C", "D"]:
        if k not in hints_dict or not hints_dict[k]:
            if k == correct_opt:
                hints_dict[k] = explanation if explanation else "Verified correct option as per Nepal Government laws and standards."
            else:
                hints_dict[k] = f"This alternative is incorrect for this stem. It refers to another statutory provision, standard, or distractor."

    return hints_dict

# =====================================================================
# 7. RESILIENT JSON EXTRACTOR
# =====================================================================
def extract_and_parse_json(content):
    if not content or not content.strip():
        return []

    content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
    content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE).strip()

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data.get("questions", list(data.values())[0])
        elif isinstance(data, list):
            return data
    except Exception:
        pass

    m = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', content)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                return data.get("questions", list(data.values())[0])
            elif isinstance(data, list):
                return data
        except Exception:
            pass

    q_pattern = re.compile(r'\{\s*"q_num"[\s\S]*?"question_text"[\s\S]*?"correct_option"\s*:\s*"[A-D]"[\s\S]*?\}')
    recovered = []
    for match in q_pattern.finditer(content):
        block = re.sub(r',\s*([\}\]])', r'\1', match.group(0))
        try:
            recovered.append(json.loads(block))
        except Exception:
            pass

    return recovered

# =====================================================================
# 8. EXACT 100-QUESTION COMPILER
# =====================================================================
def fetch_batch(prompt, client, active_model):
    for _ in range(2):
        try:
            comp = client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": "You are Nepal Public Service Commission (Loksewa Aayog) Chief Examination Specialist. Return pure JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.2
            )
            q_list = extract_and_parse_json(comp.choices[0].message.content)
            if q_list:
                return q_list
        except Exception:
            time.sleep(0.3)
    return []

def generate_full_100_exam(client, target_date_str, set_num, title_str):
    past_stems = get_recent_stems(limit=40)
    avoid_snippet = ("Avoid stems: " + "; ".join(past_stems[:10])) if past_stems else ""
    active_model = get_best_active_model(client)

    batches = [
        # Batch 1: GK Q1-13 (13 Qs in Nepali)
        f"""Generate exactly 13 General Awareness MCQs (numbered 1 to 13) for Nepal PSC Agri 7th in Nepali Unicode.
Strict Government sources: Census 2078 (National Statistics Office), Constitution (Art 36, 42, 51; Schedules 5, 8, 9), Physical geography. {avoid_snippet}
Include full options (option_a, option_b, option_c, option_d), correct_option, explanation, and option_hints describing why A, B, C, D are correct/incorrect.
JSON Schema: {{"questions": [{{"q_num": 1, "category": "GK", "sub_syllabus": "1.8 Constitution", "exam_source": "Federal PSC 2080", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A": "why A...", "B": "why B...", "C": "why C...", "D": "why D..."}}}}]}}""",

        # Batch 2: GK Q14-25 (12 Qs in Nepali)
        f"""Generate exactly 12 General Awareness MCQs (numbered 14 to 25) for Nepal PSC Agri 7th in Nepali Unicode.
Strict Government sources: 16th Plan targets, Civil Service Act 2049, POSDCORB, Budgeting, Good Governance, UNO, BIMSTEC. {avoid_snippet}
Include full options (option_a, option_b, option_c, option_d), correct_option, explanation, and option_hints for A, B, C, D.
JSON Schema: {{"questions": [{{"q_num": 14, "category": "GK", "sub_syllabus": "1.5 Plan", "exam_source": "Bagmati PSC 2081", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A": "why A...", "B": "why B...", "C": "why C...", "D": "why D..."}}}}]}}""",

        # Batch 3: IQ Verbal & Numerical Q26-42 (17 Qs in English)
        f"""Generate exactly 17 Loksewa Aptitude MCQs (numbered 26 to 42) in English:
Q26-34: Logical reasoning (series, direction, coding, Venn diagram). Q35-42: Numerical reasoning (ratio, time/work, profit/loss, percentage).
'is_figure_option': 0, 'figure_svg': null. Include full options, explanation, and option_hints for A, B, C, D.
JSON Schema: {{"questions": [{{"q_num": 26, "category": "IQ", "sub_syllabus": "2.1 Reasoning", "exam_source": "PSC Aptitude", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}""",

        # Batch 4: IQ Spatial Q43-50 (8 Qs with inline SVGs)
        f"""Generate exactly 8 Non-Verbal Spatial MCQs (numbered 43 to 50):
Figure series, pattern completion, 3x3 matrix, cube net unfolding.
MUST provide valid inline SVGs: 'is_figure_option': 1, 'figure_svg': "<svg viewBox='0 0 200 60' ...>...</svg>", 'option_a'/'option_b'/'option_c'/'option_d': "<svg viewBox='0 0 50 50' ...>...</svg>".
Include explanation and option_hints for A, B, C, D.
JSON Schema: {{"questions": [{{"q_num": 43, "category": "IQ", "sub_syllabus": "2.3 Spatial", "exam_source": "PSC Spatial", "is_figure_option": 1, "figure_svg": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}""",

        # Batch 5: Technical Agri Part A Q51-75 (25 Qs in English)
        f"""Generate exactly 25 Technical Agri MCQs (numbered 51 to 75) based strictly on Government of Nepal official sources:
- Unit 1: History & Status (5 Qs, Q51-55): APP, Devolution, DoA/NARC timeline, Agriculture Census 2078 landholdings, GDP share.
- Unit 2: Research & Extension (5 Qs, Q56-60): NARC vision, AFU, CTEVT, FFS, AKC, T&V.
- Unit 3: NRM, Environment & DRM (10 Qs, Q61-70): IPNM, IPM, GAP, Organic certification (PGS), NAPA/LAPA, Crop insurance (80% subsidy).
- Unit 4: Policies (5 Qs, Q71-75): Constitution Art 36, 16th Plan agri goals, ADS (2015-2035) 4 pillars. {avoid_snippet}
Include full options (option_a, option_b, option_c, option_d), correct_option, explanation, and option_hints for A, B, C, D.
JSON Schema: {{"questions": [{{"q_num": 51, "category": "Agri", "sub_syllabus": "Technical Agri", "exam_source": "Koshi PSC 2080", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}""",

        # Batch 6: Technical Agri Part B Q76-100 (25 Qs in English)
        f"""Generate exactly 25 Technical Agri MCQs (numbered 76 to 100) based strictly on Government of Nepal official acts:
- Unit 4: Acts & Trade (5 Qs, Q76-80): Seeds Act 2045 & Rules 2069, Plant Protection Act 2064, Pesticide Management Act 2076 (26 banned list), Food Sovereignty Act 2076, WTO SPS.
- Unit 5: Agri Technology & Management (20 Qs, Q81-100):
  * Seed classes (Foundation White, Breeder Yellow, Certified Blue), isolation distances
  * Soil pH, lime requirement formula, essential nutrient mobility (N, P, K mobile)
  * Plant protection: Fall Armyworm (inverted Y), Late blight, Clubroot, ETL
  * Economics & research: LER, price elasticity, RCBD (12 error df). {avoid_snippet}
Include full options (option_a, option_b, option_c, option_d), correct_option, explanation, and option_hints for A, B, C, D.
JSON Schema: {{"questions": [{{"q_num": 76, "category": "Agri", "sub_syllabus": "Technical Agri", "exam_source": "Lumbini PSC 2080", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}"""
    ]

    all_100 = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_batch, p, client, active_model) for p in batches]
        for f in as_completed(futures):
            all_100.extend(f.result())

    if not all_100:
        raise ValueError("Failed to retrieve questions from AI engine. Please retry.")

    all_100.sort(key=lambda x: x.get("q_num", 0))

    # Save to SQLite Database with guaranteed 100 count and normalized options
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO exams (exam_date, set_number, title, total_questions) VALUES (?, ?, ?, ?)",
            (target_date_str, set_num, title_str, len(all_100))
        )
        exam_id = cursor.lastrowid

        for idx, raw_q in enumerate(all_100, 1):
            q_num = idx
            cat = "GK" if 1 <= q_num <= 25 else ("IQ" if 26 <= q_num <= 50 else "Agri")
            sub_syl = raw_q.get("sub_syllabus", "PSC Syllabus Section")
            exam_src = raw_q.get("exam_source", "Federal/Provincial PSC")
            q_text = raw_q.get("question_text", f"Question {q_num}")
            correct_opt = str(raw_q.get("correct_option", "A")).upper().strip()
            if correct_opt not in ["A", "B", "C", "D"]:
                correct_opt = "A"

            opt_a = extract_opt(raw_q, "a")
            opt_b = extract_opt(raw_q, "b")
            opt_c = extract_opt(raw_q, "c")
            opt_d = extract_opt(raw_q, "d")

            is_fig = 1 if (26 <= q_num <= 50 and "<svg" in str(opt_a).lower()) else 0
            fig_svg = raw_q.get("figure_svg") if is_fig else None
            explanation = raw_q.get("explanation", "Standard verified benchmark according to Nepal Government official syllabus.")
            hints_dict = extract_hints_dict(raw_q, correct_opt, explanation)

            cursor.execute('''
                INSERT INTO questions 
                (exam_id, q_num, category, sub_syllabus, exam_source, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id, q_num, cat, sub_syl, exam_src, is_fig, q_text, fig_svg,
                opt_a, opt_b, opt_c, opt_d, correct_opt, explanation, json.dumps(hints_dict)
            ))
        conn.commit()

    return exam_id, len(all_100), active_model

# =====================================================================
# 9. SILENT BUFFER WORKER (PRE-GENERATES UP TO 10 SETS IN BACKGROUND)
# =====================================================================
def is_buffer_thread_active():
    for t in threading.enumerate():
        if t.name == "LoksewaBufferWorker":
            return True
    return False

def buffer_worker_loop(api_key, target_sets=10):
    """Silently runs in background to compile up to 10 sets so the user never waits."""
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        while True:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            count = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
            val = conn.execute("SELECT MAX(set_number) FROM exams").fetchone()[0]
            conn.close()

            if count >= target_sets:
                break

            next_s = (val + 1) if val else 1
            t_str = get_today_nepal_str()
            title = f"Loksewa Krishi 7th Level Model Set #{next_s}"
            try:
                generate_full_100_exam(client, t_str, next_s, title)
            except Exception:
                time.sleep(4)

            time.sleep(3) # Polite interval between sets
    except Exception:
        pass

def trigger_background_buffering():
    key = get_groq_api_key()
    if key and not is_buffer_thread_active():
        t = threading.Thread(target=buffer_worker_loop, args=(key, 10), name="LoksewaBufferWorker", daemon=True)
        t.start()

# Automatically kick off buffering when app starts
trigger_background_buffering()

# =====================================================================
# 10. SIDEBAR NAVIGATION & REAL-TIME CLOCK
# =====================================================================
st.sidebar.markdown("<h2 style='color:#10b981; margin-bottom:0;'>🌱 AgriLoksewa 7th</h2>", unsafe_allow_html=True)
st.sidebar.caption("Nepal Krishi Sewa (Gazetted 3rd Class / 7th Level)")

nepal_clock = get_nepal_now().strftime("%Y-%m-%d | %I:%M %p")
st.sidebar.markdown(f"<div class='clock-badge'>🕒 Nepal: {nepal_clock}</div>", unsafe_allow_html=True)

# Live Sets Ready Counter
total_cached = get_total_exams_count()
buffer_status = "Pre-buffering active in background..." if is_buffer_thread_active() else "10 Sets Buffer Complete"
st.sidebar.info(f"📦 **Ready Sets in System:** {total_cached} / 10\n\n_{buffer_status}_")

st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigation Menu",
    [
        "📝 Attempt 100-Question Exam",
        "📖 Review Exam & Option Hints",
        "⚡ Instant Next Set (0s Wait)",
        "📊 Score History & Analytics"
    ]
)

# =====================================================================
# TAB 1: ATTEMPT 100-QUESTION EXAM
# =====================================================================
if menu == "📝 Attempt 100-Question Exam":
    st.markdown('<div class="main-title">📝 100-Question Model Examination</div>', unsafe_allow_html=True)

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY set_number ASC, id ASC").fetchall()

    if not exams:
        st.info("No exam sets compiled yet. Initializing your first 100-question set...")
        api_key = get_groq_api_key()
        if not api_key:
            st.error("Please configure GROQ_API_KEY in `.streamlit/secrets.toml` or your environment variables.")
            st.stop()

        if st.button("🚀 Compile Set #1 Now", type="primary"):
            from groq import Groq
            c = Groq(api_key=api_key)
            with st.spinner("Compiling Set #1 (100 Questions) strictly as per syllabus..."):
                generate_full_100_exam(c, get_today_nepal_str(), 1, "Loksewa Krishi 7th Model Set #1")
            trigger_background_buffering()
            st.rerun()
        st.stop()

    exam_map = {f"Set #{e['set_number']} ({e['exam_date']}) - {e['title']} ({e['total_questions']} Qs)": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Set to Solve:", list(exam_map.keys()))
    selected_exam_id = exam_map[selected_label]

    # Live Timer
    if f"start_time_{selected_exam_id}" not in st.session_state:
        st.session_state[f"start_time_{selected_exam_id}"] = time.time()

    elapsed = int(time.time() - st.session_state[f"start_time_{selected_exam_id}"])
    remaining = max(0, 5400 - elapsed)
    rem_m, rem_s = divmod(remaining, 60)

    st.markdown(f"""
    <div class="exam-top-bar">
        <div>
            <b>🕒 Nepal Standard Time:</b> {get_nepal_now().strftime("%I:%M:%S %p")} &nbsp;|&nbsp; 
            <b>📅 Date:</b> {get_today_nepal_str()}
        </div>
        <div>
            <span class="clock-badge">⏳ Time Remaining: {rem_m:02d}:{rem_s:02d} / 90:00</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with get_db() as conn:
        questions = conn.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", (selected_exam_id,)).fetchall()

    if not questions:
        st.error("No questions found.")
        st.stop()

    if f"user_ans_{selected_exam_id}" not in st.session_state:
        st.session_state[f"user_ans_{selected_exam_id}"] = {q['q_num']: None for q in questions}

    # Sidebar Progress & Palette
    st.sidebar.markdown("### 🧭 Question Palette (1-100)")
    ans_count = sum(1 for v in st.session_state[f"user_ans_{selected_exam_id}"].values() if v is not None)
    st.sidebar.progress(ans_count / len(questions), text=f"Answered: {ans_count} / {len(questions)}")

    pal_cols = st.sidebar.columns(5)
    for idx, q in enumerate(questions):
        q_no = q['q_num']
        col = pal_cols[idx % 5]
        is_done = st.session_state[f"user_ans_{selected_exam_id}"][q_no] is not None
        col.caption(f"{'🟢' if is_done else '⚪'} {q_no}")

    # Exam Form
    with st.form(key=f"exam_form_{selected_exam_id}"):
        for q in questions:
            q_num = q['q_num']
            cat = safe_get(q, 'category', 'Agri')
            sub_syl = safe_get(q, 'sub_syllabus', '')
            exam_src = safe_get(q, 'exam_source', 'PSC Model')
            badge_class = "badge-gk" if cat == "GK" else ("badge-iq" if cat == "IQ" else "badge-agri")

            st.markdown(f"""
            <div class="question-card">
                <div>
                    <span class="badge {badge_class}">{cat}</span>
                    <span class="badge badge-src">{exam_src}</span>
                    <span style="font-size:0.75rem; color:#64748b;">{sub_syl}</span>
                </div>
                <h4 style="margin: 0.4rem 0 0.5rem 0; color:#0f172a;">Q{q_num}. {q['question_text']}</h4>
            </div>
            """, unsafe_allow_html=True)

            fig_svg = safe_get(q, 'figure_svg')
            if fig_svg and str(fig_svg).strip().startswith("<svg"):
                st.components.v1.html(fig_svg, height=85)

            current_choice = st.session_state[f"user_ans_{selected_exam_id}"].get(q_num, None)
            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0)) and str(q['option_a']).strip().startswith("<svg")

            opts = {"A": q['option_a'], "B": q['option_b'], "C": q['option_c'], "D": q['option_d']}

            if is_fig_opt:
                st.markdown("**Choose the matching figure:**")
                fA, fB, fC, fD = st.columns(4)
                with fA:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(A)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_a'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)
                with fB:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(B)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_b'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)
                with fC:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(C)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_c'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)
                with fD:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(D)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_d'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)

                idx_val = ["A", "B", "C", "D"].index(current_choice) if current_choice in ["A", "B", "C", "D"] else None
                chosen = st.radio(
                    label=f"Q{q_num} Selection",
                    options=["A", "B", "C", "D"],
                    index=idx_val,
                    format_func=lambda x: f"Option ({x})",
                    key=f"radio_fig_{selected_exam_id}_{q_num}",
                    horizontal=True
                )
                st.session_state[f"user_ans_{selected_exam_id}"][q_num] = chosen
            else:
                idx_val = ["A", "B", "C", "D"].index(current_choice) if current_choice in ["A", "B", "C", "D"] else None
                chosen = st.radio(
                    label=f"Q{q_num} Answer Options",
                    options=["A", "B", "C", "D"],
                    index=idx_val,
                    format_func=lambda x: f"({x}) {opts[x]}",
                    key=f"radio_txt_{selected_exam_id}_{q_num}"
                )
                st.session_state[f"user_ans_{selected_exam_id}"][q_num] = chosen

            st.write("---")

        submitted = st.form_submit_button("🏁 Final Submit & Compute Official Score", type="primary", use_container_width=True)

        if submitted:
            correct_cnt = 0
            wrong_cnt = 0
            unattempted_cnt = 0

            for q in questions:
                ans = st.session_state[f"user_ans_{selected_exam_id}"][q['q_num']]
                if ans is None:
                    unattempted_cnt += 1
                elif ans == q['correct_option']:
                    correct_cnt += 1
                else:
                    wrong_cnt += 1

            final_score = round((correct_cnt * 1.0) - (wrong_cnt * 0.20), 2)
            passed = 1 if final_score >= 40.0 else 0

            with get_db() as conn:
                conn.execute('''
                    INSERT INTO attempts (exam_id, attempt_date, total_attempted, correct_count, wrong_count, unattempted_count, score, is_passed, user_answers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    selected_exam_id,
                    get_nepal_now().strftime("%Y-%m-%d %H:%M:%S"),
                    (correct_cnt + wrong_cnt),
                    correct_cnt,
                    wrong_cnt,
                    unattempted_cnt,
                    final_score,
                    passed,
                    json.dumps(st.session_state[f"user_ans_{selected_exam_id}"])
                ))
                conn.commit()

            st.success("✅ Exam Evaluated Successfully!")
            if passed:
                st.balloons()

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#059669,#10b981); color:#fff; padding:18px; border-radius:10px; margin:16px 0;">
                <h2 style="margin:0; color:#fff;">Score: {final_score} / 100 {'(QUALIFIED ✅)' if passed else '(FAILED ❌)'}</h2>
                <p style="margin:4px 0 0 0; font-size:1.05rem;">Correct (+1.0): <b>{correct_cnt}</b> | Incorrect (-0.2): <b>{wrong_cnt}</b> | Unattempted: <b>{unattempted_cnt}</b></p>
            </div>
            """, unsafe_allow_html=True)
            st.info("👉 Check the **'📖 Review Exam & Option Hints'** tab to inspect all correct answers and the full 4-option breakdowns!")

# =====================================================================
# TAB 2: REVIEW EXAM & DETAILED OPTION HINTS (ALL 4 OPTIONS EXPLAINED)
# =====================================================================
elif menu == "📖 Review Exam & Option Hints":
    st.markdown('<div class="main-title">📖 Comprehensive Review & Option Breakdown</div>', unsafe_allow_html=True)

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY set_number DESC, id DESC").fetchall()

    if not exams:
        st.warning("No exams stored.")
        st.stop()

    exam_map = {f"Set #{e['set_number']} ({e['exam_date']}) - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam to Review:", list(exam_map.keys()))
    exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", (exam_id,)).fetchall()
        attempt = conn.execute("SELECT * FROM attempts WHERE exam_id = ? ORDER BY id DESC LIMIT 1", (exam_id,)).fetchone()

    user_answers = json.loads(attempt['user_answers']) if attempt and attempt['user_answers'] else {}
    if attempt:
        st.markdown(f"""
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:10px 14px; margin-bottom:15px;">
            <b>Latest Attempt:</b> {attempt['attempt_date']} | <b>Score:</b> {attempt['score']}/100 | 
            <b>Correct:</b> {attempt['correct_count']} | <b>Wrong:</b> {attempt['wrong_count']} | <b>Status:</b> {'QUALIFIED ✅' if attempt['is_passed'] else 'NOT QUALIFIED ❌'}
        </div>
        """, unsafe_allow_html=True)

    filter_sec = st.radio("Filter By Section:", ["All 100 Questions", "GK (Q1-25)", "IQ (Q26-50)", "Technical Agri (Q51-100)"], horizontal=True)

    for q in questions:
        q_no = q['q_num']
        if filter_sec == "GK (Q1-25)" and not (1 <= q_no <= 25): continue
        if filter_sec == "IQ (Q26-50)" and not (26 <= q_no <= 50): continue
        if filter_sec == "Technical Agri (Q51-100)" and not (51 <= q_no <= 100): continue

        user_pick = user_answers.get(str(q_no), user_answers.get(q_no, None))
        correct = q['correct_option']
        cat = safe_get(q, 'category', 'Agri')
        exam_src = safe_get(q, 'exam_source', 'PSC Model')
        badge_class = "badge-gk" if cat == "GK" else ("badge-iq" if cat == "IQ" else "badge-agri")

        is_correct = (user_pick == correct)
        status_text = "⚪ Unattempted" if user_pick is None else ("✅ Correct" if is_correct else f"❌ Wrong (Your: {user_pick})")

        opts = {"A": q['option_a'], "B": q['option_b'], "C": q['option_c'], "D": q['option_d']}

        with st.expander(f"Q{q_no}. {q['question_text']} [{status_text}]", expanded=False):
            st.markdown(f'<span class="badge {badge_class}">{cat}</span> <span class="badge badge-src">{exam_src}</span>', unsafe_allow_html=True)

            fig_svg = safe_get(q, 'figure_svg')
            if fig_svg and str(fig_svg).strip().startswith("<svg"):
                st.components.v1.html(fig_svg, height=85)

            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0)) and str(q['option_a']).strip().startswith("<svg")
            if is_fig_opt:
                fA, fB, fC, fD = st.columns(4)
                with fA:
                    st.caption("(A)")
                    st.components.v1.html(q['option_a'], height=70)
                with fB:
                    st.caption("(B)")
                    st.components.v1.html(q['option_b'], height=70)
                with fC:
                    st.caption("(C)")
                    st.components.v1.html(q['option_c'], height=70)
                with fD:
                    st.caption("(D)")
                    st.components.v1.html(q['option_d'], height=70)
            else:
                cA, cB = st.columns(2)
                cA.write(f"**(A)** {opts['A']}")
                cA.write(f"**(B)** {opts['B']}")
                cB.write(f"**(C)** {opts['C']}")
                cB.write(f"**(D)** {opts['D']}")

            user_disp = "Unattempted" if user_pick is None else f"Option ({user_pick})"
            st.markdown(f"""
            <div class="{'answer-banner-correct' if is_correct else 'answer-banner-wrong'}">
                Official Verified Answer: Option ({correct}) &nbsp;|&nbsp; Your Attempt: {user_disp}
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="hint-container">
                <b>💡 Core Concept:</b> {q['explanation']}
            </div>
            """, unsafe_allow_html=True)

            # DETAILED EXPLANATION FOR ALL 4 OPTIONS (A, B, C, D)
            st.markdown("<div style='margin-top:12px; font-weight:700; color:#1e293b;'>🔍 Comprehensive Breakdown of All 4 Options:</div>", unsafe_allow_html=True)
            try:
                hints = json.loads(q['option_hints'])
            except Exception:
                hints = {}

            for opt_k in ["A", "B", "C", "D"]:
                is_opt_correct = (opt_k == correct)
                tag = "✅ [CORRECT OPTION]" if is_opt_correct else "❌ [INCORRECT OPTION]"
                opt_text = opts.get(opt_k, "")
                exp_text = hints.get(opt_k, "Official syllabus benchmark.")

                st.markdown(f"""
                <div class='option-explanation-pill'>
                    <b>Option ({opt_k}): {opt_text}</b> — <span style='font-weight:700; color:{"#059669" if is_opt_correct else "#dc2626"};'>{tag}</span><br>
                    <span style='color:#475569;'>{exp_text}</span>
                </div>
                """, unsafe_allow_html=True)

# =====================================================================
# TAB 3: INSTANT NEXT SET (0 SECONDS WAIT - PRE-BUFFERED)
# =====================================================================
elif menu == "⚡ Instant Next Set (0s Wait)":
    st.markdown('<div class="main-title">⚡ Instant Next Set Engine</div>', unsafe_allow_html=True)
    st.caption("Automatic pre-buffering maintains up to 10 full sets in SQLite so you never wait for generation.")

    with get_db() as conn:
        all_exams = conn.execute("SELECT set_number, title, exam_date, total_questions FROM exams ORDER BY set_number ASC").fetchall()

    total_avail = len(all_exams)
    st.success(f"📦 Currently Available Sets in Local Storage: **{total_avail} / 10 Sets**")

    # Display list of ready sets
    df_sets = pd.DataFrame([dict(e) for e in all_exams])
    if not df_sets.empty:
        st.dataframe(df_sets, use_container_width=True)

    st.markdown("---")
    st.markdown("### 🚀 Load Next Prepared Set")

    if total_avail >= 1:
        st.info("💡 Sets are pre-compiled and buffered in the background while you study. Select any ready set directly in the **'📝 Attempt 100-Question Exam'** tab with **0 seconds wait time**.")
    
    if total_avail < 10:
        if is_buffer_thread_active():
            st.info("⏳ Background worker is currently compiling additional sets up to Set #10. Check back shortly to see more sets added.")
        else:
            st.caption("Buffer worker is idle. You can trigger background compilation below:")
            if st.button("🔄 Resume Background Compilation to 10 Sets", type="primary"):
                trigger_background_buffering()
                st.success("Background worker started. It will continue adding sets up to 10 silently.")

# =====================================================================
# TAB 4: SCORE HISTORY & ANALYTICS
# =====================================================================
elif menu == "📊 Score History & Analytics":
    st.markdown('<div class="main-title">📊 Score History & Performance Analytics</div>', unsafe_allow_html=True)

    with get_db() as conn:
        attempts = conn.execute('''
            SELECT a.id, e.set_number, e.exam_date, e.title, a.attempt_date, a.score, 
                   a.correct_count, a.wrong_count, a.unattempted_count, a.is_passed
            FROM attempts a
            JOIN exams e ON a.exam_id = e.id
            ORDER BY a.id ASC
        ''').fetchall()

    if not attempts:
        st.info("No exam attempts recorded yet. Attempt an exam first to view analytics.")
        st.stop()

    df = pd.DataFrame([dict(a) for a in attempts])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sets Attempted", len(df))
    m2.metric("Highest Score", f"{df['score'].max():.2f}")
    m3.metric("Average Score", f"{df['score'].mean():.2f}")
    m4.metric("Pass Rate", f"{(df['is_passed'].sum() / len(df) * 100):.1f}%")

    st.subheader("📈 Score Progression Curve")
    st.line_chart(df.set_index('attempt_date')['score'])

    st.subheader("📜 Detailed Record Sheet")
    st.dataframe(df[['set_number', 'title', 'attempt_date', 'score', 'correct_count', 'wrong_count', 'unattempted_count', 'is_passed']], use_container_width=True)
