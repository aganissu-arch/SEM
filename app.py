import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. การตั้งค่า API และ Path ---
KNOWLEDGE_DIR = "knowledge_base"

# ดึง API Key จาก Secrets
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    # สำหรับรันทดสอบในเครื่อง (ใส่ Key ของคุณตรงนี้)
    genai.configure(api_key="AIzaSyD4r6Ek3pJqi_CGtNLL89-OB0I30UQzuxA")

# --- 2. เชื่อมต่อ Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_log_to_gsheets(question, answer):
    try:
        # อ่านข้อมูลเดิม (ตั้ง ttl=0 เพื่อให้อัปเดตสดใหม่)
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
        st.error(f"Error saving to GSheets: {e}")

# --- 3. ฟังก์ชัน AI ---
def get_chatbot_model():
    try:
        # เลือกใช้ gemini-1.5-flash เป็นตัวหลัก
        return genai.GenerativeModel('gemini-1.5-flash')
    except:
        return None

@st.cache_data
def load_knowledge_base():
    combined_content = ""
    if not os.path.exists(KNOWLEDGE_DIR): return None
    files = sorted([f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".txt")])
    for filename in files:
        with open(os.path.join(KNOWLEDGE_DIR, filename), 'r', encoding='utf-8') as f:
            combined_content += f"\n\n--- Source: {filename} ---\n" + f.read()
    return combined_content

model = get_chatbot_model()
knowledge_context = load_knowledge_base()

# --- 4. หน้าจอ UI ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬")
st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.markdown("---")

if prompt := st.chat_input("สอบถามเรื่องการเตรียมตัวอย่าง หรือ ค่าบริการ..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if model and knowledge_context:
            with st.spinner("กำลังหาคำตอบ..."):
                system_prompt = f"""
                คุณคือ AI ผู้ช่วยประจำห้อง Lab FE-SEM ตอบคำถามโดยใช้ข้อมูลนี้เท่านั้น:
                {knowledge_context}
                กฎ: หากไม่มีคำตอบให้แจ้งเบอร์ติดต่อคุณเอิ๊ก 0927829658
                """
                response = model.generate_content([system_prompt, prompt])
                answer = response.text
                st.markdown(answer)
                
                # บันทึก Log ลง GSheets ทันที
                save_log_to_gsheets(prompt, answer)