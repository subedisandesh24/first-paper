import streamlit as st
import sqlite3
import json
from datetime import datetime, date
import pandas as pd
import os
import time

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
    
    .question-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1.4rem;
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

# ----------------- DATABASE SCHEMA -----------------
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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

# ----------------- SEED SAMPLE EXAM -----------------
def seed_sample_exam():
    with get_db() as conn:
        cursor = conn.cursor()
        today_str = str(date.today())
        cursor.execute("SELECT id FROM exams WHERE exam_date = ?", (today_str,))
        if cursor.fetchone():
            return

        cursor.execute(
            "INSERT INTO exams (exam_date, title, total_questions) VALUES (?, ?, ?)",
            (today_str, f"Daily 100-Question Exam Set - {today_str}", 100)
        )
        exam_id = cursor.lastrowid

        qs = []

        # 1. SAMPLE GK (Q1 to Q25)
        for i in range(1, 26):
            if i == 1:
                qs.append((
                    exam_id, 1, "GK", "Federal PSC 2080", 0,
                    "नेपालको वर्तमान संविधानको कुन धारामा 'खाद्य सम्बन्धी हक' (खाद्य सम्प्रभुता) को मौलिक हक सुनिश्चित गरिएको छ?",
                    None, "धारा ३३", "धारा ३५", "धारा ३६", "धारा ४०", "C",
                    "धारा ३६ मा प्रत्येक नागरिकलाई खाद्य सम्बन्धी हक, खाद्यवस्तुको अभावमा जीवन जोखिममा नपर्ने हक तथा खाद्य सम्प्रभुताको हक प्रत्याभूत गरिएको छ।",
                    json.dumps({"A": "धारा ३३: रोजगारीको हक", "B": "धारा ३५: स्वास्थ्य सम्बन्धी हक", "D": "धारा ४०: दलितको हक"})
                ))
            elif i == 2:
                qs.append((
                    exam_id, 2, "GK", "Bagmati PSC 2081", 0,
                    "नेपाल सरकारको १६ औं आवधिक योजना (२०८१/८२-२०८५/८६) को मुख्य राष्ट्रिय सोच (Vision) के हो?",
                    None, "समृद्ध नेपाल, सुखी नेपाली", "सुशासन, सामाजिक न्याय र समृद्धि", "समाजवाद उन्मुख स्वाधीन अर्थतन्त्र", "दिगो विकास र गरिबी निवारण", "B",
                    "१६ औं आवधिक योजनाको सोच 'सुशासन, सामाजिक न्याय र समृद्धि' तय गरिएको छ।",
                    json.dumps({"A": "यो १५ औं योजनाको २५ वर्षे दीर्घकालीन सोच हो।", "C": "संविधानको निर्देशक सिद्धान्तको अंश हो।", "D": "सामान्य विकास लक्ष्य हो।"})
                ))
            else:
                qs.append((
                    exam_id, i, "GK", "Federal & Province PSC", 0,
                    f"नेपालको भूगोल, संविधान तथा सुशासन सम्बन्धी वस्तुगत प्रश्न नं. {i}: तलका मध्ये कुन तथ्य सही छ?",
                    None, "नेपालमा ७५३ स्थानीय तह छन्।", "नेपालमा ७७ प्रदेशहरू छन्।", "नेपालमा ४० वटा मन्त्रालय छन्।", "नेपालको संविधानमा ५० वटा अनुसूची छन्।", "A",
                    "नेपालको संघीय संरचनामा ७ प्रदेश र ७५३ स्थानीय तह (गाउँपालिका/नगरपालिका) छन्।",
                    json.dumps({"B": "प्रदेश संख्या ७ मात्र हो।", "C": "संघीय मन्त्रालयको संख्या २५ मा सीमित छ।", "D": "संविधानमा ९ वटा अनुसूची मात्र छन्।"})
                ))

        # 2. SAMPLE IQ (Q26 to Q50) with Non-Verbal Figure Options
        for i in range(26, 51):
            if i == 45: # PURE NON-VERBAL WITH FIGURE OPTIONS
                q_fig = """<svg width="220" height="70" style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:8px;">
                    <rect x="20" y="20" width="30" height="30" fill="none" stroke="#2563eb" stroke-width="3"/>
                    <text x="65" y="42" font-size="20" fill="#64748b">→</text>
                    <rect x="90" y="20" width="30" height="30" fill="none" stroke="#2563eb" stroke-width="3"/>
                    <line x1="90" y1="20" x2="120" y2="50" stroke="#dc2626" stroke-width="3"/>
                    <text x="135" y="42" font-size="20" fill="#64748b">::</text>
                    <circle cx="175" cy="35" r="16" fill="none" stroke="#2563eb" stroke-width="3"/>
                    <text x="200" y="42" font-size="22" font-weight="bold" fill="#dc2626">?</text>
                </svg>"""
                opt_a = """<svg width="70" height="60"><circle cx="35" cy="30" r="16" fill="none" stroke="#2563eb" stroke-width="3"/><line x1="22" y1="18" x2="48" y2="42" stroke="#dc2626" stroke-width="3"/></svg>"""
                opt_b = """<svg width="70" height="60"><circle cx="35" cy="30" r="16" fill="none" stroke="#2563eb" stroke-width="3"/><circle cx="35" cy="30" r="6" fill="#dc2626"/></svg>"""
                opt_c = """<svg width="70" height="60"><rect x="20" y="15" width="30" height="30" fill="#2563eb"/></svg>"""
                opt_d = """<svg width="70" height="60"><circle cx="35" cy="30" r="16" fill="none" stroke="#2563eb" stroke-width="3"/><line x1="35" y1="14" x2="35" y2="46" stroke="#000" stroke-width="2"/></svg>"""

                qs.append((
                    exam_id, 45, "IQ", "Federal PSC 2080", 1,
                    "[Non-Verbal Analogy] Problem Figure: Analyze the rule in the first pair and choose the correct Answer Figure to replace (?):",
                    q_fig, opt_a, opt_b, opt_c, opt_d, "A",
                    "In the first pair, a diagonal line cuts across the square. Following the exact same relationship, a diagonal line cuts across the circle.",
                    json.dumps({"B": "A dot inside is a different transformation rule.", "C": "Solid fill is not present in the pattern.", "D": "Vertical bisector alters the diagonal symmetry."})
                ))
            else:
                qs.append((
                    exam_id, i, "IQ", "Federal PSC 2079", 0,
                    f"Logical/Numerical Reasoning Question #{i}: If 6 agri-technicians can survey 6 hectares of land in 6 days, how many days will 1 technician take to survey 1 hectare?",
                    None, "1 day", "6 days", "12 days", "36 days", "B",
                    "Formula: (M1 * D1)/W1 = (M2 * D2)/W2 => (6 * 6)/6 = (1 * D2)/1 => D2 = 6 days.",
                    json.dumps({"A": "Common misconception assuming linear single unit.", "C": "Calculation error.", "D": "Inversion error."})
                ))

        # 3. SAMPLE TECHNICAL AGRICULTURE (Q51 to Q100)
        for i in range(51, 101):
            if i == 51:
                qs.append((
                    exam_id, 51, "Agri", "Federal PSC 2078", 0,
                    "The 20-year Agriculture Development Strategy (ADS, 2015-2035) of Nepal has identified how many core strategic pillars/components?",
                    None, "3 Pillars", "4 Pillars", "5 Pillars", "8 Pillars", "B",
                    "ADS operates on 4 core strategic pillars: Governance, Productivity, Commercialization, and Competitiveness.",
                    json.dumps({
                        "A": "3 is incorrect; ADS has 4 distinct pillars.",
                        "C": "5 denotes monitoring indicators and priority commodities.",
                        "D": "8 corresponds to core flagship outcomes, not strategic pillars."
                    })
                ))
            elif i == 52:
                qs.append((
                    exam_id, 52, "Agri", "Bagmati PSC 2081", 0,
                    "Which physiological disorder of cauliflower is caused by the deficiency of Molybdenum (Mo) in acidic soils?",
                    None, "Browning", "Whiptail", "Buttoning", "Black heart", "B",
                    "Whiptail in Brassicas is caused by Molybdenum deficiency under acidic pH conditions.",
                    json.dumps({
                        "A": "Browning in cauliflower is caused by Boron (B) deficiency.",
                        "C": "Buttoning is caused by severe Nitrogen deficiency or using over-aged nursery seedlings.",
                        "D": "Black heart is a Calcium deficiency disorder common in celery and potato."
                    })
                ))
            else:
                qs.append((
                    exam_id, i, "Agri", "Federal & Province PSC", 0,
                    f"Agricultural Technology & Science Model Question #{i}: What is the primary objective of Integrated Plant Nutrient Management (IPNM)?",
                    None,
                    "Complete prohibition of all mineral chemical fertilizers.",
                    "Judicious and balanced combination of organic manures, bio-fertilizers, and chemical fertilizers.",
                    "Applying single heavy-dose nitrogen fertilizer during vegetative growth only.",
                    "Exclusive dependence on green manuring without soil testing.",
                    "B",
                    "IPNM optimizes crop yields while maintaining long-term soil health through balanced integrated inputs.",
                    json.dumps({
                        "A": "Complete prohibition is Organic farming, not IPNM.",
                        "C": "Single heavy doses cause nitrogen leaching, volatilization, and soil acidification.",
                        "D": "Soil testing is the fundamental prerequisite of IPNM."
                    })
                ))

        cursor.executemany('''
            INSERT INTO questions 
            (exam_id, q_num, category, exam_place, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', qs)
        conn.commit()

seed_sample_exam()

# ----------------- SIDEBAR -----------------
st.sidebar.markdown("<h2 style='color:#10b981; margin-bottom:0;'>🌱 AgriLoksewa 7th</h2>", unsafe_allow_html=True)
st.sidebar.caption("Nepal Agriculture Service (Gazetted 3rd Class / 7th Level)")
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
    st.caption("Strict Blueprint: 25 GK + 25 IQ + 50 Agriculture | Negative Marking: 20% (-0.2 marks)")

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()

    if not exams:
        st.warning("No exams available. Go to the Generator tab to generate one!")
        st.stop()

    exam_map = {f"{e['exam_date']} - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Date:", list(exam_map.keys()))
    selected_exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute(
            "SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC",
            (selected_exam_id,)
        ).fetchall()

    if not questions:
        st.error("No questions found.")
        st.stop()

    # Session State Answers (None initially = unattempted)
    if f"user_ans_{selected_exam_id}" not in st.session_state:
        st.session_state[f"user_ans_{selected_exam_id}"] = {q['q_num']: None for q in questions}

    # Top Status Bar
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("<div style='background:#f1f5f9; padding:10px; border-radius:8px; text-align:center;'><b>Total Questions:</b> 100</div>", unsafe_allow_html=True)
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

    # Exam Form
    with st.form(key=f"exam_form_{selected_exam_id}"):
        for q in questions:
            q_num = q['q_num']
            cat = q['category']
            badge_class = "badge-gk" if cat == "GK" else ("badge-iq" if cat == "IQ" else "badge-agri")

            # Question Header Card
            st.markdown(f"""
            <div class="question-card">
                <div>
                    <span class="badge {badge_class}">{cat}</span>
                    <span class="badge badge-source">{q['exam_place']}</span>
                </div>
                <h4 style="margin: 0.5rem 0 0.8rem 0; color:#0f172a;">Q{q_num}. {q['question_text']}</h4>
            </div>
            """, unsafe_allow_html=True)

            # Main Figure SVG
            if q['figure_svg']:
                st.components.v1.html(q['figure_svg'], height=85)

            current_choice = st.session_state[f"user_ans_{selected_exam_id}"].get(q_num, None)

            # CASE 1: Non-Verbal IQ with FIGURE OPTIONS (None selected initially)
            if q['is_figure_option']:
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

                # Strictly options A, B, C, D with index=None if not yet marked
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

            # CASE 2: Text Options (None selected initially)
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
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        cat = q['category']
        badge_class = "badge-gk" if cat == "GK" else ("badge-iq" if cat == "IQ" else "badge-agri")

        is_correct = (user_pick == correct)
        status_text = "⚪ Unattempted" if user_pick is None else ("✅ Correct" if is_correct else f"❌ Wrong (You: {user_pick})")

        with st.expander(f"Q{q_no}. {q['question_text']} [{status_text}]", expanded=False):
            st.markdown(f'<span class="badge {badge_class}">{cat}</span> <span class="badge badge-source">{q["exam_place"]}</span>', unsafe_allow_html=True)

            if q['figure_svg']:
                st.components.v1.html(q['figure_svg'], height=85)

            if q['is_figure_option']:
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

            if q['option_hints']:
                try:
                    hints = json.loads(q['option_hints'])
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
    st.caption("Generates 100 questions (25 GK + 25 IQ with SVG Non-Verbal Figures + 50 Agri Technical) in 4 parallel batches.")

    api_key = st.text_input("Enter Groq API Key:", type="password", value=os.environ.get("GROQ_API_KEY", ""))
    target_dt = st.date_input("Exam Date:", value=date.today())
    target_title = st.text_input("Exam Title:", value=f"Loksewa Krishi Adhikrit 7th Level - {target_dt}")

    if st.button("🚀 Generate Fresh 100-Question Exam Set", type="primary"):
        if not api_key:
            st.error("Please provide a Groq API Key.")
            st.stop()

        from groq import Groq
        groq_client = Groq(api_key=api_key)

        batches = [
            # Batch 1: 25 GK
            {
                "category": "GK",
                "prompt": f"""
                Generate 25 Loksewa Agriculture 7th Level General Awareness (GK) questions in JSON.
                Topics: Geography of Nepal (Census 2078), Constitution (Articles 36, Part 1-5, Schedules), 16th Plan targets, Civil Service Act 2049, Governance, Budget, SDGs.
                Language: Nepali.
                Include 'exam_place' tag (e.g. 'Federal PSC 2080', 'Bagmati PSC 2081').
                Format: JSON array of 25 objects:
                [{{"q_num": 1, "category": "GK", "exam_place": "Federal PSC 2080", "is_figure_option": 0, "question_text": "...", "figure_svg": null, "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "explanation": "...", "option_hints": {{"B":"note","C":"note","D":"note"}}}}]
                Number strictly from 1 to 25.
                """
            },
            # Batch 2: 25 IQ with Non-Verbal Figure Options
            {
                "category": "IQ",
                "prompt": f"""
                Generate 25 Loksewa IQ questions (numbered 26 to 50):
                - Q26-Q42: Verbal and Numerical reasoning. is_figure_option: 0.
                - Q43-Q50: NON-VERBAL SPATIAL REASONING WITH FIGURE OPTIONS! 
                  For Q43-Q50:
                  - set "is_figure_option": 1
                  - "figure_svg": Inline SVG code for the Problem Figure (width 220, height 70)
                  - "option_a", "option_b", "option_c", "option_d": Inline SVG code for each of the 4 answer figures (width 70, height 60)!
                Format: JSON array of 25 objects numbered 26 to 50.
                """
            },
            # Batch 3: 25 Agri Part A
            {
                "category": "Agri",
                "prompt": f"""
                Generate 25 Technical Agriculture questions (numbered 51 to 75) for 7th Level Officer:
                Topics: History of DoA/NARC, Extension (FFS, T&V, AKC), ADS 2015-2035 (4 pillars, targets), Seeds Act 2045, Pesticides Act 2076, WTO SPS.
                Language: English.
                Provide informative 'option_hints' for all incorrect options. is_figure_option: 0.
                Format: JSON array of 25 objects numbered 51 to 75.
                """
            },
            # Batch 4: 25 Agri Part B
            {
                "category": "Agri",
                "prompt": f"""
                Generate 25 Technical Agriculture questions (numbered 76 to 100):
                Topics: Agronomy (seed classes, tags, isolation distance), Horticulture (disorders, grafting), Soil (pH, IPNM, NPK), Plant Protection (Fall armyworm, Late blight, ETL), Postharvest.
                Language: English.
                Provide informative 'option_hints' for all incorrect options. is_figure_option: 0.
                Format: JSON array of 25 objects numbered 76 to 100.
                """
            }
        ]

        all_qs = []
        progress = st.progress(0, text="Starting 4-batch generation pipeline...")

        try:
            with st.spinner("Generating 100 questions with SVG figure options..."):
                for idx, b in enumerate(batches):
                    progress.progress((idx + 1) * 25, text=f"Generating Batch {idx+1}/4 ({b['category']})...")
                    comp = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": b["prompt"]}],
                        response_format={"type": "json_object"}
                    )
                    data = json.loads(comp.choices[0].message.content)
                    q_list = data if isinstance(data, list) else data.get("questions", list(data.values())[0])
                    all_qs.extend(q_list)
                    time.sleep(0.5)

                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO exams (exam_date, title, total_questions) VALUES (?, ?, ?)",
                        (str(target_dt), target_title, len(all_qs))
                    )
                    exam_id = cursor.lastrowid

                    for q in all_qs:
                        cursor.execute('''
                            INSERT INTO questions 
                            (exam_id, q_num, category, exam_place, is_figure_option, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            exam_id, q['q_num'], q.get('category', 'Agri'), q.get('exam_place', 'Model PSC'),
                            q.get('is_figure_option', 0), q['question_text'], q.get('figure_svg'),
                            q['option_a'], q['option_b'], q['option_c'], q['option_d'],
                            q['correct_option'], q['explanation'], json.dumps(q.get('option_hints', {}))
                        ))
                    conn.commit()

            st.success(f"🎉 Successfully generated and saved all {len(all_qs)} questions for {target_dt}!")
        except Exception as e:
            st.error(f"Generation error: {e}")
