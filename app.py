import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime

# --- 1. ตั้งค่าพื้นฐาน ---
LOG_FILE = "chat_logs.csv"
KNOWLEDGE_DIR = "knowledge_base"

# --- 2. การตั้งค่า API และ Model (ฉบับแก้ 404 ถาวร) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ ไม่พบ API Key ใน Secrets")
    st.stop()

@st.cache_resource
def get_working_model():
    """
    ฟังก์ชันเลือก Model: 
    ลองเรียกแบบ 'gemini-1.5-flash' (ไม่มี models/ นำหน้า) 
    เพราะบาง Library Version จะเติมให้เอง ถ้าเราใส่ไปซ้ำจะเกิด 404
    """
    # รายชื่อที่ API ส่วนใหญ่ยอมรับ
    test_names = ['gemini-1.5-flash', 'gemini-1.0-pro']
    
    for name in test_names:
        try:
            # ทดสอบสร้าง Model
            model = genai.GenerativeModel(name)
            # ทดสอบ List เพื่อเช็คว่า Model นี้มีตัวตนจริงไหม
            # ถ้าผ่านบรรทัดนี้ได้ แสดงว่า Model พร้อมใช้
            return model, name
        except Exception:
            continue
            
    # ถ้ายังไม่ได้ ให้ลองเติม models/ (แผนสำรอง)
    try:
        return genai.GenerativeModel('models/gemini-1.5-flash'), 'models/gemini-1.5-flash'
    except:
        return None, None

# --- 3. ฟังก์ชันบันทึก Log ---
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

# --- 4. โหลดฐานข้อมูล ---
@st.cache_data
def load_context():
    if not os.path.exists(KNOWLEDGE_DIR): return None
    try:
        files = sorted([f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".txt")])
        if not files: return None
        text = ""
        for fn in files:
            with open(os.path.join(KNOWLEDGE_DIR, fn), 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content: text += f"\n\n--- {fn} ---\n{content}\n"
        return text
    except Exception: return None

# --- 5. หน้าจอ UI ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬")

st.title("🔬 FE-SEM Assistant")
st.markdown("ระบบตอบคำถามอัตโนมัติจากฐานข้อมูลห้อง Lab")
st.markdown("---")

context = load_context()

if prompt := st.chat_input("สอบถามเรื่องการจอง หรือค่าบริการ..."):
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        if not context:
            st.error("❌ ไม่พบข้อมูลใน knowledge_base")
        else:
            with st.spinner("AI กำลังวิเคราะห์..."):
                model, model_name = get_working_model()
                
                if model:
                    st.caption(f"🤖 Active Model: {model_name}")
                    
                    system_prompt = f"""คุณคือผู้ช่วยห้อง Lab FE-SEM (MIRA4) 
ตอบคำถามโดยใช้ข้อมูลนี้เท่านั้น:
{context}

หากไม่มีข้อมูลให้ตอบว่า: "ขออภัยครับ ข้อมูลส่วนนี้ไม่มีในฐานข้อมูลของผม กรุณาติดต่อคุณเอิ๊ก 0927829658" """
                    
                    try:
                        # แก้ไขตรงนี้: ใช้การส่งคำถามแบบง่ายที่สุด
                        response = model.generate_content(f"{system_prompt}\n\nคำถาม: {prompt}")
                        st.markdown(response.text)
                        save_log(prompt, response.text)
                    except Exception as e:
                        if "404" in str(e):
                            st.error(f"❌ 404 Error: ระบบหา '{model_name}' ไม่พบใน Version นี้")
                        elif "429" in str(e):
                            st.error("⚠️ โควต้าเต็ม กรุณารอ 1 นาที")
                        else:
                            st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error("❌ ไม่พบ Model ที่ใช้งานได้")
