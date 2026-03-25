import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime

# --- 1. การตั้งค่าเบื้องต้น ---
LOG_FILE = "chat_logs.csv"
KNOWLEDGE_DIR = "knowledge_base"

# --- 2. ระบบจัดการ API และเลือก Model อัจฉริยะ ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ ไม่พบ API Key ในหน้า Secrets ของ Streamlit Cloud")
    st.stop()

@st.cache_resource
def get_working_model():
    """
    ฟังก์ชันตรวจสอบ Model ที่ใช้งานได้จริงในระบบ 
    เพื่อป้องกัน Error 404 จาก Library เวอร์ชันเก่า
    """
    try:
        # พยายามดึงรายชื่อ Model ที่ API ของคุณเข้าถึงได้
        models_in_system = [m.name for m in genai.list_models()]
        
        # ลำดับความสำคัญ: 1.5 Flash (โควต้าเยอะ) -> 1.0 Pro (ตัวสำรอง)
        priority_targets = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.0-pro'
        ]
        
        for target in priority_targets:
            if target in models_in_system:
                return genai.GenerativeModel(target), target
        
        # หากไม่พบในลิสต์เลย (Library อาจจะเก่า) ให้ลองเรียกชื่อสั้น
        return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash (attempt)'
        
    except Exception:
        # กรณีสุดท้ายถ้า Error หนัก ให้ใช้ชื่อพื้นฐานที่สุดที่ Lib ทุกรุ่นรู้จัก
        return genai.GenerativeModel('gemini-pro'), 'gemini-pro (legacy mode)'

# --- 3. ฟังก์ชันบันทึกข้อมูล (Log) ---
def save_log(question, answer):
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

# --- 4. ฟังก์ชันโหลดฐานข้อมูลความรู้ ---
@st.cache_data
def load_context():
    if not os.path.exists(KNOWLEDGE_DIR):
        return None
    try:
        files = [f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".txt")]
        if not files: return None
        
        full_text = ""
        for f_name in sorted(files):
            with open(os.path.join(KNOWLEDGE_DIR, f_name), 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    full_text += f"\n\n--- Source: {f_name} ---\n{content}\n"
        return full_text
    except Exception as e:
        st.error(f"Error loading knowledge: {e}")
        return None

# --- 5. การแสดงผลหน้าจอ (UI) ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬", layout="centered")

with st.sidebar:
    st.header("⚙️ สำหรับผู้ดูแล")
    if st.checkbox("ดูประวัติการแชท (Admin Only)"):
        pw = st.text_input("รหัสผ่าน", type="password")
        if pw == "admin123":
            if os.path.exists(LOG_FILE):
                df = pd.read_csv(LOG_FILE)
                st.dataframe(df.tail(10))
                st.download_button("📥 โหลด Log ทั้งหมด", df.to_csv(index=False).encode('utf-8-sig'), "logs.csv")
            else:
                st.info("ยังไม่มีประวัติ")

st.title("🔬 FE-SEM Assistant")
st.caption("ระบบตอบคำถามอัตโนมัติ (MIRA4) มหาวิทยาลัยขอนแก่น")
st.markdown("---")

# โหลดฐานข้อมูล
context = load_context()

# ส่วนการแชท
if prompt := st.chat_input("สอบถามเรื่องการจองเครื่อง, ค่าบริการ หรือการเตรียมตัวอย่าง..."):
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        if not context:
            st.error("❌ ไม่พบไฟล์ข้อมูลในโฟลเดอร์ knowledge_base")
        else:
            with st.spinner("กำลังประมวลผลคำตอบ..."):
                model, model_used = get_working_model()
                
                if model:
                    # แสดงชื่อรุ่นที่จับได้จริงเพื่อความโปร่งใส
                    st.caption(f"🤖 ระบบกำลังใช้รุ่น: {model_used}")
                    
                    system_instruction = f"""คุณคือ AI ผู้ช่วยห้อง Lab FE-SEM 
                    ตอบคำถามโดยใช้ข้อมูลที่ให้มานี้เท่านั้น:
                    {context}
                    
                    หากไม่มีในข้อมูล ให้ตอบว่า: 'ขออภัยครับ ข้อมูลส่วนนี้ไม่มีในฐานข้อมูลของผม กรุณาติดต่อคุณเอิ๊ก 0927829658'"""
                    
                    try:
                        response = model.generate_content([system_instruction, prompt])
                        answer = response.text
                        st.markdown(answer)
                        save_log(prompt, answer)
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ โควต้าชั่วคราวเต็ม (Rate Limit) กรุณารอ 1 นาทีแล้วลองใหม่ครับ")
                        elif "404" in str(e):
                            st.error("❌ ไม่พบ Model ในระบบ (404) กรุณากด Reboot App ในหน้า Streamlit Cloud")
                        else:
                            st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error("❌ ไม่สามารถเชื่อมต่อกับ AI ได้")
