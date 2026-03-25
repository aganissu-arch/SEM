import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. การตั้งค่า API และการเลือก Model อัตโนมัติ ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def get_best_available_model():
    """ฟังก์ชันเลือก Model ที่ดีที่สุดและใช้งานได้จริงอัตโนมัติ"""
    try:
        # ดึงรายชื่อโมเดลทั้งหมดที่ Key นี้ใช้ได้
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        # รายชื่อลำดับความสำคัญ (ถ้าเจอตัวไหนก่อน ให้ใช้ตัวนั้น)
        priority_list = [
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'models/gemini-1.0-pro',
            'models/gemini-pro'
        ]
        
        for model_name in priority_list:
            if model_name in available_models:
                return genai.GenerativeModel(model_name)
        
        # ถ้าไม่เจอตัวในลิสต์เลย ให้เอาตัวแรกที่ระบบอนุญาต
        if available_models:
            return genai.GenerativeModel(available_models[0])
            
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถดึงรายชื่อ Model ได้: {e}")
    return None

# --- 2. เชื่อมต่อ Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_log_to_gsheets(question, answer):
    try:
        # 1. อ่านข้อมูลโดยไม่ระบุชื่อ Worksheet (เพื่อให้ระบบเลือกหน้าแรกอัตโนมัติ)
        # วิธีนี้จะช่วยลดปัญหา 404 หากชื่อ Sheet1 มีการเว้นวรรคหรือพิมพ์ผิด
        df = conn.read(ttl=0) 
        
        # 2. จัดการข้อมูลเก่า (ลบแถวที่ว่างเปล่า)
        if df is not None:
            df = df.dropna(how="all")
        
        # 3. เตรียมข้อมูลแถวใหม่
        new_row = pd.DataFrame({
            "timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "question": [str(question)],
            "answer": [str(answer)]
        })
        
        # 4. รวมข้อมูลเข้าด้วยกัน
        # กรณี Sheet ว่างเปล่า (ไม่มี Header) ให้ใช้ข้อมูลใหม่เป็นตัวตั้งต้น
        if df is None or df.empty:
            updated_df = new_row
        else:
            # พยายามทำให้หัวข้อคอลัมน์ตรงกันก่อนรวม
            new_row.columns = df.columns[:3] if len(df.columns) >= 3 else ["timestamp", "question", "answer"]
            updated_df = pd.concat([df, new_row], ignore_index=True)
        
        # 5. อัปเดตกลับไปยัง Google Sheets
        # ระบุชื่อ worksheet ให้ชัดเจน (ตรวจสอบในไฟล์จริงว่าชื่อ Sheet1 หรือไม่)
        conn.update(worksheet="Sheet1", data=updated_df)
        
    except Exception as e:
        st.error(f"⚠️ บันทึก Log ไม่สำเร็จ: {e}")

# --- 3. ฟังก์ชันโหลดความรู้ ---
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

# --- 4. หน้าจอ UI ---
st.set_page_config(page_title="FE-SEM Assistant", page_icon="🔬")
st.title("🔬 FE-SEM (Tescan MIRA4) Assistant")
st.caption("ระบบตอบคำถามอัตโนมัติจากฐานข้อมูลห้องปฏิบัติการ")
st.markdown("---")

if prompt := st.chat_input("สอบถามเรื่องการจองเครื่อง หรือ การเตรียมตัวอย่าง..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if knowledge_context:
            with st.spinner("AI กำลังวิเคราะห์คำตอบ..."):
                # เรียกใช้ฟังก์ชันเลือก Model อัตโนมัติ
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
                        
                        # บันทึก Log ลง Google Sheets
                        save_log_to_gsheets(prompt, answer)
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการสร้างคำตอบ: {e}")
                else:
                    st.error("❌ ไม่พบ Model ที่พร้อมใช้งานใน API Key นี้")
        else:
            st.error("❌ ไม่พบข้อมูลใน knowledge_base")
