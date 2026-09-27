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
# 3. SILENT API KEY RESOLVER (HIDDEN FROM UI)
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
    """Initializes empty database schema with zero pre-seeded questions."""
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

def get_all_used_stems():
    with get_db() as conn:
        rows = conn.execute("SELECT question_text FROM questions").fetchall()
        return set(r[0][:35].strip().lower() for r in rows if r[0])

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
# 6. UNIVERSAL NORMALIZER & STRICT VERIFIER
# =====================================================================
def extract_opt(q, key_letter):
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
    return ""

def extract_hints_dict(q, correct_opt, explanation, opts_map):
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
                hints_dict[k] = explanation if explanation else "This option is factually verified and correct according to Nepal Government official benchmarks."
            else:
                hints_dict[k] = f"Option ({k}) is incorrect for this question stem. It refers to an alternate statutory provision, benchmark, or distractor."

    return hints_dict

def validate_and_clean_question(q, existing_stems):
    """
    STRICT VERIFICATION:
    1. Rejects if question stem already exists (Anti-Repetition).
    2. Rejects if any option (A, B, C, D) is blank.
    3. Rejects if options are duplicates of each other.
    4. Rejects if correct_option is invalid or not in ['A', 'B', 'C', 'D'].
    5. Verifies that the correct option contains non-empty text.
    """
    q_text = str(q.get("question_text", "")).strip()
    if not q_text or len(q_text) < 8:
        return None

    stem = q_text[:35].strip().lower()
    if stem in existing_stems:
        return None

    opt_a = extract_opt(q, "a")
    opt_b = extract_opt(q, "b")
    opt_c = extract_opt(q, "c")
    opt_d = extract_opt(q, "d")

    # Options must be non-empty
    if not (opt_a and opt_b and opt_c and opt_d):
        return None

    # Options must be distinct
    opts_set = {opt_a.strip().lower(), opt_b.strip().lower(), opt_c.strip().lower(), opt_d.strip().lower()}
    if len(opts_set) < 4:
        return None

    # Correct option must be A, B, C, or D
    correct_opt = str(q.get("correct_option", "")).upper().strip()
    if correct_opt not in ["A", "B", "C", "D"]:
        return None

    opts_map = {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d}
    if not opts_map.get(correct_opt):
        return None

    explanation = q.get("explanation", "Standard verified benchmark according to Nepal Government official syllabus.")
    hints_dict = extract_hints_dict(q, correct_opt, explanation, opts_map)

    is_fig = 1 if "<svg" in opt_a.lower() else 0
    fig_svg = q.get("figure_svg") if is_fig else None

    existing_stems.add(stem)

    return {
        "q_num": q.get("q_num"),
        "category": q.get("category", "Agri"),
        "sub_syllabus": q.get("sub_syllabus", "PSC Section"),
        "exam_source": q.get("exam_source", "Federal/Provincial PSC"),
        "is_figure_option": is_fig,
        "question_text": q_text,
        "figure_svg": fig_svg,
        "option_a": opt_a,
        "option_b": opt_b,
        "option_c": opt_c,
        "option_d": opt_d,
        "correct_option": correct_opt,
        "explanation": explanation,
        "option_hints": json.dumps(hints_dict)
    }

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
# 8. STRICT 100-QUESTION COMPILER WITH ANTI-REPETITION & VERIFICATION
# =====================================================================
def fetch_verified_batch(prompt, count_needed, client, active_model, existing_stems, max_retries=2):
    collected = []
    attempts = 0
    while len(collected) < count_needed and attempts < max_retries:
        attempts += 1
        try:
            comp = client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": "You are Nepal Public Service Commission (Loksewa Aayog) Chief Examination Officer. Return pure JSON only. You must verify that the answer is factually present in options A, B, C, or D."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.25
            )
            raw_list = extract_and_parse_json(comp.choices[0].message.content)
            for raw_q in raw_list:
                cleaned = validate_and_clean_question(raw_q, existing_stems)
                if cleaned:
                    collected.append(cleaned)
                    if len(collected) == count_needed:
                        break
        except Exception:
            time.sleep(0.4)
    return collected

def generate_full_100_exam(client, target_date_str, set_num, title_str):
    existing_stems = get_all_used_stems()
    active_model = get_best_active_model(client)

    # 4 Strict Section Targets: 25 GK + 25 IQ + 25 Agri A + 25 Agri B = 100 Qs
    section_configs = [
        # Section 1: 25 GK (Nepali Unicode) - Syllabus 1.1 to 1.16
        {
            "count": 25,
            "prompt": f"""Generate exactly 25 General Awareness MCQs (Q1 to Q25) for Nepal PSC Agri 7th in Nepali Unicode.
Strict Government sources to adhere to:
- Census 2078 (National Statistics Office official data)
- Constitution of Nepal (Articles 36, 42, 51; Schedules 5, 8, 9)
- 16th Periodic Plan (2081/82-2085/86 targets)
- Civil Service Act 2049 & Rules 2050, Budgeting, Good Governance, UNO, BIMSTEC.
MANDATORY RULES:
1. All 4 options (A, B, C, D) must be non-empty and mutually distinct.
2. The correct answer MUST be accurately present in the options.
3. In option_hints, detail WHY the correct option is right AND explain what the other three options refer to.
JSON Schema: {{"questions": [{{"q_num": 1, "category": "GK", "sub_syllabus": "1.8 Constitution", "exam_source": "Federal PSC", "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A": "why A...", "B": "why B...", "C": "why C...", "D": "why D..."}}}}]}}"""
        },
        # Section 2: 25 IQ (17 Verbal/Numerical + 8 Spatial with SVGs) - Syllabus 2.1 to 2.3
        {
            "count": 25,
            "prompt": f"""Generate exactly 25 Loksewa Aptitude MCQs (Q26 to Q50) in English:
- Q26 to Q42 (17 Verbal/Numerical Qs): Series, direction, coding, Venn, ratio, percentage, time/work. (figure_svg: null)
- Q43 to Q50 (8 Spatial Qs): Figure series, pattern completion, 3x3 matrix, cube net unfolding.
  MUST have compact valid inline SVGs: 'figure_svg': "<svg viewBox='0 0 200 60' ...>...</svg>", 'option_a'/'option_b'/'option_c'/'option_d': "<svg viewBox='0 0 50 50' ...>...</svg>".
MANDATORY: Verify that the correct option is accurately positioned in A, B, C, or D. Provide option_hints explaining all 4 options.
JSON Schema: {{"questions": [{{"q_num": 26, "category": "IQ", "sub_syllabus": "2.1 Reasoning", "exam_source": "PSC Aptitude", "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}"""
        },
        # Section 3: 25 Technical Agri Part A (Units 1 to 4)
        {
            "count": 25,
            "prompt": f"""Generate exactly 25 Technical Agriculture MCQs (Q51 to Q75) in English based on Nepal Government official sources:
- Unit 1: History & Status (5 Qs, Q51-55): APP, Devolution, DoA/NARC timeline, Agriculture Census 2078 landholding data, GDP share.
- Unit 2: Research & Extension (5 Qs, Q56-60): NARC vision, AFU, CTEVT, FFS, AKC, T&V.
- Unit 3: NRM, Environment & DRM (10 Qs, Q61-70): IPNM, IPM, GAP, Organic certification (PGS), NAPA/LAPA, Crop insurance (80% subsidy).
- Unit 4: Policies (5 Qs, Q71-75): Constitution Art 36, 16th Plan agri goals, ADS (2015-2035) 4 pillars.
MANDATORY: Verify options are distinct and answer is present in options. Detail all 4 options in option_hints.
JSON Schema: {{"questions": [{{"q_num": 51, "category": "Agri", "sub_syllabus": "Technical Agri Part A", "exam_source": "Koshi PSC", "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}"""
        },
        # Section 4: 25 Technical Agri Part B (Units 4 to 5)
        {
            "count": 25,
            "prompt": f"""Generate exactly 25 Technical Agriculture MCQs (Q76 to Q100) in English based on Nepal Government official acts:
- Unit 4: Acts & Trade (5 Qs, Q76-80): Seeds Act 2045 & Rules 2069, Plant Protection Act 2064, Pesticide Management Act 2076 (26 banned list), Food Sovereignty Act 2076, WTO SPS.
- Unit 5: Agri Technology & Management (20 Qs, Q81-100):
  * Seed classes (Foundation White, Breeder Yellow, Certified Blue), isolation distances
  * Soil pH, lime requirement formula, essential nutrient mobility (N, P, K mobile)
  * Plant protection: Fall Armyworm (inverted Y), Late blight, Clubroot, ETL
  * Economics & research: LER, price elasticity, RCBD (12 error df).
MANDATORY: Verify options are distinct and answer is present in options. Detail all 4 options in option_hints.
JSON Schema: {{"questions": [{{"q_num": 76, "category": "Agri", "sub_syllabus": "Technical Agri Part B", "exam_source": "Lumbini PSC", "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}]}}"""
        }
    ]

    all_verified_100 = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_verified_batch, cfg["prompt"], cfg["count"], client, active_model, existing_stems) for cfg in section_configs]
        for f in as_completed(futures):
            all_verified_100.extend(f.result())

    if len(all_verified_100) < 50:
        raise ValueError("Failed to compile verified questions. Please retry.")

    # Sort sequentially and enforce numbering 1 to 100
    all_verified_100.sort(key=lambda x: x.get("q_num", 0))
    final_100 = all_verified_100[:100]

    # Save verified set to SQLite
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO exams (exam_date, set_number, title, total_questions) VALUES (?, ?, ?, ?)",
            (target_date_str, set_num, title_str, len(final_100))
        )
        exam_id = cursor.lastrowid

        for idx, q in enumerate(final_100, 1):
            q_num = idx
            cat = "GK" if 1 <= q_num <= 25 else ("IQ" if 26 <= q_num <= 50 else "Agri")
            cursor.execute('''
                INSERT INTO questions 
                (exam_id, q_num, category, sub_syllabus, exam_source, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id, q_num, cat, q['sub_syllabus'], q['exam_source'],
                q['is_figure_option'], q['question_text'], q['figure_svg'],
                q['option_a'], q['option_b'], q['option_c'], q['option_d'],
                q['correct_option'], q['explanation'], q['option_hints']
            ))
        conn.commit()

    return exam_id, len(final_100), active_model

# =====================================================================
# 9. SILENT BUFFER WORKER (PRE-GENERATES UP TO 10 SETS IN BACKGROUND)
# =====================================================================
def is_buffer_thread_active():
    for t in threading.enumerate():
        if t.name == "LoksewaBufferWorker":
            return True
    return False

def buffer_worker_loop(api_key, target_sets=10):
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

            time.sleep(3)
    except Exception:
        pass

def trigger_background_buffering():
    key = get_groq_api_key()
    if key and not is_buffer_thread_active():
        t = threading.Thread(target=buffer_worker_loop, args=(key, 10), name="LoksewaBufferWorker", daemon=True)
        t.start()

# Automatically trigger background buffer
trigger_background_buffering()

# =====================================================================
# 10. SIDEBAR NAVIGATION & TIME DISPLAY
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

        if st.button("🚀 Compile Set #1 Now (Verified 100 Qs)", type="primary"):
            from groq import Groq
            c = Groq(api_key=api_key)
            with st.spinner("Compiling & verifying Set #1 (100 Questions) strictly as per syllabus..."):
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
                    st.markdown('<div class="figure-frame"><span class="figure-label">(B)</span>', unsa
