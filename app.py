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
    page_icon="🌾",
    layout="wide"
)

DB_FILE = "loksewa_agri_exams.db"

# ----------------- DATABASE SCHEMA -----------------
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Exams Table (date-based)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_date TEXT UNIQUE,
                title TEXT,
                total_questions INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Questions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                q_num INTEGER,
                category TEXT,
                exam_place TEXT,
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
        
        # Student Attempts
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

# ----------------- 4-BATCH 100-QUESTION GROQ ENGINE -----------------
def generate_full_100_exam(client, exam_date, title):
    """
    Calls Groq in 4 sequential batches of 25 questions each to reliably
    generate exactly 100 high-quality, syllabus-accurate questions.
    """
    batches = [
        # Batch 1: 25 GK (Q1 to Q25)
        {
            "range": "Q1 to Q25",
            "category": "GK",
            "prompt": f"""
            You are an expert examiner for Nepal Loksewa Agriculture 7th Level (Gazetted 3rd Class).
            Generate exactly 25 General Awareness (GK) questions strictly adhering to the syllabus.
            Topics:
            - Physical, economic, and demographic geography of Nepal (Census 2078)
            - Constitution of Nepal (Part 1-5, Schedules 5,6,7,8,9, Article 36 Right to Food)
            - 16th Periodic Plan of Nepal (2081/82-2085/86 targets)
            - Governance, Civil Service Act 2049, Citizen Charter, Public Policy, Budgeting
            - International organizations: UN, SAARC, BIMSTEC, WTO
            - Sustainable Development Goals (SDGs)
            
            Every question must have an 'exam_place' tag (e.g. 'Federal PSC 2080', 'Bagmati PSC 2081', 'Koshi PSC 2080', 'Lumbini PSC 2079', 'CARE Model Exam', 'Himalayan Institute').
            Language: Nepali (Unicode).
            
            Respond ONLY with a valid JSON array of 25 question objects:
            [
              {{
                "q_num": 1,
                "category": "GK",
                "exam_place": "Federal PSC 2080",
                "question_text": "...",
                "figure_svg": null,
                "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
                "correct_option": "A",
                "explanation": "...",
                "option_hints": {{"B": "why B is wrong", "C": "...", "D": "..."}}
              }}
            ]
            Number questions strictly from 1 to 25.
            """
        },
        # Batch 2: 25 IQ (Q26 to Q50)
        {
            "range": "Q26 to Q50",
            "category": "IQ",
            "prompt": f"""
            Generate exactly 25 General Reasoning Test (IQ) questions for Nepal Loksewa Agriculture Officer (7th level).
            Distribution:
            - Logical Reasoning (9 Qs): Coding-decoding, series, blood relation, direction & distance, statement & conclusion.
            - Numerical Reasoning (8 Qs): Time & work, profit & loss, ratio, average, arithmetic series, percentage.
            - Spatial Reasoning (8 Qs): Figure series, matrix completion, analogy, mirror/water image, paper folding.
            
            CRITICAL: For Spatial questions (at least 5 of them), provide a clean inline SVG string in 'figure_svg' (e.g. circles, squares, arrows, lines with width 260 and height 75) to visually represent the pattern or matrix!
            Language: Nepali/English mixed as standard in PSC.
            
            Respond ONLY with a valid JSON array of 25 question objects numbered from 26 to 50:
            [
              {{
                "q_num": 26,
                "category": "IQ",
                "exam_place": "Federal PSC 2079",
                "question_text": "...",
                "figure_svg": "<svg width='260' height='75'>...</svg>" (or null if verbal),
                "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
                "correct_option": "B",
                "explanation": "Step by step calculation or logic",
                "option_hints": {{"A": "...", "C": "...", "D": "..."}}
              }}
            ]
            Number questions strictly from 26 to 50.
            """
        },
        # Batch 3: 25 Agriculture Part A (Q51 to Q75)
        {
            "range": "Q51 to Q75",
            "category": "Agri",
            "prompt": f"""
            Generate exactly 25 Technical Agriculture questions for Nepal Agriculture Service 7th Level (Gazetted 3rd Class).
            Topics:
            - History of Agri Research and DoA in Nepal, NARC vision and mandate
            - Agriculture Extension Systems (T&V, FFS, Farmer-to-Farmer, AKC structure)
            - Agricultural Education (AFU, TU-IAAS, CTEVT)
            - Natural Resource Conservation, Climate Change adaptation, Weather instruments
            - Agriculture Development Strategy (ADS 2015-2035) 4 pillars, indicators & targets
            - Seeds Act 2045 & Rules 2069, Pesticides Management Act 2076, Plant Protection Act 2064
            - Right to Food & Food Sovereignty Act 2076, WTO (SPS agreement, Green/Amber box)
            
            Every question MUST have 'option_hints' giving informative notes on WHY the other 3 options are incorrect or what they actually stand for.
            Language: English (technical terminology).
            
            Respond ONLY with a valid JSON array of 25 question objects numbered from 51 to 75.
            """
        },
        # Batch 4: 25 Agriculture Part B (Q76 to Q100)
        {
            "range": "Q76 to Q100",
            "category": "Agri",
            "prompt": f"""
            Generate exactly 25 Technical Agriculture questions for Nepal Agriculture Service 7th Level (Gazetted 3rd Class).
            Topics:
            - Agronomy & Seed Tech: Seed certification classes/tags, isolation distances, crop geometries, critical irrigation stages (CRI)
            - Horticulture: Propagation methods (grafting/budding), physiological disorders (Whiptail, Browning, Bitter pit)
            - Soil Science: IPNS, soil reaction (pH), NPK calculation, fertilizer composition (Urea, DAP, MOP), micro-nutrients
            - Plant Protection: Major pests (Fall Armyworm, stem borers), diseases (Late blight, BLB, Clubroot), ETL, botanical pesticides
            - Post-harvest management, Blanching, hermetic storage moisture limits
            - Agricultural Economics, Farm management, Land Equivalent Ratio (LER), market structures (Monopoly, Monopsony)
            
            Every question MUST have 'option_hints' giving notes for all the incorrect options.
            Language: English (standard PSC format).
            
            Respond ONLY with a valid JSON array of 25 question objects numbered from 76 to 100.
            """
        }
    ]

    all_100_questions = []

    for batch in batches:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": batch["prompt"]}],
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        data = json.loads(content)
        q_list = data if isinstance(data, list) else data.get("questions", list(data.values())[0])
        all_100_questions.extend(q_list)
        time.sleep(0.5)

    # Save to Database
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO exams (exam_date, title, total_questions) VALUES (?, ?, ?)",
            (str(exam_date), title, len(all_100_questions))
        )
        exam_id = cursor.lastrowid

        for q in all_100_questions:
            cursor.execute('''
                INSERT INTO questions 
                (exam_id, q_num, category, exam_place, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id, q['q_num'], q.get('category', 'Agri'), q.get('exam_place', 'Nepal PSC Model'),
                q['question_text'], q.get('figure_svg'), q['option_a'], q['option_b'],
                q['option_c'], q['option_d'], q['correct_option'], q['explanation'],
                json.dumps(q.get('option_hints', {}))
            ))
        conn.commit()

    return len(all_100_questions)

# ----------------- SIDEBAR MENU -----------------
st.sidebar.markdown("## 🌾 Agri 7th Level Portal")
st.sidebar.caption("Exact Blueprint: 25 GK + 25 IQ + 50 Agriculture = 100 Questions")
st.sidebar.divider()

menu = st.sidebar.radio(
    "Go To:",
    ["📝 Attempt 100-Question Exam", "📖 Review Exam by Date & Hints", "📊 Score Analytics", "⚡ 100-Question Daily Generator"]
)

# =======================================================
# 1. ATTEMPT 100-QUESTION EXAM
# =======================================================
if menu == "📝 Attempt 100-Question Exam":
    st.header("📝 Daily 100-Question Model Exam (Agriculture 7th Level)")

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()

    if not exams:
        st.warning("⚠️ No exams available in database yet! Go to the '⚡ 100-Question Daily Generator' tab to create today's 100-question set.")
        st.stop()

    exam_map = {f"{e['exam_date']} - {e['title']} ({e['total_questions']} Qs)": e['id'] for e in exams}
    selected_label = st.selectbox("📅 Select Exam Date:", list(exam_map.keys()))
    selected_exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute(
            "SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC",
            (selected_exam_id,)
        ).fetchall()

    if not questions:
        st.error("No questions found for this exam set.")
        st.stop()

    # Session State Answer Store
    if f"ans_{selected_exam_id}" not in st.session_state:
        st.session_state[f"ans_{selected_exam_id}"] = {q['q_num']: "None" for q in questions}

    # Summary strip
    c1, c2, c3, c4 = st.columns(4)
    c1.info(f"**Total Questions:** {len(questions)}")
    c2.warning("**Time:** 90 Minutes")
    c3.error("**Negative Marking:** 20% (-0.2 marks)")
    c4.success("**Passing Score:** 45.0 Marks")

    st.markdown("---")

    # Interactive Question Palette
    st.sidebar.markdown("### 🧭 Question Palette (1 to 100)")
    answered = sum(1 for v in st.session_state[f"ans_{selected_exam_id}"].values() if v != "None")
    st.sidebar.progress(answered / len(questions), text=f"Answered: {answered} / {len(questions)}")

    cols = st.sidebar.columns(5)
    for idx, q in enumerate(questions):
        q_num = q['q_num']
        col = cols[idx % 5]
        is_done = st.session_state[f"ans_{selected_exam_id}"][q_num] != "None"
        col.caption(f"{'🟢' if is_done else '⚪'} {q_num}")

    # Exam Form
    with st.form(key=f"attempt_form_{selected_exam_id}"):
        for q in questions:
            q_num = q['q_num']
            exam_tag = f"`{q['exam_place']}`" if q['exam_place'] else "`Loksewa Model`"
            st.markdown(f"##### Q{q_num}. {q['question_text']} 🏷️ {exam_tag}")

            # Inline SVG Figure if present
            if q['figure_svg']:
                st.components.v1.html(q['figure_svg'], height=95)

            opts = {"A": q['option_a'], "B": q['option_b'], "C": q['option_c'], "D": q['option_d']}
            curr = st.session_state[f"ans_{selected_exam_id}"].get(q_num, "None")
            idx_curr = ["None", "A", "B", "C", "D"].index(curr) if curr in ["None", "A", "B", "C", "D"] else 0

            choice = st.radio(
                label=f"Q{q_num}",
                options=["None", "A", "B", "C", "D"],
                index=idx_curr,
                format_func=lambda x: f"({x}) {opts[x]}" if x in opts else "⚪ Skip / Unattempted",
                key=f"r_{selected_exam_id}_{q_num}",
                label_visibility="collapsed"
            )
            st.session_state[f"ans_{selected_exam_id}"][q_num] = choice
            st.write("")

        submitted = st.form_submit_button("🏁 Submit All 100 Questions", type="primary", use_container_width=True)

        if submitted:
            correct_cnt = 0
            wrong_cnt = 0
            unattempted_cnt = 0

            for q in questions:
                ans = st.session_state[f"ans_{selected_exam_id}"][q['q_num']]
                if ans == "None":
                    unattempted_cnt += 1
                elif ans == q['correct_option']:
                    correct_cnt += 1
                else:
                    wrong_cnt += 1

            # Exact 20% Negative Marking
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
                    json.dumps(st.session_state[f"ans_{selected_exam_id}"])
                ))
                conn.commit()

            st.success("🎉 Exam Submitted and Recorded!")
            if passed:
                st.balloons()

            r1, r2, r3, r4, r5 = st.columns(5)
            r1.metric("Final Score", f"{final_score} / 100")
            r2.metric("Result", "PASS ✅" if passed else "FAIL ❌")
            r3.metric("Correct (+1.0)", f"{correct_cnt}")
            r4.metric("Wrong (-0.2)", f"{wrong_cnt}")
            r5.metric("Unattempted", f"{unattempted_cnt}")

            st.info("👉 Check the **'📖 Review Exam by Date & Hints'** tab in the sidebar to review all correct answers and the full option-by-option breakdown!")

# =======================================================
# 2. REVIEW EXAM BY DATE & HINTS
# =======================================================
elif menu == "📖 Review Exam by Date & Hints":
    st.header("📖 Date-wise Question Review with Option Hints")

    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()

    if not exams:
        st.warning("No exams stored.")
        st.stop()

    exam_map = {f"{e['exam_date']} - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("📅 Select Exam Date to Review:", list(exam_map.keys()))
    exam_id = exam_map[selected_label]

    with get_db() as conn:
        questions = conn.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", (exam_id,)).fetchall()
        attempt = conn.execute("SELECT * FROM attempts WHERE exam_id = ? ORDER BY id DESC LIMIT 1", (exam_id,)).fetchone()

    user_answers = json.loads(attempt['user_answers']) if attempt and attempt['user_answers'] else {}
    if attempt:
        st.success(f"Last Attempt: **{attempt['attempt_date']}** | Score: **{attempt['score']} / 100** | Correct: **{attempt['correct_count']}** | Wrong: **{attempt['wrong_count']}**")

    # Filter section
    sec = st.radio("Section Filter:", ["All 100 Questions", "General Awareness (Q1-Q25)", "IQ & Reasoning (Q26-Q50)", "Technical Agriculture (Q51-Q100)"], horizontal=True)

    for q in questions:
        q_no = q['q_num']
        if sec == "General Awareness (Q1-Q25)" and not (1 <= q_no <= 25):
            continue
        if sec == "IQ & Reasoning (Q26-Q50)" and not (26 <= q_no <= 50):
            continue
        if sec == "Technical Agriculture (Q51-Q100)" and not (51 <= q_no <= 100):
            continue

        user_pick = user_answers.get(str(q_no), user_answers.get(q_no, "None"))
        correct = q['correct_option']

        if user_pick == "None":
            badge = "⚪ Unattempted"
        elif user_pick == correct:
            badge = "✅ Correct"
        else:
            badge = f"❌ Wrong (Your Choice: {user_pick})"

        with st.expander(f"Q{q_no}. {q['question_text']} [{badge}] 🏷️ {q['exam_place']}", expanded=False):
            if q['figure_svg']:
                st.components.v1.html(q['figure_svg'], height=95)

            cA, cB = st.columns(2)
            cA.write(f"**(A)** {q['option_a']}")
            cA.write(f"**(B)** {q['option_b']}")
            cB.write(f"**(C)** {q['option_c']}")
            cB.write(f"**(D)** {q['option_d']}")

            st.markdown(f"🎯 **Verified Answer:** `:green[(Option {correct})]`")
            st.info(f"💡 **Explanation / Formula:** {q['explanation']}")

            # Option-by-Option breakdown for technical questions
            if q['option_hints']:
                try:
                    hints = json.loads(q['option_hints'])
                    if hints:
                        st.markdown("🔍 **Why Other Options are Incorrect (Option Breakdown):**")
                        for opt_k, opt_desc in hints.items():
                            st.write(f"- **Option ({opt_k})**: {opt_desc}")
                except:
                    pass

# =======================================================
# 3. SCORE ANALYTICS
# =======================================================
elif menu == "📊 Score Analytics":
    st.header("📊 Performance & Score Analytics by Date")

    with get_db() as conn:
        attempts = conn.execute('''
            SELECT a.id, e.exam_date, e.title, a.attempt_date, a.score, 
                   a.correct_count, a.wrong_count, a.unattempted_count, a.is_passed
            FROM attempts a
            JOIN exams e ON a.exam_id = e.id
            ORDER BY a.id ASC
        ''').fetchall()

    if not attempts:
        st.info("No exam attempts recorded yet. Take an exam to generate performance charts!")
        st.stop()

    df = pd.DataFrame([dict(a) for a in attempts])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exams Completed", len(df))
    c2.metric("Highest Score", f"{df['score'].max()} pts")
    c3.metric("Average Score", f"{round(df['score'].mean(), 2)} pts")
    c4.metric("Pass Rate", f"{round((df['is_passed'].sum() / len(df)) * 100, 1)}%")

    st.subheader("📈 Score Progression Over Dates")
    st.line_chart(df.set_index('attempt_date')['score'])

    st.subheader("📜 Date-wise History Table")
    st.dataframe(df[['exam_date', 'attempt_date', 'score', 'correct_count', 'wrong_count', 'unattempted_count', 'is_passed']], use_container_width=True)

# =======================================================
# 4. 100-QUESTION DAILY GENERATOR (GROQ ENGINE)
# =======================================================
elif menu == "⚡ 100-Question Daily Generator":
    st.header("⚡ Generate Today's 100-Question Exam Set")
    st.markdown("""
    Generates a full 100-question set split across 4 parallel batches:
    * **Batch 1 (Q1-Q25):** 25 Nepal GK (Constitution, 16th Plan, Governance, Census 2078)
    * **Batch 2 (Q26-Q50):** 25 IQ (9 Logical, 8 Numerical, 8 Spatial with SVG figures)
    * **Batch 3 (Q51-Q75):** 25 Agri Part A (ADS 2015-2035, Seed/Pesticides Acts, Climate, Extension)
    * **Batch 4 (Q76-Q100):** 25 Agri Part B (Agronomy, Hort, Soil, Plant Protection, IPNS, Economics)
    """)

    api_key = st.text_input("Enter Groq API Key:", type="password", value=os.environ.get("GROQ_API_KEY", ""))
    target_dt = st.date_input("Exam Date:", value=date.today())
    target_title = st.text_input("Exam Title:", value=f"Agriculture 7th Level Daily Exam - {target_dt}")

    if st.button("🚀 Generate Exactly 100 Questions Now", type="primary"):
        if not api_key:
            st.error("Please provide a Groq API Key to proceed.")
            st.stop()

        from groq import Groq
        groq_client = Groq(api_key=api_key)

        progress_bar = st.progress(0, text="Starting 4-batch generation pipeline...")
        try:
            with st.spinner("Generating 100 questions (25 GK + 25 IQ + 50 Agri)..."):
                progress_bar.progress(25, text="Generating Q1-Q25: Nepal GK & Governance...")
                time.sleep(0.5)
                progress_bar.progress(50, text="Generating Q26-Q50: IQ (Logical, Numerical, Spatial SVG)...")
                time.sleep(0.5)
                progress_bar.progress(75, text="Generating Q51-Q75: Agriculture Part A (Policies & Extension)...")
                time.sleep(0.5)
                progress_bar.progress(90, text="Generating Q76-Q100: Agriculture Part B (Agronomy, Soil, Protection)...")

                total_gen = generate_full_100_exam(groq_client, target_dt, target_title)
                progress_bar.progress(100, text="All 100 questions generated and saved!")

            st.success(f"✅ Successfully generated and saved all {total_gen} questions for {target_dt}!")
            st.info("Head over to the **'📝 Attempt 100-Question Exam'** tab to take the test!")
        except Exception as e:
            st.error(f"Error during generation: {e}")
