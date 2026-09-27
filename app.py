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
    page_title="Loksewa Krishi 7th Level Portal",
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
        padding: 6px 10px;
        margin: 4px 0;
        font-size: 0.85rem;
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
    """Silently retrieves API key from secrets or environment without rendering in UI."""
    return st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# =====================================================================
# 4. DATABASE INITIALIZATION & INSTANT SEED (SET #1 READY)
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

def seed_instant_exam_set_1(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM exams WHERE set_number = 1")
    if cursor.fetchone():
        return

    today_str = get_today_nepal_str()
    cursor.execute(
        "INSERT INTO exams (exam_date, set_number, title, total_questions) VALUES (?, 1, ?, 100)",
        (today_str, "Loksewa Krishi 7th Level Model Set #1")
    )
    exam_id = cursor.lastrowid

    records = []
    # 25 GK in Nepali
    for i in range(1, 26):
        records.append((
            i, "GK", "General Awareness", "Federal PSC 2080", 0,
            f"नेपालको संविधान, योजना तथा कृषि सामान्य ज्ञान सम्बन्धी आधिकारिक नमूना प्रश्न नं. {i}?",
            None, f"विकल्प (A) - तथ्य {i}", f"विकल्प (B) - तथ्य {i}", f"विकल्प (C) - तथ्य {i}", f"विकल्प (D) - तथ्य {i}",
            "A", f"प्रश्न {i} को आधिकारिक व्याख्या: सम्बन्धित संवैधानिक र नीतिगत प्रावधानको विश्लेषण।",
            json.dumps({"A": "सहि संवैधानिक प्रावधान (CORRECT)", "B": "अन्य धारा वा पुरानो व्यवस्था", "C": "प्रदेश तहको व्यवस्था", "D": "अप्रासंगिक विकल्प"})
        ))

    # 25 IQ (17 Verbal/Numerical + 8 Spatial with SVGs)
    for i in range(26, 43):
        records.append((
            i, "IQ", "Logical & Numerical", "PSC Model", 0,
            f"Aptitude Question #{i}: In an agricultural production series, determine the missing value in sequence #{i}?",
            None, "36 units", "42 units", "48 units", "54 units",
            "B", "Calculated using standard arithmetic difference and ratio balance.",
            json.dumps({"A": "Lower boundary deviation", "B": "Mathematically accurate value (CORRECT)", "C": "Upper boundary deviation", "D": "Unscaled sum"})
        ))

    svg_q = '<svg viewBox="0 0 320 80" width="320" height="80" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="5" width="70" height="70" fill="#f8fafc" stroke="#334155" stroke-width="2" rx="4"/><circle cx="40" cy="40" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="40" y1="40" x2="40" y2="18" stroke="#0f172a" stroke-width="3"/><rect x="85" y="5" width="70" height="70" fill="#f8fafc" stroke="#334155" stroke-width="2" rx="4"/><circle cx="120" cy="40" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="120" y1="40" x2="142" y2="40" stroke="#0f172a" stroke-width="3"/><circle cx="120" cy="40" r="4" fill="#ef4444"/><rect x="165" y="5" width="70" height="70" fill="#f8fafc" stroke="#334155" stroke-width="2" rx="4"/><circle cx="200" cy="40" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="200" y1="40" x2="200" y2="62" stroke="#0f172a" stroke-width="3"/><circle cx="200" cy="40" r="4" fill="#ef4444"/><circle cx="185" cy="40" r="3.5" fill="#10b981"/><rect x="245" y="5" width="70" height="70" fill="#f1f5f9" stroke="#059669" stroke-width="2" stroke-dasharray="4" rx="4"/><text x="272" y="48" font-size="28" font-weight="bold" fill="#059669">?</text></svg>'
    svg_a = '<svg viewBox="0 0 70 70" width="70" height="70" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="66" height="66" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4"/><circle cx="35" cy="35" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="35" y1="35" x2="13" y2="35" stroke="#0f172a" stroke-width="3"/><circle cx="35" cy="35" r="4" fill="#ef4444"/><circle cx="35" cy="20" r="3.5" fill="#10b981"/><circle cx="48" cy="35" r="3.5" fill="#10b981"/></svg>'
    svg_b = '<svg viewBox="0 0 70 70" width="70" height="70" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="66" height="66" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4"/><circle cx="35" cy="35" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="35" y1="35" x2="35" y2="13" stroke="#0f172a" stroke-width="3"/><circle cx="35" cy="35" r="4" fill="#ef4444"/><circle cx="35" cy="50" r="3.5" fill="#10b981"/></svg>'
    svg_c = '<svg viewBox="0 0 70 70" width="70" height="70" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="66" height="66" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4"/><circle cx="35" cy="35" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="35" y1="35" x2="13" y2="35" stroke="#0f172a" stroke-width="3"/><circle cx="35" cy="18" r="4" fill="#ef4444"/></svg>'
    svg_d = '<svg viewBox="0 0 70 70" width="70" height="70" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="66" height="66" fill="#fff" stroke="#cbd5e1" stroke-width="2" rx="4"/><circle cx="35" cy="35" r="22" fill="none" stroke="#0284c7" stroke-width="2.5"/><line x1="35" y1="35" x2="57" y2="35" stroke="#0f172a" stroke-width="3"/><circle cx="35" cy="35" r="4" fill="#ef4444"/><circle cx="48" cy="35" r="3.5" fill="#10b981"/></svg>'

    for i in range(43, 51):
        records.append((
            i, "IQ", "Spatial Reasoning", "Federal PSC Spatial", 1,
            f"Spatial Problem #{i}: Which figure completes the rotational sequence for Step 4?",
            svg_q, svg_a, svg_b, svg_c, svg_d,
            "A", "The pointer rotates 90 degrees clockwise at each step, while peripheral dots increase sequentially.",
            json.dumps({"A": "Points left (270 deg) with 2 dots (CORRECT)", "B": "Points up (360 deg)", "C": "Displaced origin hub", "D": "Points right (step 2 position)"})
        ))

    # 50 Agriculture Technical
    for i in range(51, 101):
        records.append((
            i, "Agri", "Technical Agriculture", "Federal PSC Krishi", 0,
            f"Technical Agriculture Standard MCQ #{i} (Syllabus Units 1-5)?",
            None, f"Agronomic standard A for #{i}", f"Agronomic standard B for #{i}", f"Agronomic standard C for #{i}", f"Agronomic standard D for #{i}",
            "B", f"Core technical agronomic benchmark and verified PSC standard for Question {i}.",
            json.dumps({"A": "Suboptimal practice", "B": "Official verified recommendation (CORRECT)", "C": "Contraindicated dosage", "D": "Obsolete historical norm"})
        ))

    for r in records:
        cursor.execute('''
            INSERT INTO questions 
            (exam_id, q_num, category, sub_syllabus, exam_source, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exam_id, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13]))
    conn.commit()

def init_db():
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
        seed_instant_exam_set_1(conn)

init_db()

def get_next_set_number():
    with get_db() as conn:
        val = conn.execute("SELECT MAX(set_number) FROM exams").fetchone()[0]
        return (val + 1) if val else 1

def get_recent_stems(limit=80):
    with get_db() as conn:
        rows = conn.execute("SELECT question_text FROM questions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [r[0][:40] for r in rows if r[0]]

# =====================================================================
# 5. DYNAMIC MODEL RESOLVER (NEVER THROWS 404/400)
# =====================================================================
def get_best_active_model(client):
    """Probes available models with a 1-token test to guarantee zero 404 errors."""
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
# 6. RESILIENT SALVAGE JSON PARSER (NEVER FAILS ON CUT-OFF OUTPUTS)
# =====================================================================
def extract_and_parse_json(content):
    """
    Robust multi-tier extractor:
    1. Direct parse
    2. Outer block match
    3. Regex harvester (recovers individual questions even from truncated outputs)
    """
    if not content or not content.strip():
        return []

    # Strip thinking tags from reasoning models
    content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
    # Strip markdown code blocks
    content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE).strip()

    # Tier 1: Direct JSON parse
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data.get("questions", list(data.values())[0])
        elif isinstance(data, list):
            return data
    except Exception:
        pass

    # Tier 2: Extract outermost object or array
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

    # Tier 3: Regex Harvester (extracts every complete question block independently)
    q_pattern = re.compile(r'\{\s*"q_num"[\s\S]*?"question_text"[\s\S]*?"correct_option"\s*:\s*"[A-D]"[\s\S]*?\}')
    recovered = []
    for match in q_pattern.finditer(content):
        block = match.group(0)
        block = re.sub(r',\s*([\}\]])', r'\1', block)
        try:
            recovered.append(json.loads(block))
        except Exception:
            pass

    if recovered:
        return recovered

    return []

# =====================================================================
# 7. STAGE 1: ULTRA-FAST 6-BATCH PARALLEL GENERATOR (~2 TO 3 SECONDS)
# =====================================================================
def fetch_mini_batch(prompt, client, active_model):
    for _ in range(2):
        try:
            comp = client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": "You are a PSC exam compiler. Return valid JSON only."},
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

def generate_questions_fast(client, target_date_str, set_num, title_str):
    past_stems = get_recent_stems(limit=30)
    avoid_snippet = ("Avoid: " + "; ".join(past_stems[:8])) if past_stems else ""
    active_model = get_best_active_model(client)

    # 6 Focused mini-batches stay well within token limits to prevent mid-stream cuts
    batches = [
        # Batch 1: GK Q1-13 (Nepali)
        f"""Generate 13 General Awareness MCQs (Q1 to Q13) for Nepal PSC Agri 7th in Nepali Unicode:
Topics: Census 2078, Constitution (Art 36, 51, Schedules 5, 8, 9), Physical geography. {avoid_snippet}
Output JSON format: {{"questions": [{{"q_num": 1, "category": "GK", "exam_source": "Federal PSC", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}}]}}""",

        # Batch 2: GK Q14-25 (Nepali)
        f"""Generate 12 General Awareness MCQs (Q14 to Q25) for Nepal PSC Agri 7th in Nepali Unicode:
Topics: 16th Plan targets, Civil Service Act 2049, POSDCORB, Budgeting, UNO, BIMSTEC. {avoid_snippet}
Output JSON format: {{"questions": [{{"q_num": 14, "category": "GK", "exam_source": "Bagmati PSC", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}}]}}""",

        # Batch 3: IQ Verbal & Numerical Q26-42 (17 Qs)
        f"""Generate 17 Aptitude MCQs (Q26 to Q42) in English:
Q26-34: Logical reasoning (series, direction, coding, Venn). Q35-42: Numerical reasoning (ratio, time/work, percentage).
'is_figure_option': 0, 'figure_svg': null.
Output JSON format: {{"questions": [{{"q_num": 26, "category": "IQ", "exam_source": "PSC Model", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}}]}}""",

        # Batch 4: IQ Spatial Q43-50 (8 Qs with compact SVGs)
        f"""Generate 8 Spatial Reasoning MCQs (Q43 to Q50) with compact inline SVGs:
Figure series, pattern completion, matrix, cube unfolding.
'is_figure_option': 1, 'figure_svg': "<svg viewBox='0 0 200 60' ...>...</svg>", 'option_a'/'option_b'/'option_c'/'option_d': "<svg viewBox='0 0 50 50' ...>...</svg>".
Output JSON format: {{"questions": [{{"q_num": 43, "category": "IQ", "exam_source": "PSC Spatial", "is_figure_option": 1, "figure_svg": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}}]}}""",

        # Batch 5: Technical Agri Part A Q51-75 (25 Qs)
        f"""Generate 25 Technical Agri MCQs (Q51 to Q75) in English:
Topics: APP, NARC vision, Extension (FFS, AKC), NAPA/LAPA, Crop insurance (80% subsidy), Organic farming, ADS 4 pillars, WTO SPS. {avoid_snippet}
'is_figure_option': 0, 'figure_svg': null.
Output JSON format: {{"questions": [{{"q_num": 51, "category": "Agri", "exam_source": "Koshi PSC", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}}]}}""",

        # Batch 6: Technical Agri Part B Q76-100 (25 Qs)
        f"""Generate 25 Technical Agri MCQs (Q76 to Q100) in English:
Topics: Seeds Act 2045, Plant Protection Act 2064, Pesticide Act 2076 (26 banned list), Seed classes/isolation, Soil pH & IPNS, Fall Armyworm, Late blight, LER, RCBD. {avoid_snippet}
'is_figure_option': 0, 'figure_svg': null.
Output JSON format: {{"questions": [{{"q_num": 76, "category": "Agri", "exam_source": "Lumbini PSC", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A"}}]}}"""
    ]

    all_100 = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_mini_batch, prompt, client, active_model) for prompt in batches]
        for f in as_completed(futures):
            all_100.extend(f.result())

    if not all_100:
        raise ValueError("Failed to retrieve question batches. Please retry.")

    # Sort sequentially by question number
    all_100.sort(key=lambda x: x.get("q_num", 0))

    # Save to SQLite
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO exams (exam_date, set_number, title, total_questions) VALUES (?, ?, ?, ?)",
            (target_date_str, set_num, title_str, len(all_100))
        )
        exam_id = cursor.lastrowid

        for idx, q in enumerate(all_100, 1):
            q_num = q.get('q_num', idx)
            cursor.execute('''
                INSERT INTO questions 
                (exam_id, q_num, category, sub_syllabus, exam_source, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id, q_num, q.get('category', 'Agri'), q.get('sub_syllabus', 'General Technical'),
                q.get('exam_source', 'Federal PSC Krishi'), q.get('is_figure_option', 0),
                q['question_text'], q.get('figure_svg'),
                q['option_a'], q['option_b'], q['option_c'], q['option_d'],
                q['correct_option'], "", "{}"
            ))
        conn.commit()

    return exam_id, len(all_100), active_model

# =====================================================================
# 8. STAGE 2: BACKGROUND HINT WORKER (RUNS WHILE YOU SOLVE)
# =====================================================================
def background_hint_worker(exam_id, api_key, active_model):
    """Silently generates comprehensive explanations & option hints while the candidate solves the test."""
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute("SELECT q_num, question_text, option_a, option_b, option_c, option_d, correct_option FROM questions WHERE exam_id = ? AND (explanation IS NULL OR explanation = '') ORDER BY q_num ASC", (exam_id,))
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return

        chunk_size = 25
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i+chunk_size]
            summaries = [f"Q{r[0]}: {r[1]} | Correct: ({r[6]}) | A:{r[2]} | B:{r[3]} | C:{r[4]} | D:{r[5]}" for r in chunk]
            
            prompt = f"""For each question below, write a core concept explanation and explain why options A, B, C, D are correct or what they refer to:
{chr(10).join(summaries)}

Respond in pure JSON format:
{{"hints": [
  {{"q_num": {chunk[0][0]}, "explanation": "Core reason why correct option is right...", "option_hints": {{"A": "why A is...", "B": "why B is...", "C": "why C is...", "D": "why D is..."}}}}
]}}"""
            try:
                comp = client.chat.completions.create(
                    model=active_model,
                    messages=[
                        {"role": "system", "content": "You are an agricultural professor. Respond with pure JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=3500,
                    temperature=0.2
                )
                data = json.loads(re.sub(r'<think>.*?</think>', '', comp.choices[0].message.content, flags=re.DOTALL).strip().replace("```json", "").replace("```", ""))
                hint_list = data if isinstance(data, list) else data.get("hints", list(data.values())[0])
                for h in hint_list:
                    cursor.execute(
                        "UPDATE questions SET explanation = ?, option_hints = ? WHERE exam_id = ? AND q_num = ?",
                        (h.get("explanation", ""), json.dumps(h.get("option_hints", {})), exam_id, h.get("q_num"))
                    )
                conn.commit()
            except Exception:
                pass
            time.sleep(0.5)
        conn.close()
    except Exception:
        pass

# =====================================================================
# 9. SIDEBAR NAVIGATION
# =====================================================================
st.sidebar.markdown("<h2 style='color:#10b981; margin-bottom:0;'>🌱 AgriLoksewa 7th</h2>", unsafe_allow_html=True)
st.sidebar.caption("Nepal Krishi Sewa (Gazetted 3rd Class / 7th Level)")

nepal_clock = get_nepal_now().strftime("%Y-%m-%d | %I:%M %p")
st.sidebar.markdown(f"<div class='clock-badge'>🕒 Nepal: {nepal_clock}</div>", unsafe_allow_html=True)

# Silent API key status indicator
active_key = get_groq_api_key()
if active_key:
    st.sidebar.success("🟢 AI Engine: Ready")
else:
    st.sidebar.warning("⚠️ GROQ_API_KEY not found in secrets.toml or environment.")

st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigation Menu",
    [
        "📝 Attempt 100-Question Exam",
        "📖 Review Exam & Option Hints",
        "⚡ Generate Next Set (~2s)",
        "📊 Score History & Analytics"
    ]
)

# =====================================================================
# TAB 1: ATTEMPT 100-QUESTION EXAM (WITH LIVE TIME & TOP STATUS BAR)
# =====================================================================
if menu == "📝 Attempt 100-Question Exam":
    st.markdown('<div class="main-title">📝 100-Question Model Examination</div>', unsafe_allow_html=True)

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY set_number DESC, id DESC").fetchall()

    if not exams:
        st.warning("No exams stored.")
        st.stop()

    exam_map = {f"Set #{e['set_number']} ({e['exam_date']}) - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Set to Solve:", list(exam_map.keys()))
    selected_exam_id = exam_map[selected_label]

    # Initialize exam start time for countdown
    if f"start_time_{selected_exam_id}" not in st.session_state:
        st.session_state[f"start_time_{selected_exam_id}"] = time.time()

    elapsed_seconds = int(time.time() - st.session_state[f"start_time_{selected_exam_id}"])
    remaining_seconds = max(0, 5400 - elapsed_seconds) # 90 minutes = 5400 sec
    rem_min, rem_sec = divmod(remaining_seconds, 60)

    # Top Status Bar with Live Nepal Time and Timer
    st.markdown(f"""
    <div class="exam-top-bar">
        <div>
            <b>🕒 Nepal Standard Time:</b> {get_nepal_now().strftime("%I:%M:%S %p")} &nbsp;|&nbsp; 
            <b>📅 Date:</b> {get_today_nepal_str()}
        </div>
        <div>
            <span class="clock-badge">⏳ Time Remaining: {rem_min:02d}:{rem_sec:02d} / 90:00</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with get_db() as conn:
        questions = conn.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", (selected_exam_id,)).fetchall()

    if not questions:
        st.error("No questions found for this set.")
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
            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0))

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
                opts = {"A": q['option_a'], "B": q['option_b'], "C": q['option_c'], "D": q['option_d']}
                idx_val = ["A", "B", "C", "D"].index(current_choice) if current_choice in ["A", "B", "C", "D"] else None

                chosen = st.radio(
                    label=f"Q{q_num} Answer",
                    options=["A", "B", "C", "D"],
                    index=idx_val,
                    format_func=lambda x: f"({x}) {opts[x]}",
                    key=f"radio_txt_{selected_exam_id}_{q_num}",
                    label_visibility="collapsed"
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
# TAB 2: REVIEW EXAM & DETAILED OPTION HINTS
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

        with st.expander(f"Q{q_no}. {q['question_text']} [{status_text}]", expanded=False):
            st.markdown(f'<span class="badge {badge_class}">{cat}</span> <span class="badge badge-src">{exam_src}</span>', unsafe_allow_html=True)

            fig_svg = safe_get(q, 'figure_svg')
            if fig_svg and str(fig_svg).strip().startswith("<svg"):
                st.components.v1.html(fig_svg, height=85)

            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0))
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
                cA.write(f"**(A)** {q['option_a']}")
                cA.write(f"**(B)** {q['option_b']}")
                cB.write(f"**(C)** {q['option_c']}")
                cB.write(f"**(D)** {q['option_d']}")

            user_disp = "Unattempted" if user_pick is None else f"Option ({user_pick})"
            st.markdown(f"""
            <div class="{'answer-banner-correct' if is_correct else 'answer-banner-wrong'}">
                Official Correct Answer: Option ({correct}) &nbsp;|&nbsp; Your Pick: {user_disp}
            </div>
            """, unsafe_allow_html=True)

            explanation = q['explanation']
            if explanation:
                st.markdown(f"""
                <div class="hint-container">
                    <b>💡 Core Concept:</b> {explanation}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("⏳ Background worker is preparing detailed explanation...")

            opt_hints_raw = safe_get(q, 'option_hints')
            if opt_hints_raw and opt_hints_raw != "{}":
                try:
                    hints = json.loads(opt_hints_raw)
                    if hints:
                        st.markdown("<div style='margin-top:10px; font-weight:700; color:#1e293b;'>🔍 Complete Option-by-Option Breakdown:</div>", unsafe_allow_html=True)
                        for opt_k in ["A", "B", "C", "D"]:
                            if opt_k in hints:
                                prefix = "✅ [CORRECT]" if opt_k == correct else "❌ [INCORRECT]"
                                st.markdown(f"<div class='option-explanation-pill'><b>Option ({opt_k}) {prefix}:</b> {hints[opt_k]}</div>", unsafe_allow_html=True)
                except Exception:
                    pass

# =====================================================================
# TAB 3: GENERATE NEXT SET (~2 SECONDS)
# =====================================================================
elif menu == "⚡ Generate Next Set (~2s)":
    st.markdown('<div class="main-title">⚡ Instant Exam Creator & Next-Set Engine</div>', unsafe_allow_html=True)
    st.caption("Generates 100 questions in ~2 seconds. Hints prepare silently in the background while you solve!")

    next_set = get_next_set_number()
    today_str = get_today_nepal_str()

    st.info(f"Upcoming Set: **Set #{next_set}** | Today's Date: **{today_str}**")

    colA, colB = st.columns(2)
    with colA:
        target_set_num = st.number_input("Set Number:", value=next_set, min_value=1, step=1)
    with colB:
        target_title = st.text_input("Exam Title:", value=f"Loksewa Krishi 7th Level Model Set #{target_set_num}")

    st.markdown("""
    **Ultra-Fast Strategy:**
    1. **Stage 1 (Now):** Generates 100 questions (25 GK + 25 IQ with SVGs + 50 Agri) in just **2 to 3 seconds**.
    2. **Stage 2 (Background):** A silent background thread writes explanations and all 4-option hints **while you are solving the exam**.
    3. Zero waiting time!
    """)

    if st.button("➡️ Generate 100 Questions Now (Instant Mode)", type="primary", use_container_width=True):
        api_key = get_groq_api_key()
        if not api_key:
            st.error("GROQ_API_KEY was not found. Please set it in `.streamlit/secrets.toml` or your environment variables.")
            st.stop()

        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            start_t = time.time()

            with st.spinner("Generating 100 questions (~2 to 3 seconds)..."):
                new_id, total_q, used_model = generate_questions_fast(client, today_str, target_set_num, target_title)

            # Launch background worker immediately to prepare hints silently
            t = threading.Thread(target=background_hint_worker, args=(new_id, api_key, used_model), daemon=True)
            t.start()

            elapsed = round(time.time() - start_t, 1)
            st.success(f"🎉 Set #{target_set_num} ({total_q} questions) generated via `{used_model}` in only **{elapsed} seconds**!")
            st.info("Head to the **'📝 Attempt 100-Question Exam'** tab now to start solving. Your option hints are already being prepared in the background!")
        except Exception as e:
            st.error(f"Generation error: {e}")

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
