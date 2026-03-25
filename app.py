import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. ตั้งค่า API Key จาก Secrets (ดึงมาจากหน้าเว็บ Streamlit)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 2. เชื่อมต่อ Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def save_log_to_gsheets(question, answer):
    try:
        # อ่านข้อมูลปัจจุบันจาก Sheet (ttl=0 คือไม่ใช้แคชเพื่อให้ได้ข้อมูลล่าสุด)
        existing_data = conn.read(worksheet="Sheet1", ttl=0)
        existing_data = existing_data.dropna(how="all")
        
        new_row = pd.DataFrame({
            "timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "question": [question],
            "answer": [answer]
        })
        
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        st.error(f"⚠️ บันทึก Log ไม่สำเร็จ: {e}")

# 3. ฟังก์ชันโหลดความรู้จากไฟล์ .txt
@st.cache_data
def load_knowledge_base():
    path = "knowledge_base"
    combined_content = ""
    if not os.path.exists(path): return None
    files = sorted([f for f in os.listdir(path) if f.endswith(".txt")])
    for filename in files:
        with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
            combined_content += f"\n\n--- Source: {filename} ---\n" + f.read()
    return combined_content

knowledge_context = load_knowledge_base()

# 4. หน้าจอ UI
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬")
st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.caption("ระบบตอบคำถามอัตโนมัติ (RAG System)")
st.markdown("---")

if prompt := st.chat_input("สอบถามเรื่องการจองเครื่อง หรือ การเตรียมตัวอย่าง..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if knowledge_context:
            with st.spinner("AI กำลังวิเคราะห์คำตอบ..."):
                model = genai.GenerativeModel('models/gemini-1.5-flash')
                system_prompt = f"คุณคือ AI ผู้ช่วยห้อง Lab FE-SEM ตอบคำถามโดยใช้ข้อมูลนี้เท่านั้น: {knowledge_context}\nหากไม่มีข้อมูลให้บอกให้ติดต่อคุณเอิ๊ก 0927829658"
                
                try:
                    response = model.generate_content([system_prompt, prompt])
                    answer = response.text
                    st.markdown(answer)
                    
                    # บันทึกข้อมูลลง Google Sheets
                    save_log_to_gsheets(prompt, answer)
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")
