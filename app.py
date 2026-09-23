import streamlit as st
import sqlite3
import json
from datetime import datetime, date
import pandas as pd
import os
from groq import Groq

# ----------------- PAGE CONFIG -----------------
st.set_page_set_up = st.set_page_config(
    page_title="Loksewa Agriculture Officer Exam Portal",
    page_icon="🌱",
    layout="wide"
)

DB_FILE = "loksewa_exams.db"

# ----------------- DATABASE SETUP -----------------
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Exams Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_date TEXT UNIQUE,
                title TEXT,
                total_questions INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Questions Table (with figure_svg for visual IQ)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                q_num INTEGER,
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
        
        # Attempts Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                attempt_date TEXT,
                total_attempted INTEGER,
                correct_count INTEGER,
                wrong_count INTEGER,
                score REAL,
                user_answers TEXT,
                FOREIGN KEY(exam_id) REFERENCES exams(id)
            )
        ''')
        conn.commit()

init_db()

# ----------------- HELPER SEED DATA (IF DB EMPTY) -----------------
def seed_sample_exam():
    with get_db() as conn:
        cursor = conn.cursor()
        today_str = str(date.today())
        cursor.execute("SELECT id FROM exams WHERE exam_date = ?", (today_str,))
        if cursor.fetchone():
            return

        cursor.execute("INSERT INTO exams (exam_date, title, total_questions) VALUES (?, ?, ?)",
                       (today_str, f"Daily Mock Set - {today_str}", 4))
        exam_id = cursor.lastrowid

        # Sample Questions demonstrating General, Visual IQ (SVG), and Agriculture with option hints
        sample_qs = [
            (
                exam_id, 1,
                "नेपालको संविधानको कुन धारामा खाद्य सम्बन्धी हक (खाद्य सम्प्रभुता) को व्यवस्था गरिएको छ?",
                None,
                "धारा ३३", "धारा ३६", "धारा ३८", "धारा ४०",
                "B",
                "धारा ३६ मा खाद्य सम्बन्धी हक र खाद्य सम्प्रभुताको प्रत्याभूति गरिएको छ।",
                json.dumps({
                    "A": "धारा ३३ रोजगारीको हकसँग सम्बन्धित छ।",
                    "C": "धारा ३८ महिलाको हकसँग सम्बन्धित छ।",
                    "D": "धारा ४० दलितको हकसँग सम्बन्धित छ।"
                })
            ),
            (
                exam_id, 2,
                "[Spatial IQ] तल दिइएको म्याट्रिक्स चित्रमा प्रश्नचिह्न (?) भएको ठाउँमा कुन आकृति हुनुपर्छ?",
                """<svg width="220" height="70" style="background:#f8f9fa; border:1px solid #ccc; border-radius:6px;">
                    <!-- Cell 1: Circle -->
                    <circle cx="35" cy="35" r="18" fill="none" stroke="#2563eb" stroke-width="3" />
                    <!-- Arrow -->
                    <text x="65" y="40" font-size="20" fill="#666">→</text>
                    <!-- Cell 2: Circle with dot -->
                    <circle cx="105" cy="35" r="18" fill="none" stroke="#2563eb" stroke-width="3" />
                    <circle cx="105" cy="35" r="5" fill="#2563eb" />
                    <!-- Separator -->
                    <text x="135" y="40" font-size="20" fill="#666">::</text>
                    <!-- Cell 3: Square -->
                    <rect x="155" y="20" width="30" height="30" fill="none" stroke="#dc2626" stroke-width="3" />
                    <text x="195" y="40" font-size="20" fill="#666">→</text>
                    <text x="210" y="40" font-size="22" font-weight="bold" fill="#dc2626">?</text>
                   </svg>""",
                "Square with inner circle", "Square with inner dot", "Triangle with dot", "Double square",
                "B",
                "पहिलो जोडीमा वृत्तभित्र थोप्लो (dot) थपिए जस्तै, दोस्रो जोडीमा वर्गभित्र थोप्लो थपिनुपर्छ।",
                json.dumps({
                    "A": "Inner circle pattern नियम अनुसार छैन।",
                    "C": "Triangle shape परिवर्तन गर्ने नियम यहाँ लागू हुँदैन।",
                    "D": "Double square आकार दोहोर्‍याउने नियम होइन।"
                })
            ),
            (
                exam_id, 3,
                "The 20-year Agriculture Development Strategy (ADS, 2015–2035) has identified how many core strategic pillars?",
                None,
                "3 Pillars", "4 Pillars", "5 Pillars", "8 Pillars",
                "B",
                "ADS has 4 core pillars: Governance, Productivity, Commercialization, and Competitiveness.",
                json.dumps({
                    "A": "3 pillars is incorrect; ADS operates strictly on 4 pillars.",
                    "C": "5 is the number of monitoring dimensions, not pillars.",
                    "D": "8 corresponds to core flagship programs, not primary strategic pillars."
                })
            ),
            (
                exam_id, 4,
                "Which physiological disorder of cauliflower is caused by the deficiency of Molybdenum (Mo) in acidic soils?",
                None,
                "Browning", "Whiptail", "Buttoning", "Black heart",
                "B",
                "Whiptail of cauliflower is caused by Molybdenum (Mo) deficiency.",
                json.dumps({
                    "A": "Browning in cauliflower is caused by Boron (B) deficiency.",
                    "C": "Buttoning is caused by severe Nitrogen deficiency or transplanting older seedlings.",
                    "D": "Black heart is a Calcium deficiency disorder common in celery and potato, not cauliflower."
                })
            )
        ]
        cursor.executemany('''
            INSERT INTO questions 
            (exam_id, q_num, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_qs)
        conn.commit()

seed_sample_exam()

# ----------------- SIDEBAR NAVIGATION -----------------
st.sidebar.title("🌱 Loksewa Agri Portal")
st.sidebar.caption("Gazetted 3rd Class / Technical Officer")
menu = st.sidebar.radio(
    "Navigation",
    ["📝 Take Daily Exam", "📖 Review Past Exams & Hints", "📊 Score History & Analytics", "⚙️ Exam Manager (Groq AI)"]
)

# =======================================================
# 1. TAKE DAILY EXAM
# =======================================================
if menu == "📝 Take Daily Exam":
    st.header("📝 Daily Loksewa Model Exam")
    
    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()
    
    if not exams:
        st.warning("No exams available in the database yet!")
        st.stop()
        
    exam_options = {f"{e['exam_date']} - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam Date:", list(exam_options.keys()))
    selected_exam_id = exam_options[selected_label]
    
    # Load Questions for the chosen exam
    with get_db() as conn:
        questions = conn.execute(
            "SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", 
            (selected_exam_id,)
        ).fetchall()
        
    if not questions:
        st.info("No questions found for this exam.")
        st.stop()
        
    st.markdown(f"**Total Questions:** {len(questions)} | **Negative Marking:** 20% (-0.2 marks per wrong answer)")
    st.divider()
    
    # Form for Exam Submission
    with st.form(key=f"exam_form_{selected_exam_id}"):
        user_responses = {}
        for q in questions:
            st.markdown(f"#### Q{q['q_num']}. {q['question_text']}")
            
            # Display SVG visual figure if present (for IQ)
            if q['figure_svg']:
                st.components.v1.html(q['figure_svg'], height=90)
                
            options = {
                "A": q['option_a'],
                "B": q['option_b'],
                "C": q['option_c'],
                "D": q['option_d']
            }
            
            # Radio option (None selected initially)
            choice = st.radio(
                label=f"Select answer for Q{q['q_num']}",
                options=["None", "A", "B", "C", "D"],
                format_func=lambda x: f"({x}) {options[x]}" if x in options else "Skip / Unattempted",
                key=f"q_{q['id']}",
                label_visibility="collapsed"
            )
            user_responses[q['q_num']] = choice
            st.write("---")
            
        submitted = st.form_submit_button("Submit Exam & Calculate Score", type="primary", use_container_width=True)
        
        if submitted:
            correct_count = 0
            wrong_count = 0
            unattempted_count = 0
            
            for q in questions:
                q_ans = user_responses.get(q['q_num'], "None")
                if q_ans == "None":
                    unattempted_count += 1
                elif q_ans == q['correct_option']:
                    correct_count += 1
                else:
                    wrong_count += 1
                    
            # 20% Negative Marking
            final_score = round((correct_count * 1.0) - (wrong_count * 0.20), 2)
            
            # Save into Attempts table
            with get_db() as conn:
                conn.execute('''
                    INSERT INTO attempts (exam_id, attempt_date, total_attempted, correct_count, wrong_count, score, user_answers)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    selected_exam_id, 
                    str(datetime.now().strftime("%Y-%m-%d %H:%M")), 
                    (correct_count + wrong_count), 
                    correct_count, 
                    wrong_count, 
                    final_score, 
                    json.dumps(user_responses)
                ))
                conn.commit()
                
            st.success("🎉 Exam Submitted Successfully!")
            st.balloons()
            
            # Show Result Card
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Final Score", f"{final_score} / {len(questions)}")
            col2.metric("Correct", f"{correct_count} ✅")
            col3.metric("Wrong (-20%)", f"{wrong_count} ❌")
            col4.metric("Unattempted", f"{unattempted_count} ⚪")
            
            st.info("💡 Visit the **'📖 Review Past Exams & Hints'** tab in the sidebar to review detailed hints and option breakdowns!")

# =======================================================
# 2. REVIEW PAST EXAMS & HINTS
# =======================================================
elif menu == "📖 Review Past Exams & Hints":
    st.header("📖 Question Bank & Detailed Review")
    
    with get_db() as conn:
        exams = conn.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()
        
    if not exams:
        st.warning("No exams stored yet.")
        st.stop()
        
    exam_dict = {f"{e['exam_date']} - {e['title']}": e['id'] for e in exams}
    selected_label = st.selectbox("Select Exam to View:", list(exam_dict.keys()))
    exam_id = exam_dict[selected_label]
    
    with get_db() as conn:
        questions = conn.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY q_num ASC", (exam_id,)).fetchall()
        latest_attempt = conn.execute(
            "SELECT * FROM attempts WHERE exam_id = ? ORDER BY id DESC LIMIT 1", (exam_id,)
        ).fetchone()
        
    user_choices = {}
    if latest_attempt and latest_attempt['user_answers']:
        user_choices = json.loads(latest_attempt['user_answers'])
        st.caption(f"Showing comparison with your attempt on: **{latest_attempt['attempt_date']}** (Score: {latest_attempt['score']})")

    for q in questions:
        q_no = str(q['q_num'])
        user_ans = user_choices.get(q_no, "N/A")
        correct_ans = q['correct_option']
        
        # Color coding title
        status_badge = "⚪ Not attempted"
        if user_ans == correct_ans:
            status_badge = "✅ Correct"
        elif user_ans != "N/A" and user_ans != "None":
            status_badge = f"❌ Wrong (Your Choice: {user_ans})"
            
        with st.expander(f"Q{q['q_num']}. {q['question_text']}  [{status_badge}]", expanded=True):
            if q['figure_svg']:
                st.components.v1.html(q['figure_svg'], height=90)
                
            colA, colB = st.columns(2)
            colA.markdown(f"**A:** {q['option_a']}")
            colA.markdown(f"**B:** {q['option_b']}")
            colB.markdown(f"**C:** {q['option_c']}")
            colB.markdown(f"**D:** {q['option_d']}")
            
            st.markdown(f"**Correct Option:** `:green[{correct_ans}]`")
            st.info(f"**Key Hint / Explanation:** {q['explanation']}")
            
            # Technical hints for other options
            if q['option_hints']:
                hints = json.loads(q['option_hints'])
                st.markdown("**🔍 Detailed Breakdown of Other Options:**")
                for opt, note in hints.items():
                    st.write(f"- **Option ({opt})**: {note}")

# =======================================================
# 3. SCORE HISTORY & ANALYTICS
# =======================================================
elif menu == "📊 Score History & Analytics":
    st.header("📊 Performance & Score History")
    
    with get_db() as conn:
        attempts = conn.execute('''
            SELECT a.id, e.exam_date, e.title, a.attempt_date, a.score, a.correct_count, a.wrong_count, a.total_attempted
            FROM attempts a
            JOIN exams e ON a.exam_id = e.id
            ORDER BY a.id ASC
        ''').fetchall()
        
    if not attempts:
        st.info("No exam attempts recorded yet. Attempt an exam first!")
        st.stop()
        
    df = pd.DataFrame([dict(a) for a in attempts])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Tests Taken", len(df))
    col2.metric("Highest Score", f"{df['score'].max()} pts")
    col3.metric("Average Score", f"{round(df['score'].mean(), 2)} pts")
    
    st.subheader("Progress Over Time")
    st.line_chart(df.set_index('attempt_date')['score'])
    
    st.subheader("Attempt History Records")
    st.dataframe(df[['exam_date', 'title', 'attempt_date', 'score', 'correct_count', 'wrong_count']], use_container_width=True)

# =======================================================
# 4. EXAM MANAGER (AI QUESTION GENERATOR)
# =======================================================
elif menu == "⚙️ Exam Manager (Groq AI)":
    st.header("⚙️ Generate Daily Exam via Groq API")
    st.markdown("Use **Groq API** to generate a new syllabus-based exam and save it to the database by date.")
    
    groq_api_key = st.text_input("Enter Groq API Key:", type="password", value=os.environ.get("GROQ_API_KEY", ""))
    target_date = st.date_input("Exam Date:", value=date.today())
    target_title = st.text_input("Exam Title:", value=f"Agriculture Officer Mock - {target_date}")
    
    if st.button("Generate & Save New Exam", type="primary"):
        if not groq_api_key:
            st.error("Please provide a Groq API Key to proceed.")
            st.stop()
            
        with st.spinner("Generating syllabus-based questions with option breakdowns using Groq..."):
            try:
                client = Groq(api_key=groq_api_key)
                prompt = """
                Generate 5 Loksewa Agriculture Officer (Gazetted 3rd class) exam questions in strictly valid JSON format.
                Include:
                - 1 GK question (Nepal Geography/Constitution/Plan)
                - 1 Spatial/Logical IQ question (describe figure clearly or give clean inline SVG)
                - 3 Core Agriculture questions (Agronomy, Soil Science, ADS/Policies, Plant Protection)
                
                For technical questions, provide breakdown notes for all wrong options as well.
                
                Respond ONLY with a JSON array formatted as:
                [
                  {
                    "q_num": 1,
                    "question_text": "...",
                    "figure_svg": null,
                    "option_a": "...",
                    "option_b": "...",
                    "option_c": "...",
                    "option_d": "...",
                    "correct_option": "A/B/C/D",
                    "explanation": "...",
                    "option_hints": {"B": "note", "C": "note", "D": "note"}
                  }
                ]
                """
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                
                raw_content = completion.choices[0].message.content
                data = json.loads(raw_content)
                questions_list = data if isinstance(data, list) else data.get("questions", [])
                
                if not questions_list:
                    st.error("Could not parse question list from response.")
                    st.stop()
                    
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR REPLACE INTO exams (exam_date, title, total_questions) VALUES (?, ?, ?)",
                                   (str(target_date), target_title, len(questions_list)))
                    exam_id = cursor.lastrowid
                    
                    for q in questions_list:
                        cursor.execute('''
                            INSERT INTO questions 
                            (exam_id, q_num, question_text, figure_svg, option_a, option_b, option_c, option_d, correct_option, explanation, option_hints)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            exam_id,
                            q['q_num'],
                            q['question_text'],
                            q.get('figure_svg'),
                            q['option_a'],
                            q['option_b'],
                            q['option_c'],
                            q['option_d'],
                            q['correct_option'],
                            q['explanation'],
                            json.dumps(q.get('option_hints', {}))
                        ))
                    conn.commit()
                    
                st.success(f"Successfully generated and saved {len(questions_list)} questions for {target_date}!")
            except Exception as e:
                st.error(f"Error generating exam: {e}")
