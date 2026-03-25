import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime

# --- 1. ตั้งค่าตัวแปร Global ---
LOG_FILE = "chat_logs.csv"
KNOWLEDGE_DIR = "knowledge_base"

# --- 2. การตั้งค่า API และระบบเลือก Model อัตโนมัติ ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ ไม่พบ API Key ในหน้า Secrets ของ Streamlit Cloud")
    st.stop()

@st.cache_resource
def get_best_model():
    """
    ฟังก์ชันอัจฉริยะ: ตรวจสอบว่า API ของคุณมองเห็น Model รุ่นไหนบ้าง 
    และเลือกตัวที่ดีที่สุด (1.5 Flash) เพื่อเลี่ยง Error 404
    """
    try:
        # ดึงรายชื่อ Model ทั้งหมดที่ Key นี้เข้าถึงได้
        available_models = [m.name for m in genai.list_models()]
        
        # ลำดับความสำคัญ (เน้น 1.5 Flash เพื่อ Quota 1,500 ครั้ง/วัน)
        priority_list = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.0-pro'  # ตัวสำรองสุดท้าย
        ]
        
        for target in priority_list:
            if target in available_models:
                return genai.GenerativeModel(target), target
        
        # ถ้าไม่เจอใน List เลย ให้ลองเรียกแบบ Default
        return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash (default)'
        
    except Exception as e:
        # กรณี List ไม่ได้ (เช่น Library เก่า) ให้ลองเรียกตรงๆ
        return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash (manual)'

# --- 3. ฟังก์ชันบันทึก Log ลงไฟล์ CSV ---
def save_log_to_csv(question, answer):
    try:
        new_row = pd.DataFrame({
            "timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "question": [str(question)],
            "answer": [str(answer)]
        })
        if not os.path.isfile(LOG_FILE):
            new_row.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
        else:
            new_row.to_csv(LOG_FILE, mode='a', index=False, header=False, encoding='utf-8-sig')
    except Exception:
        pass

# --- 4. ฟังก์ชันโหลดความรู้จากโฟลเดอร์ ---
@st.cache_data
def load_knowledge_base():
    path = KNOWLEDGE_DIR
    combined_content = ""
    if not os.path.exists(path):
        return None
    try:
        files = sorted([f for f in os.listdir(path) if f.endswith(".txt")])
        if not files:
            return None
        for filename in files:
            with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    combined_content += f"\n\n--- Source: {filename} ---\n{content}\n"
        return combined_content
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดฐานข้อมูล: {e}")
        return None

# --- 5. หน้าจอ UI หลัก ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬", layout="wide")

# ส่วนของ Sidebar สำหรับ Admin
with st.sidebar:
    st.header("⚙️ Admin Panel")
    if st.checkbox("ดูประวัติการถาม (Log)"):
        pwd = st.text_input("รหัสผ่าน", type="password")
        if pwd == "admin123":
            if os.path.exists(LOG_FILE):
                df_log = pd.read_csv(LOG_FILE)
                st.dataframe(df_log.tail(10), use_container_width=True)
                csv_data = df_log.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Download Log CSV", csv_data, "chat_logs.csv", "text/csv")
            else:
                st.info("ยังไม่มีข้อมูลบันทึก")

st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.markdown("สวัสดีครับ! ผมคือ AI ผู้ช่วยประจำห้อง Lab FE-SEM มข. สอบถามข้อมูลได้เลยครับ")
st.markdown("---")

# โหลดฐานข้อมูลความรู้
knowledge_context = load_knowledge_base()

# ส่วนรับคำถาม
if prompt := st.chat_input("พิมพ์คำถามของคุณที่นี่... (เช่น ค่าบริการเท่าไหร่, จองเครื่องยังไง)"):
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        if not knowledge_context:
            st.error("❌ ไม่พบข้อมูลในโฟลเดอร์ knowledge_base กรุณาตรวจสอบไฟล์ .txt")
        else:
            with st.spinner("กำลังค้นหาคำตอบจากฐานข้อมูล..."):
                # ดึง Model ที่ดีที่สุดมาใช้งาน
                model, model_name = get_best_model()
                
                if model:
                    # แสดงชื่อรุ่นที่ระบบเลือกใช้จริง (ช่วยในการ Debug)
                    st.caption(f"🤖 Active Model: {model_name}")
                    
                    system_prompt = f"""คุณคือ AI ผู้ช่วยห้อง Lab FE-SEM (Tescan MIRA4) 
ตอบคำถามโดยใช้ข้อมูลอ้างอิงด้านล่างนี้เท่านั้น 
หากไม่มีข้อมูลในฐานข้อมูล ให้ตอบว่า "ขออภัยครับ ข้อมูลส่วนนี้ไม่มีในฐานข้อมูลของผม กรุณาติดต่อคุณเอิ๊ก 0927829658"

ข้อมูลอ้างอิง:
{knowledge_context}
"""
                    try:
                        response = model.generate_content([system_prompt, prompt])
                        answer = response.text
                        st.markdown(answer)
                        save_log_to_csv(prompt, answer)
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ โควต้าการถามชั่วคราวเต็ม (Rate Limit) กรุณารอ 1 นาทีแล้วลองใหม่ครับ")
                        elif "404" in str(e):
                            st.error(f"❌ ระบบไม่พบรุ่น {model_name} (404) กรุณาตรวจสอบ Library Version")
                        else:
                            st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error("❌ ไม่สามารถเชื่อมต่อกับ Gemini API ได้")
