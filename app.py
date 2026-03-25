import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime

# --- 1. ตั้งค่าตัวแปร Global (ต้องอยู่ด้านบนสุด) ---
LOG_FILE = "chat_logs.csv"
KNOWLEDGE_DIR = "knowledge_base"

# --- 2. การตั้งค่า API และการเลือก Model อัตโนมัติ ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ ไม่พบ API Key ใน Secrets")
    st.stop()

def get_best_available_model():
    """ฟังก์ชันเลือก Model ที่ดีที่สุดและใช้งานได้จริงอัตโนมัติ"""
    try:
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        priority_list = [
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'models/gemini-1.0-pro',
            'models/gemini-pro'
        ]
        for model_name in priority_list:
            if model_name in available_models:
                return genai.GenerativeModel(model_name)
        if available_models:
            return genai.GenerativeModel(available_models[0])
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถดึงรายชื่อ Model ได้: {e}")
    return None

# --- 3. ฟังก์ชันบันทึก Log ลงไฟล์ CSV (แทนที่ Google Sheets) ---
def save_log_to_csv(question, answer):
    try:
        new_row = pd.DataFrame({
            "timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "question": [str(question)],
            "answer": [str(answer)]
        })
        # ถ้ายังไม่มีไฟล์ให้สร้างใหม่พร้อมหัวตาราง ถ้ามีแล้วให้บันทึกต่อท้าย
        if not os.path.isfile(LOG_FILE):
            new_row.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
        else:
            new_row.to_csv(LOG_FILE, mode='a', index=False, header=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"⚠️ บันทึก Log ไม่สำเร็จ: {e}")

# --- 4. ฟังก์ชันโหลดความรู้ ---
@st.cache_data
def load_knowledge_base():
    path = KNOWLEDGE_DIR
    combined_content = ""
    if not os.path.exists(path): return None
    files = sorted([f for f in os.listdir(path) if f.endswith(".txt")])
    for filename in files:
        with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
            combined_content += f"\n\n--- Source: {filename} ---\n" + f.read()
    return combined_content

knowledge_context = load_knowledge_base()

# --- 5. หน้าจอ UI และ Sidebar ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬")

# ส่วนของ Sidebar สำหรับผู้ดูแลระบบ
with st.sidebar:
    st.header("⚙️ สำหรับผู้ดูแลระบบ")
    if st.checkbox("เปิดโหมดดู Log"):
        pwd = st.text_input("รหัสผ่าน", type="password")
        if pwd == "admin123":
            if os.path.exists(LOG_FILE):
                df_log = pd.read_csv(LOG_FILE)
                st.write("รายการคำถามล่าสุด:")
                st.dataframe(df_log.tail(10))
                
                # ปุ่มดาวน์โหลดไฟล์ Log
                csv_data = df_log.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 ดาวน์โหลด Log (CSV)",
                    data=csv_data,
                    file_name=f"logs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ยังไม่มีข้อมูลการบันทึก")

st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.caption("ระบบตอบคำถามอัตโนมัติจากฐานข้อมูลห้องปฏิบัติการ")
st.markdown("---")

# ส่วนรับคำถามจากผู้ใช้
if prompt := st.chat_input("สอบถามเรื่องการจองเครื่อง หรือ การเตรียมตัวอย่าง..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if knowledge_context:
            with st.spinner("AI กำลังวิเคราะห์คำตอบ..."):
                model = get_best_available_model()
                
                if model:
                    system_prompt = f"""
                    คุณคือ AI ผู้ช่วยประจำห้อง Lab FE-SEM (Tescan MIRA4)
                    ทำหน้าที่ตอบคำถามลูกค้าโดยใช้ข้อมูลอ้างอิงที่ให้มาเท่านั้น
                    หากไม่มีข้อมูลในฐานข้อมูล ให้บอกว่า "ขออภัยครับ ข้อมูลส่วนนี้ไม่มีในฐานข้อมูลของผม กรุณาติดต่อคุณเอิ๊ก 0927829658"
                    
                    ข้อมูลอ้างอิง:
                    {knowledge_context}
                    """
                    
                    try:
                        response = model.generate_content([system_prompt, prompt])
                        answer = response.text
                        st.markdown(answer)
                        
                        # บันทึก Log ลงไฟล์ CSV
                        save_log_to_csv(prompt, answer)
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการสร้างคำตอบ: {e}")
                else:
                    st.error("❌ ไม่พบ Model ที่พร้อมใช้งาน")
        else:
            st.error("❌ ไม่พบข้อมูลใน knowledge_base")
