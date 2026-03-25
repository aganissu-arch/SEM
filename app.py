import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime

# --- 1. ตั้งค่าตัวแปร Global ---
LOG_FILE = "chat_logs.csv"
KNOWLEDGE_DIR = "knowledge_base"

# --- 2. การตั้งค่า API ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ ไม่พบ API Key ใน Secrets")
    st.stop()

def get_best_available_model():
    """ฟังก์ชันเลือก Model โดยเน้น 1.5 Flash เพื่อประหยัด Quota"""
    try:
        # รายชื่อ Model ที่เราต้องการใช้ (เรียงลำดับความสำคัญ)
        # เราตัดรุ่น 2.5 ออกเพื่อป้องกันการดึงโควต้าที่จำกัดเกินไปมาใช้
        priority_list = [
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'models/gemini-1.0-pro'
        ]
        
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        for model_name in priority_list:
            if model_name in available_models:
                return genai.GenerativeModel(model_name)
        
        # ถ้าไม่เจอตัวที่กำหนด ให้เลือกตัวแรกที่ใช้งานได้
        if available_models:
            return genai.GenerativeModel(available_models[0])
            
    except Exception as e:
        # หากเกิด Error 429 ระหว่างลิสต์รายชื่อ ให้ลองเรียกตรงๆ
        return genai.GenerativeModel('models/gemini-1.5-flash')
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
    except Exception as e:
        pass # ไม่แสดง Error ให้ผู้ใช้ตกใจหากบันทึก Log ไม่สำเร็จ

# --- 4. ฟังก์ชันโหลดความรู้ ---
@st.cache_data
def load_knowledge_base():
    path = KNOWLEDGE_DIR
    combined_content = ""
    if not os.path.exists(path): return None
    
    # อ่านไฟล์ทั้งหมดและรวมเป็นก้อนเดียว
    files = sorted([f for f in os.listdir(path) if f.endswith(".txt")])
    if not files: return None
    
    for filename in files:
        with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                combined_content += f"\n{content}\n"
    return combined_content

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
                st.download_button("📥 ดาวน์โหลด Log (CSV)", csv_data, f"logs_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            else:
                st.info("ยังไม่มีข้อมูลบันทึก")

st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.caption("ระบบตอบคำถามอัตโนมัติจากฐานข้อมูลห้องปฏิบัติการ")
st.markdown("---")

if prompt := st.chat_input("สอบถามเรื่องการจองเครื่อง หรือ การเตรียมตัวอย่าง..."):
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        if knowledge_context:
            with st.spinner("AI กำลังวิเคราะห์คำตอบ..."):
                model = get_best_available_model()
                
                if model:
                    st.caption(f"🤖 กำลังใช้งานรุ่น: {model.model_name}")
                    # ปรับ Prompt ให้กระชับเพื่อประหยัด Token
                    system_prompt = f"""คุณคือผู้ช่วยห้อง Lab FE-SEM (Tescan MIRA4) 
ตอบคำถามโดยใช้ข้อมูลนี้เท่านั้น:
{knowledge_context}

หากไม่มีในข้อมูล ให้บอกว่า: "ขออภัยครับ ข้อมูลส่วนนี้ไม่มีในฐานข้อมูลของผม กรุณาติดต่อคุณเอิ๊ก 0927829658" """
                    
                    try:
                        # กำหนดความปลอดภัยและพารามิเตอร์พื้นฐาน
                        response = model.generate_content([system_prompt, prompt])
                        answer = response.text
                        st.markdown(answer)
                        save_log_to_csv(prompt, answer)
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ ขออภัยครับ โควต้าการถามชั่วคราวเต็มแล้ว (Rate Limit) กรุณารอ 1 นาทีแล้วลองใหม่ครับ")
                        else:
                            st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error("❌ ไม่พบ Model ที่พร้อมใช้งาน")
        else:
            st.error("❌ ไม่พบข้อมูลใน knowledge_base (กรุณาอัปโหลดไฟล์ .txt)")
