import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime

# --- 1. ตั้งค่าตัวแปร Global ---
LOG_FILE = "chat_logs.csv"
KNOWLEDGE_DIR = "knowledge_base"

# --- 2. การตั้งค่า API และ Model ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ ไม่พบ API Key ใน Secrets")
    st.stop()

# แก้ไข: ใส่ models/ นำหน้าชื่อรุ่นเพื่อป้องกัน Error 404
# และใช้ gemini-1.5-flash เพื่อให้ได้ Quota ฟรี 1,500 ครั้ง/วัน
ACTIVE_MODEL_NAME = 'models/gemini-1.5-flash' 

def get_model():
    """ดึง Model รุ่นที่ระบุไว้มาใช้งานโดยตรง"""
    try:
        # ระบุชื่อรุ่นแบบเต็มผ่านพารามิเตอร์ model_name
        return genai.GenerativeModel(model_name=ACTIVE_MODEL_NAME)
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถโหลด Model {ACTIVE_MODEL_NAME} ได้: {e}")
        return None

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

# --- 4. ฟังก์ชันโหลดความรู้ ---
@st.cache_data
def load_knowledge_base():
    path = KNOWLEDGE_DIR
    combined_content = ""
    if not os.path.exists(path): 
        return None
    
    # อ่านไฟล์ .txt ทั้งหมดในโฟลเดอร์มาต่อกัน
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

knowledge_context = load_knowledge_base()

# --- 5. หน้าจอ UI และ Sidebar ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬")

with st.sidebar:
    st.header("⚙️ สำหรับผู้ดูแลระบบ")
    if st.checkbox("เปิดโหมดดู Log"):
        pwd = st.text_input("รหัสผ่าน", type="password")
        if pwd == "admin123":
            if os.path.exists(LOG_FILE):
                df_log = pd.read_csv(LOG_FILE)
                st.write("รายการคำถามล่าสุด:")
                st.dataframe(df_log.tail(10))
                
                csv_data = df_log.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 ดาวน์โหลด Log (CSV)", 
                    data=csv_data, 
                    file_name=f"logs_{datetime.now().strftime('%Y%m%d')}.csv", 
                    mime="text/csv"
                )
            else:
                st.info("ยังไม่มีข้อมูลบันทึก")

st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.caption("ระบบตอบคำถามอัตโนมัติจากฐานข้อมูลห้องปฏิบัติการ")
st.markdown("---")

# ส่วนรับคำถามจากผู้ใช้
if prompt := st.chat_input("สอบถามเรื่องการจองเครื่อง หรือ การเตรียมตัวอย่าง..."):
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        if knowledge_context:
            with st.spinner("AI กำลังวิเคราะห์คำตอบ..."):
                model = get_model()
                
                if model:
                    # แสดงชื่อรุ่นที่ใช้งานจริงเพื่อให้ตรวจสอบได้ง่าย
                    st.caption(f"🤖 กำลังใช้งานรุ่น: {ACTIVE_MODEL_NAME}")
                    
                    system_prompt = f"""คุณคือผู้ช่วยห้อง Lab FE-SEM (Tescan MIRA4) 
ทำหน้าที่ตอบคำถามลูกค้าโดยใช้ข้อมูลอ้างอิงที่ให้มาเท่านั้น
หากไม่มีข้อมูลในฐานข้อมูล ให้บอกว่า "ขออภัยครับ ข้อมูลส่วนนี้ไม่มีในฐานข้อมูลของผม กรุณาติดต่อคุณเอิ๊ก 0927829658"

ข้อมูลอ้างอิง:
{knowledge_context}
"""
                    
                    try:
                        # เรียกใช้การสร้างคำตอบ
                        response = model.generate_content([system_prompt, prompt])
                        answer = response.text
                        
                        st.markdown(answer)
                        save_log_to_csv(prompt, answer)
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg:
                            st.error("⚠️ โควต้าชั่วคราวเต็ม (Rate Limit) กรุณารอ 1 นาทีแล้วลองใหม่ครับ")
                        elif "404" in error_msg:
                            st.error("❌ ไม่พบ Model ในระบบ (404) กรุณาตรวจสอบการระบุชื่อรุ่นในโค้ด")
                        else:
                            st.error(f"เกิดข้อผิดพลาดในการสร้างคำตอบ: {e}")
                else:
                    st.error("❌ ไม่พบ Model ที่พร้อมใช้งาน")
        else:
            st.error("❌ ไม่พบข้อมูลในโฟลเดอร์ knowledge_base หรือไฟล์ว่างเปล่า")
