import streamlit as st
import sqlite3
import json
from datetime import datetime, timezone, timedelta
import pandas as pd
import os
import time

# ----------------- TIMEZONE CONFIG (NEPAL TIME UTC+5:45) -----------------
NEPAL_TZ = timezone(timedelta(hours=5, minutes=45))

def get_nepal_now():
    return datetime.now(NEPAL_TZ)

def get_today_nepal_str():
    return get_nepal_now().strftime("%Y-%m-%d")

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="Loksewa Agri 7th Level Portal",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- EYE-CATCHY CUSTOM CSS -----------------
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-title {
        background: linear-gradient(135deg, #10b981 0%, #059669 40%, #0284c7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
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
        margin-bottom: 1.2rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .question-card:hover {
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.08);
        border-color: #cbd5e1;
    }

    .badge {
        display: inline-block;
        padding: 0.22rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-right: 0.4rem;
    }
    .badge-gk { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
    .badge-iq { background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe; }
    .badge-agri { background: #d1fae5; color: #047857; border: 1px solid #a7f3d0; }
    .badge-source { background: #f1f5f9; color: #334155; border: 1px solid #e2e8f0; }

    .figure-option-card {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 10px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .figure-option-card:hover {
        border-color: #10b981;
        background: #f0fdf4;
        transform: translateY(-2px);
    }
    .figure-tag {
        font-weight: 800;
        font-size: 0.95rem;
        color: #0f172a;
        margin-bottom: 6px;
        display: block;
    }
    
    .answer-banner-correct {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border-left: 5px solid #10b981;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 10px 0;
        color: #065f46;
        font-weight: 600;
    }
    .answer-banner-wrong {
        background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%);
        border-left: 5px solid #f43f5e;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 10px 0;
        color: #9f1239;
        font-weight: 600;
    }
    .hint-box {
        background: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 10px 14px;
        border-radius: 6px;
        margin-top: 8px;
        font-size: 0.92rem;
        color: #1e293b;
    }
    .option-hint-pill {
        background: #ffffff;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        padding: 6px 12px;
        margin: 4px 0;
        font-size: 0.88rem;
        color: #475569;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DB_FILE = "loksewa_agri_exams.db"

# ----------------- DATABASE HELPERS -----------------
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
                exam_date TEXT UNIQUE,
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
                exam_place TEXT,
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

        # Auto-migration for schema changes
        cursor.execute("PRAGMA table_info(questions)")
        existing_cols = [r[1] for r in cursor.fetchall()]
        
        required_cols = {
            "is_figure_option": "INTEGER DEFAULT 0",
            "figure_svg": "TEXT",
            "category": "TEXT",
            "exam_place": "TEXT",
            "option_hints": "TEXT"
        }
        for col, col_type in required_cols.items():
            if col not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE questions ADD COLUMN {col} {col_type}")
                except Exception:
                    pass
        
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

# ----------------- ANTI-REPETITION PAST TOPIC EXTRACTOR -----------------
def get_recent_question_stems(limit=150):
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT question_text FROM questions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        stems = [r[0][:45] for r in rows if r[0]]
        return stems

# ----------------- ROTATIONAL TOPIC MATRIX -----------------
def get_daily_topic_focus():
    weekday = get_nepal_now().weekday()
    # Rotates core topics across 7 days to eliminate repetition
    matrix = {
        0: { # Monday
            "gk": "Nepal Demography (Census 2078), Physical Geography (Lakes, Glaciers, Mountain passes), UN & BIMSTEC",
            "agri_a": "History of Agri Extension (DoA, NARC mandate), Agri Education (AFU, IAAS), ADS Pillar 1 (Governance)",
            "agri_b": "Cereal Agronomy (Paddy & Maize SRI, biofortification, hybrid seed rate), IPNS & Urea calculation"
        },
        1: { # Tuesday
            "gk": "Constitution of Nepal (Fundamental rights, Directive principles, Schedules 5, 6, 7, 8, 9)",
            "agri_a": "Plant Protection Act 2064, Pesticide Management Act 2076, Banned pesticides (26 banned active ingredients)",
            "agri_b": "Horticulture: Olericulture, Potato late blight & wart disease, Physiological disorders (Whiptail, Browning, Buttoning)"
        },
        2: { # Wednesday
            "gk": "16th Periodic Plan (2081/82-2085/86 targets & strategies), Fiscal Budgeting & Accounting",
            "agri_a": "Right to Food and Food Sovereignty Act 2076, National Seed Policy 2056, WTO SPS Agreement",
            "agri_b": "Soil Science: Soil reaction (pH), Lime requirement calculation, Cation Exchange Capacity (CEC), Phosphorus fixation"
        },
        3: { # Thursday
            "gk": "Civil Service Act 2049 & Rules 2050 (Leave, Pension, Conduct), Good Governance Act 2064",
            "agri_a": "Natural Resource Conservation, Climate Change adaptation (NAPA, LAPA), GLOF & Disaster management",
            "agri_b": "Entomology: Invasive pests (Fall Armyworm, Tuta absoluta), ETL, Biopesticides, Honeybee castes & pollination"
        },
        4: { # Friday
            "gk": "Management principles (POSDCORB, Motivation theories, Leadership, Public Policy formulation)",
            "agri_a": "Agro-forestry policy, Crop Insurance policy (80% premium subsidy), Agricultural Projects planning",
            "agri_b": "Pomology & Fruit processing, Pruning/training, Postharvest curing/blanching, Hermetic storage moisture limits"
        },
        5: { # Saturday
            "gk": "Comprehensive Federal & Province Past Questions: Nepal History (Lichhavi, Malla, Shah) & Contemporary Affairs",
            "agri_a": "ADS 20-year roadmap (Productivity & Commercialization targets), National Seed Vision 2013-2025",
            "agri_b": "Cash crops (Tea, Coffee, Cardamom, Ginger), Seed quality testing (Tetrazolium, purity), Land Equivalent Ratio (LER)"
        },
        6: { # Sunday
            "gk": "Sustainable Development Goals (SDGs 1, 2, 13), National Parks & Biodiversity Conservation",
            "agri_a": "Extension teaching methods (FFS, Result demonstration, Method demonstration), Participatory Planning (PRA)",
            "agri_b": "Plant Pathology (Bacterial blight, Clubroot, Rusts), Agricultural Marketing & Monopsony structures"
        }
    }
    return matrix.get(weekday, matrix[0])

# ----------------- 4-BATCH 100-QUESTION GROQ ENGINE -----------------
def generate_full_100_exam(client, target_date_str, title_str):
    past_stems = get_recent_question_stems(limit=100)
    avoid_snippet = ("\nCRITICAL: AVOID repeating these recently asked question stems/topics:\n- " + "\n- ".join(past_stems[:35])) if past_stems else ""
    focus = get_daily_topic_focus()

    batches = [
        # Batch 1: 25 GK
        {
            "category": "GK",
            "prompt": f"""
            You are the chief examiner for Nepal Loksewa Agriculture 7th Level (Gazetted 3rd Class).
            Generate exactly 25 General Awareness (GK) MCQs for the exam date: {target_date_str}.
            Today's Primary Focus: {focus['gk']}.
            {avoid_snippet}
            
            Strictly adhere to Nepal PSC Section Officer syllabus:
            - Physical/Demographic Geography (Census 2078)
            - Constitution of Nepal (Articles 36, 42, Schedules 5-9)
            - 16th Periodic Plan targets
            - Civil Service Act 2049, Governance, Budgeting
            
            Every question must have:
            - 'exam_place' tag (e.g. 'Federal PSC 2080', 'Bagmati PSC 2081', 'Koshi PSC 2080', 'Lumbini PSC 2079', 'CARE Model Exam', 'Himalayan Institute')
            - 'is_figure_option': 0
            - 'figure_svg': null
            Language: Nepali (Unicode).
            
            Respond ONLY with a valid JSON array of 25 objects numbered 1 to 25:
            [
              {{
                "q_num": 1, "category": "GK", "exam_place": "Federal PSC 2080", "is_figure_option": 0,
                "question_text": "...", "figure_svg": null,
                "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
                "correct_option": "A", "explanation": "...",
                "option_hints": {{"B": "why B is wrong", "C": "...", "D": "..."}}
              }}
            ]
            """
        },
        # Batch 2: 25 IQ (with 8 Non-Verbal SVG Figure Option Questions)
        {
            "category": "IQ",
            "prompt": f"""
            Generate exactly 25 Loksewa Aptitude / IQ questions (numbered 26 to 50):
            - Q26 to Q42 (17 Verbal/Numerical Qs): Time & work, series, coding-decoding, blood relations, ratio, profit & loss. ('is_figure_option': 0).
            - Q43 to Q50 (8 Non-Verbal Spatial Qs): MUST HAVE FIGURE OPTIONS!
              For Q43 to Q50:
              - 'is_figure_option': 1
              - 'figure_svg': Inline SVG code for the Problem Figure (width 220, height 70)
              - 'option_a', 'option_b', 'option_c', 'option_d': Inline SVG code for each of the 4 answer figures (width 70, height 60)
            
            Respond ONLY with a valid JSON array of 25 objects numbered 26 to 50.
            """
        },
        # Batch 3: 25 Agriculture Part A (Policies, Extension, Environment)
        {
            "category": "Agri",
            "prompt": f"""
            Generate exactly 25 Technical Agriculture questions (numbered 51 to 75) for 7th Level Officer:
            Today's Primary Focus: {focus['agri_a']}.
            {avoid_snippet}
            
            Topics:
            - History of Agriculture in Nepal, DoA, NARC vision
            - Agri Extension systems (T&V, FFS, AKC, Pluralistic extension)
            - ADS (2015-2035) 4 pillars, governance indicators
            - Seeds Act 2045 & Rules 2069, Pesticides Act 2076, Plant Protection Act 2064
            - Right to Food & Food Sovereignty Act 2076, WTO SPS Agreement, Climate change mitigation
            
            Every question must have 'option_hints' explaining the other options. 'is_figure_option': 0.
            Language: English.
            Respond ONLY with a valid JSON array of 25 objects numbered 51 to 75.
            """
        },
        # Batch 4: 25 Agriculture Part B (Core Agronomy, Soil, Horticulture, Protection)
        {
            "category": "Agri",
            "prompt": f"""
            Generate exactly 25 Technical Agriculture questions (numbered 76 to 100) for 7th Level Officer:
            Today's Primary Focus: {focus['agri_b']}.
            {avoid_snippet}
            
            Topics:
            - Agronomy: Seed certification classes (Breeder, Foundation, Certified, Improved tags), isolation distances
            - Horticulture: Vegetable disorders, fruit propagation (grafting/budding), postharvest blanching
            - Soil Science: IPNM, Soil reaction (pH), fertilizer active ingredients, nutrient deficiency symptoms
            - Plant Protection: Major insect pests (Fall Armyworm, stem borers), diseases (Late blight, BLB, Clubroot), ETL
            - Farm Management, Land Equivalent Ratio (LER), market structures (Monopoly, Monopsony)
            
            Every question must have 'option_hints' explaining why the incorrect options are wrong. 'is_figure_option': 0.
            Language: English.
            Respond ONLY with a valid JSON array of 25 objects numbered 76 to 100.
            """
        }
    ]

    all_100 = []
    for b in batches:
        comp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": b["prompt"]}],
            response_format={"type": "json_object"}
        )
        content = comp.choices[0].message.content
        data = json.loads(content)
        q_list = data if isinstance(data, list) else data.get("questions", list(data.values())[0])
        all_100.extend(q_list)
        time.sleep(0.4)

    # Save to SQLite by Date
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO exams (exam_date, title, total_questions) VALUES (?, ?, ?)",
            (target_date_str, title_str, len(all_100))
        )
        exam_id = cursor.lastrowid

        for q in all_100:
            cursor.execute('''
                INSERT INTO questions 
                (exam_id, q_num, category, exam_place, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id, q['q_num'], q.get('category', 'Agri'), q.get('exam_place', 'Nepal PSC Model'),
                q.get('is_figure_option', 0), q['question_text'], q.get('figure_svg'),
                q['option_a'], q['option_b'], q['option_c'], q['option_d'],
                q['correct_option'], q['explanation'], json.dumps(q.get('option_hints', {}))
            ))
        conn.commit()

    return len(all_100)

# ----------------- MIDNIGHT 12:00 AM AUTO-CHECK & GENERATION -----------------
def auto_check_and_generate_midnight_exam():
    """
    Checks if today's date (Nepal Time) exists in SQLite.
    If it's past 12:00 AM and no exam exists, automatically calls Groq to generate it.
    """
    today_nepal = get_today_nepal_str()
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM exams WHERE exam_date = ?", (today_nepal,)).fetchone()
        
    if not existing:
        # Retrieve API key from Streamlit Secrets or Environment
        api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
        if api_key:
            try:
                from groq import Groq
                client = Groq(api_key=api_key)
                title = f"Agriculture 7th Level Daily Exam - {today_nepal}"
                generate_full_100_exam(client, today_nepal, title)
            except Exception as e:
                print(f"Auto midnight generation error: {e}")

auto_check_and_generate_midnight_exam()

# ----------------- SIDEBAR -----------------
st.sidebar.markdown("<h2 style='color:#10b981; margin-bottom:0;'>🌱 AgriLoksewa 7th</h2>", unsafe_allow_html=True)
st.sidebar.caption("Nepal Agriculture Service (Gazetted 3rd Class / 7th Level)")

nepal_clock = get_nepal_now().strftime("%Y-%m-%d | %I:%M %p")
st.sidebar.markdown(f"<div class='clock-badge'>🕒 Nepal: {nepal_clock}</div>", unsafe_allow_html=True)
st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigation",
    ["📝 Attempt 100-Question Exam", "📖 Review Exam by Date & Hints", "📊 Score History & Analytics", "⚡ 100-Question Daily Generator"]
)

# =======================================================
# 1. ATTEMPT 100-QUESTION EXAM
# =======================================================
if menu == "📝 Attempt 100-Question Exam":
    st.markdown('<div class="main-title">📝 Daily 100-Question Model Exam</div>', unsafe_allow_html=True)
    st.caption("Auto-resets at 12:00 AM Daily | 25 GK + 25 IQ + 50 Agriculture | 20% Negative Marking")

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()

    if not exams:
        st.warning("⚠️ Today's exam has not been generated yet. Please visit the '⚡ 100-Question Daily Generator' tab to generate today's set.")
        st.stop()

    exam_map = {f"{e['exam_date']} - {e['title']} ({e['total_questions']} Qs)": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Date:", list(exam_map.keys()))
    selected_exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute(
            "SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC",
            (selected_exam_id,)
        ).fetchall()

    if not questions:
        st.error("No questions found for this date.")
        st.stop()

    if f"user_ans_{selected_exam_id}" not in st.session_state:
        st.session_state[f"user_ans_{selected_exam_id}"] = {q['q_num']: None for q in questions}

    # Top Status Bar
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div style='background:#f1f5f9; padding:10px; border-radius:8px; text-align:center;'><b>Total Questions:</b> {len(questions)}</div>", unsafe_allow_html=True)
    c2.markdown("<div style='background:#fef3c7; padding:10px; border-radius:8px; text-align:center;'><b>Time:</b> 90 Minutes</div>", unsafe_allow_html=True)
    c3.markdown("<div style='background:#fee2e2; padding:10px; border-radius:8px; text-align:center;'><b>Negative Mark:</b> -0.2 (20%)</div>", unsafe_allow_html=True)
    c4.markdown("<div style='background:#ecfdf5; padding:10px; border-radius:8px; text-align:center;'><b>Passing Mark:</b> 45.0</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Interactive Palette in Sidebar
    st.sidebar.markdown("### 🧭 Question Palette (1-100)")
    ans_count = sum(1 for v in st.session_state[f"user_ans_{selected_exam_id}"].values() if v is not None)
    st.sidebar.progress(ans_count / len(questions), text=f"Answered: {ans_count} / {len(questions)}")

    pal_cols = st.sidebar.columns(5)
    for idx, q in enumerate(questions):
        q_no = q['q_num']
        col = pal_cols[idx % 5]
        is_done = st.session_state[f"user_ans_{selected_exam_id}"][q_no] is not None
        col.caption(f"{'🟢' if is_done else '⚪'} {q_no}")

    # Exam Form (No pre-selected options, no 'Skip' item)
    with st.form(key=f"exam_form_{selected_exam_id}"):
        for q in questions:
            q_num = q['q_num']
            cat = safe_get(q, 'category', 'Agri')
            exam_place = safe_get(q, 'exam_place', 'Loksewa Model')
            badge_class = "badge-gk" if cat == "GK" else ("badge-iq" if cat == "IQ" else "badge-agri")

            st.markdown(f"""
            <div class="question-card">
                <div>
                    <span class="badge {badge_class}">{cat}</span>
                    <span class="badge badge-source">{exam_place}</span>
                </div>
                <h4 style="margin: 0.5rem 0 0.8rem 0; color:#0f172a;">Q{q_num}. {q['question_text']}</h4>
            </div>
            """, unsafe_allow_html=True)

            fig_svg = safe_get(q, 'figure_svg')
            if fig_svg:
                st.components.v1.html(fig_svg, height=85)

            current_choice = st.session_state[f"user_ans_{selected_exam_id}"].get(q_num, None)
            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0))

            # Non-Verbal IQ (Figure Options)
            if is_fig_opt:
                st.markdown("**Select from the Answer Figures below:**")
                colA, colB, colC, colD = st.columns(4)

                with colA:
                    st.markdown('<div class="figure-option-card"><span class="figure-tag">(A)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_a'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)

                with colB:
                    st.markdown('<div class="figure-option-card"><span class="figure-tag">(B)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_b'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)

                with colC:
                    st.markdown('<div class="figure-option-card"><span class="figure-tag">(C)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_c'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)

                with colD:
                    st.markdown('<div class="figure-option-card"><span class="figure-tag">(D)</span>', unsafe_allow_html=True)
                    st.components.v1.html(q['option_d'], height=70)
                    st.markdown('</div>', unsafe_allow_html=True)

                idx_val = ["A", "B", "C", "D"].index(current_choice) if current_choice in ["A", "B", "C", "D"] else None
                chosen = st.radio(
                    label=f"Answer for Q{q_num}",
                    options=["A", "B", "C", "D"],
                    index=idx_val,
                    format_func=lambda x: f"Option ({x})",
                    key=f"radio_fig_{selected_exam_id}_{q_num}",
                    horizontal=True
                )
                st.session_state[f"user_ans_{selected_exam_id}"][q_num] = chosen

            # Text Options
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
            passed = 1 if final_score >= 45.0 else 0

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

            st.success("🎉 Exam Successfully Submitted and Saved to Database!")
            if passed:
                st.balloons()

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#059669,#10b981); color:#fff; padding:20px; border-radius:12px; margin:20px 0;">
                <h2 style="margin:0; color:#fff;">Your Score: {final_score} / 100 {'(PASS ✅)' if passed else '(FAIL ❌)'}</h2>
                <p style="margin:5px 0 0 0; font-size:1.1rem;">Correct (+1.0): <b>{correct_cnt}</b> | Incorrect (-0.2): <b>{wrong_cnt}</b> | Unattempted: <b>{unattempted_cnt}</b></p>
            </div>
            """, unsafe_allow_html=True)
            st.info("👉 Check the **'📖 Review Exam by Date & Hints'** tab to view all answers, hints, and option breakdowns!")

# =======================================================
# 2. REVIEW EXAM BY DATE & HINTS
# =======================================================
elif menu == "📖 Review Exam by Date & Hints":
    st.markdown('<div class="main-title">📖 Exam Review & Technical Option Hints</div>', unsafe_allow_html=True)

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()

    if not exams:
        st.warning("No exams stored.")
        st.stop()

    exam_map = {f"{e['exam_date']} - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Date:", list(exam_map.keys()))
    exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", (exam_id,)).fetchall()
        attempt = conn.execute("SELECT * FROM attempts WHERE exam_id = ? ORDER BY id DESC LIMIT 1", (exam_id,)).fetchone()

    user_answers = json.loads(attempt['user_answers']) if attempt and attempt['user_answers'] else {}
    if attempt:
        st.markdown(f"""
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:10px 14px; margin-bottom:15px;">
            <b>Latest Attempt:</b> {attempt['attempt_date']} | <b>Score:</b> {attempt['score']}/100 | 
            <b>Correct:</b> {attempt['correct_count']} | <b>Wrong:</b> {attempt['wrong_count']}
        </div>
        """, unsafe_allow_html=True)

    filter_sec = st.radio("Section:", ["All 100 Questions", "GK (Q1-25)", "IQ (Q26-50)", "Technical Agri (Q51-100)"], horizontal=True)

    for q in questions:
        q_no = q['q_num']
        if filter_sec == "GK (Q1-25)" and not (1 <= q_no <= 25): continue
        if filter_sec == "IQ (Q26-50)" and not (26 <= q_no <= 50): continue
        if filter_sec == "Technical Agri (Q51-100)" and not (51 <= q_no <= 100): continue

        user_pick = user_answers.get(str(q_no), user_answers.get(q_no, None))
        correct = q['correct_option']
        cat = safe_get(q, 'category', 'Agri')
        exam_place = safe_get(q, 'exam_place', 'Loksewa Model')
        badge_class = "badge-gk" if cat == "GK" else ("badge-iq" if cat == "IQ" else "badge-agri")

        is_correct = (user_pick == correct)
        status_text = "⚪ Unattempted" if user_pick is None else ("✅ Correct" if is_correct else f"❌ Wrong (You: {user_pick})")

        with st.expander(f"Q{q_no}. {q['question_text']} [{status_text}]", expanded=False):
            st.markdown(f'<span class="badge {badge_class}">{cat}</span> <span class="badge badge-source">{exam_place}</span>', unsafe_allow_html=True)

            fig_svg = safe_get(q, 'figure_svg')
            if fig_svg:
                st.components.v1.html(fig_svg, height=85)

            is_fig_opt = bool(safe_get(q, 'is_figure_option', 0))
            if is_fig_opt:
                colA, colB, colC, colD = st.columns(4)
                with colA:
                    st.caption("(A)")
                    st.components.v1.html(q['option_a'], height=70)
                with colB:
                    st.caption("(B)")
                    st.components.v1.html(q['option_b'], height=70)
                with colC:
                    st.caption("(C)")
                    st.components.v1.html(q['option_c'], height=70)
                with colD:
                    st.caption("(D)")
                    st.components.v1.html(q['option_d'], height=70)
            else:
                cA, cB = st.columns(2)
                cA.write(f"**(A)** {q['option_a']}")
                cA.write(f"**(B)** {q['option_b']}")
                cB.write(f"**(C)** {q['option_c']}")
                cB.write(f"**(D)** {q['option_d']}")

            user_disp = "None" if user_pick is None else f"Option ({user_pick})"
            st.markdown(f"""
            <div class="{'answer-banner-correct' if is_correct else 'answer-banner-wrong'}">
                Verified Answer: Option ({correct}) | Your Response: {user_disp}
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="hint-box">
                <b>💡 Core Concept & Explanation:</b> {q['explanation']}
            </div>
            """, unsafe_allow_html=True)

            opt_hints_raw = safe_get(q, 'option_hints')
            if opt_hints_raw:
                try:
                    hints = json.loads(opt_hints_raw)
                    if hints:
                        st.markdown("<div style='margin-top:10px; font-weight:700; color:#334155;'>🔍 Why other options are incorrect:</div>", unsafe_allow_html=True)
                        for opt_k, opt_desc in hints.items():
                            st.markdown(f"<div class='option-hint-pill'><b>Option ({opt_k}):</b> {opt_desc}</div>", unsafe_allow_html=True)
                except:
                    pass

# =======================================================
# 3. SCORE HISTORY & ANALYTICS
# =======================================================
elif menu == "📊 Score History & Analytics":
    st.markdown('<div class="main-title">📊 Score Analytics by Date</div>', unsafe_allow_html=True)

    with get_db() as conn:
        attempts = conn.execute('''
            SELECT a.id, e.exam_date, e.title, a.attempt_date, a.score, 
                   a.correct_count, a.wrong_count, a.unattempted_count, a.is_passed
            FROM attempts a
            JOIN exams e ON a.exam_id = e.id
            ORDER BY a.id ASC
        ''').fetchall()

    if not attempts:
        st.info("No exam attempts recorded yet.")
        st.stop()

    df = pd.DataFrame([dict(a) for a in attempts])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tests Attempted", len(df))
    c2.metric("Top Score", f"{df['score'].max()} pts")
    c3.metric("Average Score", f"{round(df['score'].mean(), 2)} pts")
    c4.metric("Passing Rate", f"{round((df['is_passed'].sum() / len(df)) * 100, 1)}%")

    st.subheader("📈 Performance Trend")
    st.line_chart(df.set_index('attempt_date')['score'])

    st.subheader("📜 Date-wise Scores")
    st.dataframe(df[['exam_date', 'attempt_date', 'score', 'correct_count', 'wrong_count', 'unattempted_count', 'is_passed']], use_container_width=True)

# =======================================================
# 4. 100-QUESTION DAILY GENERATOR (GROQ ENGINE)
# =======================================================
elif menu == "⚡ 100-Question Daily Generator":
    st.markdown('<div class="main-title">⚡ 100-Question Daily Generator</div>', unsafe_allow_html=True)
    st.caption("Automatic at 12:00 AM Daily | Manual Generation Available Below")

    today_str = get_today_nepal_str()
    st.info(f"📅 Today's Date (Nepal Time): **{today_str}** | Resets every midnight automatically.")

    saved_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    api_key = st.text_input("Groq API Key:", type="password", value=saved_key)
    target_dt = st.date_input("Target Exam Date:", value=get_nepal_now().date())
    target_title = st.text_input("Exam Title:", value=f"Loksewa Krishi Adhikrit 7th Level - {target_dt}")

    if st.button("🚀 Generate / Refresh 100-Question Exam Set", type="primary"):
        if not api_key:
            st.error("Please provide a Groq API Key.")
            st.stop()

        from groq import Groq
        groq_client = Groq(api_key=api_key)

        progress = st.progress(0, text="Initiating Anti-Repetition 4-Batch Pipeline...")

        try:
            with st.spinner("Generating 100 non-repeating questions with SVG figures..."):
                total_generated = generate_full_100_exam(groq_client, str(target_dt), target_title)
                progress.progress(100, text="Complete!")

            st.success(f"🎉 Successfully generated {total_generated} distinct questions for {target_dt}!")
            st.info("Go to the **'📝 Attempt 100-Question Exam'** tab to take the test!")
        except Exception as e:
            st.error(f"Generation error: {e}")
