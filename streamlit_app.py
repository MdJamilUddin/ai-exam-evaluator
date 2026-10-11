import os
import sqlite3
import streamlit as st
import pandas as pd
from google import genai
from PIL import Image

# পেজ কনফিগারেশন
st.set_page_config(
    page_title="বড় পরিসর - AI খাতা মূল্যায়ন সিস্টেম",
    page_icon="🏫",
    layout="wide"
)

# ১. ডাটাবেস ইনিশিয়ালাইজেশন (SQLite)
def init_db():
    conn = sqlite3.connect("exam_results.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT,
            student_name TEXT,
            roll_number TEXT,
            marks_obtained REAL,
            total_marks REAL,
            feedback TEXT,
            extracted_text TEXT
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

st.title("🏫 বড় পরিসরে AI খাতা মূল্যায়ন ও ডাটাবেস ম্যানেজমেন্ট সিস্টেম")
st.markdown("শিক্ষাপ্রতিষ্ঠান বা বড় পরীক্ষার জন্য স্বয়ংক্রিয় মূল্যায়ন ও রেকর্ড সংরক্ষণ ড্যাশবোর্ড।")

# সাইডবার: পরীক্ষার তথ্য
st.sidebar.header("📝 পরীক্ষার কনফিগারেশন")
exam_title = st.sidebar.text_input("পরীক্ষার নাম / বিষয়", "বার্ষিক পরীক্ষা - পদার্থবিজ্ঞান")
question_text = st.sidebar.text_area("প্রশ্ন", "নিউটন গতির ৩য় সূত্রটি উদাহরণসহ ব্যাখ্যা কর।")
total_marks = st.sidebar.number_input("পূর্ণমান (Total Marks)", min_value=1, max_value=100, value=5)
model_answer = st.sidebar.text_area("আদর্শ উত্তর (Model Answer)", 
    "প্রত্যেক ক্রিয়ারই একটি সমান ও বিপরীত প্রতিক্রিয়া আছে। যেমন: নৌকার মাঝি বৈঠা দিয়ে পানি পেছনের দিকে ঠেললে নৌকা সামনে এগিয়ে যায়।")

# ট্যাব তৈরি (মূল্যায়ন বনাম সংরক্ষিত ফলাফল দেখার জন্য)
tab1, tab2 = st.tabs(["📤 খাতা মূল্যায়ন ও আপলোড", "📊 সংরক্ষিত ফলাফল ও ডাটাবেস"])

with tab1:
    st.subheader("ছাত্র-ছাত্রীদের উত্তরপত্র আপলোড করুন")
    uploaded_files = st.file_uploader(
        "একাধিক উত্তরপত্রের ছবি সিলেক্ট করুন (JPG, PNG)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files and st.button("🚀 খাতা মূল্যায়ন এবং ডাটাবেসে সংরক্ষণ শুরু করুন"):
        progress_bar = st.progress(0)
        total_files = len(uploaded_files)
        success_count = 0

        conn = sqlite3.connect("exam_results.db")
        cursor = conn.cursor()

        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            
            try:
                image = Image.open(uploaded_file)
                
                # উন্নত প্রম্পট যাতে AI নির্ভুল নম্বর ও রোল শনাক্ত করতে পারে
                prompt = f"""
                You are a strict and fair examiner. Analyze the student's handwritten answer sheet from the image.
                
                - **Question:** {question_text}
                - **Total Marks:** {total_marks}
                - **Model Answer:** {model_answer}

                Please evaluate and extract the following details strictly in this format (separated by '---'):
                ROLL_NUMBER: [Find the student roll/ID from the paper if written, otherwise write 'Unknown']
                STUDENT_NAME: [Find the student name if written, otherwise write '{file_name}']
                EXTRACTED_TEXT: [Short summary of what the student wrote]
                FEEDBACK: [Constructive feedback explaining mistakes or strong points]
                MARKS: [Only the numerical marks obtained out of {total_marks}, e.g., 4.5]
                """

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[image, prompt]
                )
                
                res_text = response.text
                
                # রেসপন্স পার্স করার সাধারণ লজিক
                roll, name, ext_text, feedback, marks = "Unknown", file_name, "", "", 0.0
                
                for line in res_text.split('\n'):
                    if "ROLL_NUMBER:" in line:
                        roll = line.replace("ROLL_NUMBER:", "").strip()
                    elif "STUDENT_NAME:" in line:
                        name = line.replace("STUDENT_NAME:", "").strip()
                    elif "EXTRACTED_TEXT:" in line:
                        ext_text = line.replace("EXTRACTED_TEXT:", "").strip()
                    elif "FEEDBACK:" in line:
                        feedback = line.replace("FEEDBACK:", "").strip()
                    elif "MARKS:" in line:
                        import re
                        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                        if numbers:
                            marks = float(numbers[0])

                # ডাটাবেসে সেভ করা
                cursor.execute("""
                    INSERT INTO results (exam_name, student_name, roll_number, marks_obtained, total_marks, feedback, extracted_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (exam_title, name, roll, marks, total_marks, feedback, ext_text))
                conn.commit()
                success_count += 1

            except Exception as e:
                st.error(f"ফাইল {file_name} মূল্যায়নে সমস্যা হয়েছে: {e}")

            progress_bar.progress((i + 1) / total_files)

        conn.close()
        st.success(f"✅ সফলভাবে {success_count} টি খাতা মূল্যায়ন করে ডাটাবেসে সংরক্ষণ করা হয়েছে!")

with tab2:
    st.subheader("📂 পূর্বের সংরক্ষিত সকল পরীক্ষার ফলাফল")
    
    if st.button("🔄 ডাটা রিফ্রেশ করুন"):
        st.rerun()

    conn = sqlite3.connect("exam_results.db")
    df_results = pd.read_sql_query("SELECT * FROM results", conn)
    conn.close()

    if not df_results.empty:
        st.dataframe(df_results, use_container_width=True)
        
        # এক্সেল বা সিএসভি ডাউনলোড
        csv = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 সম্পূর্ণ ডাটাবেস এক্সেল/সিএসভি (CSV) হিসেবে ডাউনলোড করুন",
            data=csv,
            file_name="all_exam_results_database.csv",
            mime="text/csv",
        )
    else:
        st.info("ডাটাবেসে এখনো কোনো ফলাফল সংরক্ষিত নেই। প্রথমে কিছু খাতা মূল্যায়ন করুন।")
