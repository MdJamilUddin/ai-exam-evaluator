import os
import sqlite3
import streamlit as st
import pandas as pd
from google import genai
from PIL import Image

# পেজ কনফিগারেশন
st.set_page_config(
    page_title="বার্ষিক পরীক্ষা - AI খাতা মূল্যায়ন সিস্টেম",
    page_icon="🏫",
    layout="wide"
)

# ডাটাবেس ইনিশিয়ালাইজেশন
def init_db():
    conn = sqlite3.connect("annual_exam_results.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT,
            student_name TEXT,
            roll_number TEXT,
            total_marks_obtained REAL,
            total_full_marks REAL,
            detailed_evaluation TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# জেমিনি ক্লায়েন্ট ইনিশিয়ালাইজেশন
try:
    client = genai.Client()
except Exception as e:
    st.error(f"Gemini API Client তৈরিতে সমস্যা হয়েছে: {e}")

st.title("🏫 বার্ষিক পরীক্ষা: এআই (AI) ভিত্তিক উত্তরপত্র মূল্যায়ন সিস্টেম")
st.markdown("আপনার প্রয়োজন অনুযায়ী যত খুশি প্রশ্ন যুক্ত করে ছাত্র-ছাত্রীদের উত্তরপত্র স্বয়ংক্রিয়ভাবে মূল্যায়ন করুন।")

# সাইডবার: পরীক্ষার সাধারণ তথ্য
st.sidebar.header("📝 পরীক্ষার তথ্য ও প্রশ্নপত্র")
exam_title = st.sidebar.text_input("পরীক্ষার নাম / শ্রেণি", "বার্ষিক পরীক্ষা ২০২৬ - বিজ্ঞান")

st.sidebar.markdown("---")
st.sidebar.subheader("❓ প্রশ্নমালা সেটআপ")

# সেশন স্টেট (Session State) ব্যবহার করে ডায়নামিকভাবে প্রশ্ন বাড়ানোর ব্যবস্থা
if 'question_count' not in st.session_state:
    st.session_state.question_count = 2  # ডিফল্টভাবে ২টি প্রশ্ন থাকবে

# প্রশ্ন বাড়ানোর বা কমানোর বাটন
col_add, col_remove = st.sidebar.columns(2)
if col_add.button("➕ প্রশ্ন যোগ করুন"):
    st.session_state.question_count += 1
    st.rerun()

if col_remove.button("➖ একটি প্রশ্ন মুছুন") and st.session_state.question_count > 1:
    st.session_state.question_count -= 1
    st.rerun()

# যতটি প্রশ্ন সেট করা হয়েছে, লুপ চালিয়ে সেগুলোর ফিল্ড তৈরি করা
questions_data = []
for q_idx in range(1, st.session_state.question_count + 1):
    st.sidebar.markdown(f"**প্রশ্ন নং {q_idx}**")
    q_text = st.sidebar.text_area(f"প্রশ্ন {q_idx} এর বিবরণ", f"প্রশ্ন {q_idx} এখানে লিখুন...", key=f"q_text_{q_idx}")
    q_marks = st.sidebar.number_input(f"পূর্ণমান (Marks)", min_value=1, max_value=100, value=5, key=f"q_marks_{q_idx}")
    q_ans = st.sidebar.text_area(f"আদর্শ উত্তর (Model Answer)", f"সঠিক উত্তর বা মূল পয়েন্ট এখানে লিখুন...", key=f"q_ans_{q_idx}")
    st.sidebar.markdown("---")
    
    questions_data.append({
        "q_no": q_idx,
        "question": q_text,
        "marks": q_marks,
        "model_answer": q_ans
    })

# ট্যাব তৈরি
tab1, tab2 = st.tabs(["📤 খাতা মূল্যায়ন ও আপলোড", "📊 বার্ষিক ফলাফল ও ডাটাবেস"])

with tab1:
    st.subheader("ছাত্র-ছাত্রীদের উত্তরপত্রের ছবি আপলোড করুন")
    uploaded_files = st.file_uploader(
        "উত্তরপত্রগুলোর ছবি সিলেক্ট করুন (একাধিক ছবি একসাথে আপলোড করা যাবে)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files and st.button("🚀 খাতা মূল্যায়ন শুরু করুন"):
        progress_bar = st.progress(0)
        total_files = len(uploaded_files)
        success_count = 0

        conn = sqlite3.connect("annual_exam_results.db")
        cursor = conn.cursor()

        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            
            try:
                image = Image.open(uploaded_file)
                
                # প্রশ্নগুলো ফরম্যাট করা
                formatted_questions = ""
                total_full_marks = 0
                for q in questions_data:
                    total_full_marks += q['marks']
                    formatted_questions += f"\n- Question {q['q_no']}: {q['question']} (Marks: {q['marks']})\n  Model Answer: {q['model_answer']}\n"

                prompt = f"""
                You are a strict and fair senior examiner conducting an annual exam evaluation. Analyze the student's handwritten answer sheet from the image for all the following questions:

                {formatted_questions}

                Total Full Marks for this paper: {total_full_marks}

                Please evaluate carefully and provide your response strictly in the following format:
                ROLL_NUMBER: [Find student roll/ID from paper if written, else 'Unknown']
                STUDENT_NAME: [Find student name if written, else '{file_name}']
                TOTAL_OBTAINED_MARKS: [Sum of all numerical marks obtained across all questions, e.g., 18.5]
                DETAILED_FEEDBACK: [Provide question-wise breakdown of marks and short feedback for each question]
                """

                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=[image, prompt]
                )
                
                res_text = response.text
                
                # রেসপন্স পার্স করা
                roll, name, total_obtained, detailed_fb = "Unknown", file_name, 0.0, res_text
                
                for line in res_text.split('\n'):
                    if "ROLL_NUMBER:" in line:
                        roll = line.replace("ROLL_NUMBER:", "").strip()
                    elif "STUDENT_NAME:" in line:
                        name = line.replace("STUDENT_NAME:", "").strip()
                    elif "TOTAL_OBTAINED_MARKS:" in line:
                        import re
                        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                        if numbers:
                            total_obtained = float(numbers[0])

                # ডাটাবেসে সেভ করা
                cursor.execute("""
                    INSERT INTO results (exam_name, student_name, roll_number, total_obtained_marks, total_full_marks, detailed_evaluation)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (exam_name, name, roll, total_obtained, total_full_marks, detailed_fb))
                conn.commit()
                success_count += 1

            except Exception as e:
                st.error(f"ফাইল {file_name} মূল্যায়নে সমস্যা হয়েছে: {e}")

            progress_bar.progress((i + 1) / total_files)

        conn.close()
        st.success(f"✅ সফলভাবে {success_count} টি খাতা মূল্যায়ন করা হয়েছে!")

with tab2:
    st.subheader("📊 বার্ষিক পরীক্ষার সংরক্ষিত ফলাফল শিট")
    
    if st.button("🔄 ডাটা রিফ্রেশ করুন"):
        st.rerun()

    conn = sqlite3.connect("annual_exam_results.db")
    df_results = pd.read_sql_query("SELECT * FROM results", conn)
    conn.close()

    if not df_results.empty:
        st.dataframe(df_results, use_container_width=True)
        
        # সিএসভি ডাউনলোড
        csv = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 বার্ষিক পরীক্ষার ফাইনাল মার্কশিট ডাউনলোড করুন (CSV)",
            data=csv,
            file_name="annual_exam_final_results.csv",
            mime="text/csv",
        )
    else:
        st.info("এখনো কোনো বার্ষিক পরীক্ষার ফলাফল সংরক্ষিত নেই।")
