import streamlit as st
import sqlite3
import json
import re
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
# 2. EYE-CATCHY CUSTOM CSS
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
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }
    
    .clock-badge {
        background: #0f172a;
        color: #38bdf8;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 12px;
        border: 1px solid #1e293b;
    }
    
    .question-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-top: 1rem;
        margin-bottom: 0.8rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
    }
    
    .badge {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
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
        padding: 8px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .figure-frame:hover {
        border-color: #10b981;
        background: #f0fdf4;
    }
    .figure-label {
        font-weight: 800;
        font-size: 0.92rem;
        color: #0f172a;
        margin-bottom: 4px;
        display: block;
    }
    
    .answer-banner-correct {
        background: #ecfdf5;
        border-left: 5px solid #10b981;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 10px 0;
        color: #065f46;
        font-weight: 700;
    }
    .answer-banner-wrong {
        background: #fff1f2;
        border-left: 5px solid #f43f5e;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 10px 0;
        color: #9f1239;
        font-weight: 700;
    }
    .hint-container {
        background: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        border-radius: 6px;
        margin-top: 10px;
    }
    .option-explanation-pill {
        background: #ffffff;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        padding: 8px 12px;
        margin: 6px 0;
        font-size: 0.88rem;
        color: #334155;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DB_FILE = "loksewa_agri_7th.db"

# =====================================================================
# 3. DATABASE INITIALIZATION & ANTI-REPETITION LOGIC
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

def get_recent_question_stems(limit=250):
    with get_db() as conn:
        rows = conn.execute("SELECT question_text FROM questions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [r[0][:45] for r in rows if r[0]]

def get_next_set_number():
    with get_db() as conn:
        val = conn.execute("SELECT MAX(set_number) FROM exams").fetchone()[0]
        return (val + 1) if val else 1

# =====================================================================
# 4. ROBUST JSON PARSER
# =====================================================================
def extract_and_parse_json(content):
    content = content.strip()
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data.get("questions", list(data.values())[0])
        elif isinstance(data, list):
            return data
    except Exception:
        pass

    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data.get("questions", list(data.values())[0])
            elif isinstance(data, list):
                return data
        except Exception:
            pass
    raise ValueError("Could not parse valid JSON from AI response.")

# =====================================================================
# 5. LIVE PROBE AUTO-MODEL RESOLVER (NEVER FAILS)
# =====================================================================
def find_working_model(client):
    """
    Dynamically probes active models on your Groq key.
    Automatically picks the fastest verified model without terms restrictions.
    """
    if "verified_groq_model" in st.session_state and st.session_state["verified_groq_model"]:
        return st.session_state["verified_groq_model"]

    candidate_priority = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "gemma2-9b-it",
        "mixtral-8x7b-32768"
    ]

    try:
        m_list = client.models.list()
        active_ids = [
            m.id for m in m_list.data 
            if not any(x in m.id.lower() for x in ["whisper", "embed", "guard", "vision", "canopylabs", "orpheus"])
        ]
        test_queue = [m for m in candidate_priority if m in active_ids] + [m for m in active_ids if m not in candidate_priority]
    except Exception:
        test_queue = candidate_priority

    # Quick 1-token probe test to verify permission
    for m in test_queue:
        try:
            client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=2
            )
            st.session_state["verified_groq_model"] = m
            return m
        except Exception:
            continue

    return "llama-3.1-8b-instant"

# =====================================================================
# 6. FAST 4-THREAD PARALLEL GENERATOR (ALL 100 QUESTIONS)
# =====================================================================
def fetch_single_batch(batch_idx, batch_data, client, avoid_snippet, active_model):
    prompt = batch_data["prompt"].replace("{{avoid_snippet}}", avoid_snippet)
    for attempt in range(2):
        try:
            comp = client.chat.completions.create(
                model=active_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=5000,
                temperature=0.2
            )
            content = comp.choices[0].message.content
            q_list = extract_and_parse_json(content)
            return batch_idx, q_list
        except Exception as e:
            if attempt == 1:
                raise e
            time.sleep(0.3)
    return batch_idx, []

def generate_full_100_exam_parallel(client, target_date_str, set_num, title_str):
    past_stems = get_recent_question_stems(limit=200)
    avoid_snippet = ("\nCRITICAL: DO NOT repeat any of these past question stems:\n- " + "\n- ".join(past_stems[:35])) if past_stems else ""
    
    active_model = find_working_model(client)

    batches = [
        # Batch 0: 25 GK (Nepali Unicode)
        {
            "start": 1, "end": 25,
            "prompt": f"""
            You are the Chief Examination Board Specialist for Nepal Public Service Commission (Loksewa Aayog).
            Create exactly 25 General Awareness MCQs (numbered 1 to 25) for Agri Officer 7th Level:
            - Geography & Census 2078
            - Constitution of Nepal (Art 36, 51, Schedules 5, 8, 9)
            - 16th Periodic Plan (2081/82-2085/86 targets)
            - Civil Service Act 2049, POSDCORB, Budgeting, UNO, SAARC, BIMSTEC, Climate Change
            {{{{avoid_snippet}}}}
            Language: Nepali (Unicode). 'is_figure_option': 0, 'figure_svg': null.
            Exam source tags: Federal PSC 2080, Bagmati PSC 2081, Koshi PSC 2080, Lumbini PSC 2079, Gandaki PSC 2081, CARE Bagbazar Model.
            In 'option_hints', describe why every option (A, B, C, D) is correct or what it refers to.

            Output format MUST BE a JSON object with key "questions":
            {{"questions": [
              {{"q_num": 1, "category": "GK", "sub_syllabus": "1.8 Constitution", "exam_source": "Federal PSC 2080", "is_figure_option": 0, "figure_svg": null, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"A":"...","B":"...","C":"...","D":"..."}}}}
            ]}}
            """
        },
        # Batch 1: 25 IQ (17 Verbal/Numerical + 8 Spatial with SVGs)
        {
            "start": 26, "end": 50,
            "prompt": f"""
            Generate exactly 25 Loksewa Aptitude / General Reasoning MCQs (numbered 26 to 50):
            - Q26 to Q34 (9 Logical Qs): Coding-decoding, series, direction & distance, Venn diagram, blood relation.
            - Q35 to Q42 (8 Numerical Qs): Time & work, profit & loss, ratio, percentage, calendar, average.
              ('is_figure_option': 0, 'figure_svg': null)
            - Q43 to Q50 (8 Spatial Qs with Inline SVG Figures): Figure series, pattern completion, 3x3 matrix, cube unfolding, paper folding.
              For Q43-Q50:
              * 'is_figure_option': 1
              * 'figure_svg': Valid inline SVG for Problem Figure (viewBox="0 0 320 80", width="320", height="80")
              * 'option_a', 'option_b', 'option_c', 'option_d': Valid inline SVGs for choices (viewBox="0 0 70 70", width="70", height="70")
            Language: English. Describe all 4 options in 'option_hints'.
            Output format MUST BE a JSON object with key "questions" (numbered 26 to 50).
            """
        },
        # Batch 2: 25 Technical Agriculture Part A (Q51 to Q75)
        {
            "start": 51, "end": 75,
            "prompt": f"""
            Generate exactly 25 Technical Agriculture MCQs (numbered 51 to 75) based strictly on PSC syllabus:
            - Unit 1: History & Current Status (5 Qs, Q51-Q55): APP, Devolution, DoA/NARC timeline, AgGDP.
            - Unit 2: Research, Extension & Education (5 Qs, Q56-Q60): NARC vision, AFU, FFS, AKC, T&V.
            - Unit 3: Environment, Climate & DRM (10 Qs, Q61-Q70): IPNM, IPM, GAP, Organic certification, Crop Insurance (80% subsidy), agro-biodiversity.
            - Unit 4: Policies (5 Qs, Q71-Q75): Constitution Art 36, 16th Plan agri goals, ADS (2015-2035) 4 pillars & VADEP.
            {{{{avoid_snippet}}}}
            Language: English. 'is_figure_option': 0, 'figure_svg': null. Describe all options in 'option_hints'.
            Output format MUST BE a JSON object with key "questions" (numbered 51 to 75).
            """
        },
        # Batch 3: 25 Technical Agriculture Part B (Q76 to Q100)
        {
            "start": 76, "end": 100,
            "prompt": f"""
            Generate exactly 25 Technical Agriculture MCQs (numbered 76 to 100) based strictly on PSC syllabus:
            - Unit 4: Acts & Global Trade (5 Qs, Q76-Q80): Seeds Act 2045, Plant Protection Act 2064, Pesticide Act 2076 (26 banned list), WTO SPS.
            - Unit 5: Agricultural Technology & Management (20 Qs, Q81-Q100):
              * Seed classes & isolation distances, physiological disorders (whiptail, browning), postharvest handling
              * Soil pH, lime requirement formula, IPNS
              * Entomology & Pathology: ETL, Fall Armyworm, Clubroot, Late blight
              * Farm economics (LER, elasticity, monopsony), research design (RCBD vs CRD)
            Language: English. 'is_figure_option': 0, 'figure_svg': null. Describe all options in 'option_hints'.
            Output format MUST BE a JSON object with key "questions" (numbered 76 to 100).
            """
        }
    ]

    # Run all 4 batches concurrently using 4 worker threads
    batch_results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {
            executor.submit(fetch_single_batch, idx, b, client, avoid_snippet, active_model): idx 
            for idx, b in enumerate(batches)
        }
        for future in as_completed(future_to_idx):
            b_idx, q_list = future.result()
            batch_results[b_idx] = q_list

    # Assemble sequential question list (1 to 100)
    all_100 = []
    for idx in range(len(batches)):
        all_100.extend(batch_results.get(idx, []))

    # Save to SQLite Database
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
                exam_id, q_num, q.get('category', 'Agri'), q.get('sub_syllabus', 'General Subject'),
                q.get('exam_source', 'Federal PSC Krishi'), q.get('is_figure_option', 0),
                q['question_text'], q.get('figure_svg'),
                q['option_a'], q['option_b'], q['option_c'], q['option_d'],
                q['correct_option'], q['explanation'], json.dumps(q.get('option_hints', {}))
            ))
        conn.commit()

    return exam_id, len(all_100), active_model

# =====================================================================
# 7. SIDEBAR NAVIGATION & TIME DISPLAY
# =====================================================================
st.sidebar.markdown("<h2 style='color:#10b981; margin-bottom:0;'>🌱 AgriLoksewa 7th</h2>", unsafe_allow_html=True)
st.sidebar.caption("Nepal Krishi Sewa (Gazetted 3rd Class / 7th Level)")

nepal_clock = get_nepal_now().strftime("%Y-%m-%d | %I:%M %p")
st.sidebar.markdown(f"<div class='clock-badge'>🕒 Nepal: {nepal_clock}</div>", unsafe_allow_html=True)
st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigation Menu",
    [
        "📝 Attempt 100-Question Exam",
        "📖 Review Exam & Option Hints",
        "⚡ Generate Next Set (Fast Engine)",
        "📊 Score History & Analytics"
    ]
)

# =====================================================================
# TAB 1: ATTEMPT 100-QUESTION EXAM
# =====================================================================
if menu == "📝 Attempt 100-Question Exam":
    st.markdown('<div class="main-title">📝 100-Question Model Examination</div>', unsafe_allow_html=True)
    st.caption("Nepal PSC Agriculture Service | Paper I (50 General + 50 Technical) | 20% Negative Marking")

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY set_number DESC, id DESC").fetchall()

    if not exams:
        st.warning("⚠️ No exams in database yet. Please visit the '⚡ Generate Next Set' tab to create Set #1 in seconds!")
        st.stop()

    exam_map = {f"Set #{e['set_number']} ({e['exam_date']}) - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Set:", list(exam_map.keys()))
    selected_exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute(
            "SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC",
            (selected_exam_id,)
        ).fetchall()

    if not questions:
        st.error("No questions found for this set.")
        st.stop()

    if f"user_ans_{selected_exam_id}" not in st.session_state:
        st.session_state[f"user_ans_{selected_exam_id}"] = {q['q_num']: None for q in questions}

    # Blueprint Statistics Bar
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("<div style='background:#f1f5f9; padding:10px; border-radius:8px; text-align:center;'><b>Total Questions:</b> 100</div>", unsafe_allow_html=True)
    c2.markdown("<div style='background:#fef3c7; padding:10px; border-radius:8px; text-align:center;'><b>Time Allowed:</b> 90 Minutes</div>", unsafe_allow_html=True)
    c3.markdown("<div style='background:#fee2e2; padding:10px; border-radius:8px; text-align:center;'><b>Negative Mark:</b> -0.2 (20%)</div>", unsafe_allow_html=True)
    c4.markdown("<div style='background:#ecfdf5; padding:10px; border-radius:8px; text-align:center;'><b>Pass Mark:</b> 40.0</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

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
                <h4 style="margin: 0.5rem 0 0.6rem 0; color:#0f172a;">Q{q_num}. {q['question_text']}</h4>
            </div>
            """, unsafe_allow_html=True)

            fig_svg = safe_get(q, 'figure_svg')
            if fig_svg and str(fig_svg).strip().startswith("<svg"):
                st.components.v1.html(fig_svg, height=95)

            current_choice = st.session_state[f"user_ans_{selected_exam_id}"].get(q_num, None)
            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0))

            if is_fig_opt:
                st.markdown("**Choose the matching figure:**")
                fA, fB, fC, fD = st.columns(4)

                with fA:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(A)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_a'], height=75)
                    st.markdown('</div>', unsafe_allow_html=True)
                with fB:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(B)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_b'], height=75)
                    st.markdown('</div>', unsafe_allow_html=True)
                with fC:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(C)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_c'], height=75)
                    st.markdown('</div>', unsafe_allow_html=True)
                with fD:
                    st.markdown('<div class="figure-frame"><span class="figure-label">(D)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_d'], height=75)
                    st.markdown('</div>', unsafe_allow_html=True)

                idx_val = ["A", "B", "C", "D"].index(current_choice) if current_choice in ["A", "B", "C", "D"] else None
                chosen = st.radio(
                    label=f"Q{q_num} Figure Selection",
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

            st.success("✅ Exam Evaluation Complete & Saved to Database!")
            if passed:
                st.balloons()

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#059669,#10b981); color:#fff; padding:20px; border-radius:12px; margin:20px 0;">
                <h2 style="margin:0; color:#fff;">Score: {final_score} / 100 {'(QUALIFIED ✅)' if passed else '(FAILED ❌)'}</h2>
                <p style="margin:6px 0 0 0; font-size:1.1rem;">Correct (+1.0): <b>{correct_cnt}</b> | Incorrect (-0.2): <b>{wrong_cnt}</b> | Unattempted: <b>{unattempted_cnt}</b></p>
            </div>
            """, unsafe_allow_html=True)
            st.info("👉 Check the **'📖 Review Exam & Option Hints'** tab to inspect explanations for all 4 options!")

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
                st.components.v1.html(fig_svg, height=95)

            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0))
            if is_fig_opt:
                fA, fB, fC, fD = st.columns(4)
                with fA:
                    st.caption("(A)")
                    st.components.v1.html(q['option_a'], height=75)
                with fB:
                    st.caption("(B)")
                    st.components.v1.html(q['option_b'], height=75)
                with fC:
                    st.caption("(C)")
                    st.components.v1.html(q['option_c'], height=75)
                with fD:
                    st.caption("(D)")
                    st.components.v1.html(q['option_d'], height=75)
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

            st.markdown(f"""
            <div class="hint-container">
                <b>💡 Core Syllabus Concept:</b> {q['explanation']}
            </div>
            """, unsafe_allow_html=True)

            # Option Hints Breakdown
            opt_hints_raw = safe_get(q, 'option_hints')
            if opt_hints_raw:
                try:
                    hints = json.loads(opt_hints_raw)
                    if hints:
                        st.markdown("<div style='margin-top:12px; font-weight:700; color:#1e293b;'>🔍 Complete Option-by-Option Breakdown:</div>", unsafe_allow_html=True)
                        for opt_k in ["A", "B", "C", "D"]:
                            if opt_k in hints:
                                prefix = "✅ [CORRECT]" if opt_k == correct else "❌ [INCORRECT]"
                                st.markdown(f"<div class='option-explanation-pill'><b>Option ({opt_k}) {prefix}:</b> {hints[opt_k]}</div>", unsafe_allow_html=True)
                except Exception:
                    pass

# =====================================================================
# TAB 3: GENERATE NEXT SET (FAST AUTO ENGINE)
# =====================================================================
elif menu == "⚡ Generate Next Set (Fast Engine)":
    st.markdown('<div class="main-title">⚡ Instant Exam Creator & Next-Set Engine</div>', unsafe_allow_html=True)
    st.caption("Automatic model discovery and multi-threaded parallel generation across 4 threads.")

    next_set = get_next_set_number()
    today_str = get_today_nepal_str()

    st.info(f"Upcoming Set: **Set #{next_set}** | Today's Date: **{today_str}**")

    saved_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    api_key = st.text_input("Groq API Key:", type="password", value=saved_key, help="Enter your key once; it auto-saves.")

    colA, colB = st.columns(2)
    with colA:
        target_set_num = st.number_input("Set Number:", value=next_set, min_value=1, step=1)
    with colB:
        target_title = st.text_input("Exam Title:", value=f"Loksewa Krishi 7th Level Model Set #{target_set_num}")

    st.markdown("""
    **What this generator guarantees:**
    - **25 GK Questions:** Nepali Unicode, Census 2078, Constitution, 16th Plan, Budgeting, Civil Service Act.
    - **25 IQ Questions:** 17 Verbal/Numerical + 8 Non-Verbal with native SVG Problem Figures and SVG Option Figures.
    - **50 Technical Agriculture Questions:** 5 History/Status, 5 Research/Extension, 10 Natural Resources/Climate/DRM, 10 Legislations/Trade, 20 Agri Technology & Management.
    - Hints detailing why every option (A, B, C, D) is correct or incorrect.
    - Automatically excludes previously generated questions to ensure non-repetition.
    """)

    if st.button("➡️ Generate 100-Question Exam Set (Fast Mode)", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please enter your Groq API Key.")
            st.stop()

        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            prog = st.progress(0, text="Discovering verified active model and starting parallel generation...")

            start_t = time.time()
            with st.spinner(f"Generating Set #{target_set_num} across 4 parallel threads (~5 to 8 seconds)..."):
                prog.progress(30, text="Generating all 100 questions simultaneously...")
                new_id, total_q, used_model = generate_full_100_exam_parallel(client, today_str, target_set_num, target_title)
                prog.progress(100, text="Complete!")

            elapsed = round(time.time() - start_t, 1)
            st.success(f"🎉 Generated Set #{target_set_num} ({total_q} questions) using `{used_model}` in only **{elapsed} seconds**!")
            st.info("Switch to the **'📝 Attempt 100-Question Exam'** tab to start your examination!")
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
