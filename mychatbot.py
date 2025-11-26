# mychatbot.py — FINAL COLLEGE PROJECT VERSION (Everything included!)
import base64
import json
import random
from datetime import datetime
import os
import streamlit as st
from groq import Groq

# === API & Config ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (st.secrets.get("GROQ_API_KEY") if hasattr(st, "secrets") else None)
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
GROQ_MODEL = "llama-3.1-8b-instant"

BACKGROUND_IMAGE_PATH = "r1.avif"
HISTORY_FILE = "chat_history.json"
COMMENTS_FILE = "comments.json"
APPOINTMENTS_FILE = "appointments.json"  # ← NEW: Saves appointments

SYSTEM_PROMPT = "You are a confidential, non-judgmental Mental Health Support Chatbot. Respond with empathy and care."

TOPICS = [
    "Depression","Anxiety","Feeling Isolated?","Family Issues","Boundaries",
    "Late night sleep problems","How to overcome anxiety?","Having arguments in family daily",
    "How to overcome late night sleep?","Recovering from panic attack?"
]

# === DOCTORS ===
DOCTORS = [
    {"name": "Dr. Priya Sharma", "specialty": "Anxiety & Stress Management", "location": "ballari", "phone": "+91 98765 43210", "image": "https://i.ibb.co/3chGS5k/doctor1.png"},
    {"name": "Dr. Rahul Verma", "specialty": "Depression & Mood Disorders", "location": "ballari", "phone": "+91 87654 32109", "image": "https://i.ibb.co/Zcp99sM/doctor2.png"},
    {"name": "Dr. Ananya Reddy", "specialty": "Sleep Issues & Trauma", "location": "ballari", "phone": "+91 76543 21098", "image": "https://i.ibb.co/7vbL8jr/doctor3.png"}
]

# === YOUTUBE RESOURCES ===
YOUTUBE_RESOURCES = [
    ("10-Minute Guided Breathing for Anxiety", "Calm your mind instantly", "https://www.youtube.com/watch?v=O-6f5wQXSu8"),
    ("How to Stop Overthinking", "Break the rumination cycle", "https://www.youtube.com/watch?v=1B8dZas2qg8"),
    ("Guided Sleep Meditation", "Fall asleep peacefully", "https://www.youtube.com/watch?v=inpok4MKVLM"),
    ("Understanding Depression", "Clear & compassionate explanation", "https://www.youtube.com/watch?v=z-IR48Mb3W0"),
    ("Box Breathing Technique", "Reduce stress in 2 minutes", "https://www.youtube.com/watch?v=FJJazKtH_9I")
]

# === BACKGROUND ===
def load_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""
BG_BASE64 = load_image_base64(BACKGROUND_IMAGE_PATH)

def apply_soft_frosted_ui(bg_base64):
    css = f"""
    <style>
    .stApp {{
        background: linear-gradient(rgba(6,10,14,0.45), rgba(6,10,14,0.45)),
                    url("data:image/avif;base64,{bg_base64}") no-repeat center center fixed;
        background-size: cover;
    }}
    .block-container {{
        background: rgba(10,12,14,0.38);
        backdrop-filter: blur(8px) saturate(120%);
        -webkit-backdrop-filter: blur(8px) saturate(120%);
        border-radius: 14px;
        padding: 20px 28px;
        border: 1px solid rgba(255,255,255,0.04);
        max-width: 1000px;
        margin: 0 auto;
    }}
    .glass-card {{
        background: linear-gradient(rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        border-radius: 14px;
        padding: 20px;
        margin: 16px 0;
        border: 1px solid rgba(255,255,255,0.03);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        backdrop-filter: blur(4px);
    }}
    .card-title {{ font-size: 20px; font-weight: 700; color: #f0f8ff; margin-bottom: 8px; }}
    .card-sub {{ color: #c8d6e5; font-size: 15px; line-height: 1.5; }}
    .stButton>button {{
        background: linear-gradient(135deg, #10a37f, #0d8c6b) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 10px 20px !important;
        border: none !important;
        font-weight: 600;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

apply_soft_frosted_ui(BG_BASE64)

# === Session & JSON ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.conversation_history = []
    st.session_state.community_view_topic = None

def safe_load_json(file, default={}):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        return default
    except:
        return default

def safe_save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except:
        pass

def load_comments():
    data = safe_load_json(COMMENTS_FILE, {t: [] for t in TOPICS})
    for t in TOPICS:
        if t not in data:
            data[t] = []
    return data

def save_comments(data):
    safe_save_json(COMMENTS_FILE, data)

# === Login ===
if not st.session_state.logged_in:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("# Mental Health Support Portal")
    st.markdown("### Your safe & confidential space")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password (6 digits)", type="password")
        if st.form_submit_button("Login"):
            if username and password.isdigit() and len(password) == 6:
                st.session_state.update({
                    "logged_in": True,
                    "username": username,
                    "conversation_history": safe_load_json(HISTORY_FILE, {}).get(username, [])
                })
                st.success("Welcome back! You're safe here")
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# === Main Header ===
st.markdown(f"# Welcome back, {st.session_state.username}")
st.markdown("### Your safe space for mental health support")

tab1, tab2, tab3, tab4 = st.tabs(["Chat Support", "Wellness Tools", "Resources & Appointments", "Community"])

# === Chat Support ===
with tab1:
    for msg in st.session_state.conversation_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if prompt := st.chat_input("How are you feeling today?"):
        st.session_state.conversation_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.spinner("Thinking..."):
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.conversation_history
            reply = client.chat.completions.create(model=GROQ_MODEL, messages=messages, temperature=0.7).choices[0].message.content if client else "I'm here to listen"
        
        st.session_state.conversation_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"): st.markdown(reply)
        
        data = safe_load_json(HISTORY_FILE, {})
        data[st.session_state.username] = st.session_state.conversation_history
        safe_save_json(HISTORY_FILE, data)
        st.rerun()

# === Wellness Tools ===
with tab2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Daily Affirmation</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-sub">Click for a kind message just for you</div>', unsafe_allow_html=True)
    if st.button("Give me an affirmation", key="aff"):
        st.success(random.choice(["You are enough", "This too shall pass", "You are stronger than you know", "It's okay to rest"]))
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Quick Meditation</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-sub">Take a moment to breathe</div>', unsafe_allow_html=True)
    if st.button("Start meditation", key="med"):
        st.info("Breathe in for 4... hold for 4... out for 6. You are safe.")
    st.markdown('</div>', unsafe_allow_html=True)

# === Resources & Appointments (NEW TAB NAME + DOCTORS + BOOKING) ===
with tab3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Curated Videos</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-sub">Helpful mental health content</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    for title, desc, link in YOUTUBE_RESOURCES:
        st.markdown(f'''
        <div class="glass-card">
            <div class="card-title">{title}</div>
            <div class="card-sub">{desc}</div>
            <a href="{link}" target="_blank">
                <button style="background:#ff0000;color:white;padding:10px 20px;border:none;border-radius:12px;">
                    Watch on YouTube
                </button>
            </a>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Consult a Specialist</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-sub">Book a confidential session</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    for doc in DOCTORS:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image(doc["image"], width=100)
        with col2:
            st.markdown(f"**{doc['name']}**")
            st.markdown(f"*{doc['specialty']}*")
            st.markdown(f"Location: {doc['location']}")
            st.markdown(f"Phone: {doc['phone']}")
        st.markdown("---")

    st.markdown("### Book an Appointment")
    with st.form("appointment_form"):
        patient_name = st.text_input("Your Name", value=st.session_state.username)
        doctor = st.selectbox("Choose Doctor", [d["name"] for d in DOCTORS])
        date = st.date_input("Preferred Date")
        time = st.time_input("Preferred Time")
        reason = st.text_area("Reason for visit (optional)")
        
        if st.form_submit_button("Book Appointment"):
            appointment = {
                "patient": patient_name,
                "doctor": doctor,
                "date": str(date),
                "time": str(time),
                "reason": reason,
                "booked_at": datetime.now().isoformat()
            }
            appointments = safe_load_json(APPOINTMENTS_FILE, [])
            appointments.append(appointment)
            safe_save_json(APPOINTMENTS_FILE, appointments)
            st.success(f"Appointment booked with {doctor} on {date} at {time}! Take care")

# === Community ===
with tab4:
    comments = load_comments()
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Community Space</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-sub">Share and read supportive messages. Be kind — this is a safe space.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.community_view_topic:
        topic = st.session_state.community_view_topic
        st.markdown(f'<div class="glass-card"><div class="card-title">{topic}</div>', unsafe_allow_html=True)
        if st.button("Back"):
            st.session_state.community_view_topic = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        for post in reversed(comments.get(topic, [])):
            st.markdown(f'''
            <div class="glass-card">
                <strong>{post.get("user", "Someone")}</strong> — {post.get("created_at", "")[:10]}
                <p style="margin-top:8px">{post.get("text", "")}</p>
            </div>
            ''', unsafe_allow_html=True)

        with st.form("post"):
            name = st.text_input("Name", value=st.session_state.username)
            text = st.text_area("Share something kind...")
            if st.form_submit_button("Post"):
                if text.strip():
                    comments.setdefault(topic, []).append({"user": name, "text": text.strip(), "created_at": datetime.now().isoformat()})
                    save_comments(comments)
                    st.success("Posted!")
                    st.rerun()
    else:
        cols = st.columns(2)
        for i, topic in enumerate(TOPICS):
            with cols[i % 2]:
                last = comments[topic][-1] if comments[topic] else None
                preview = (last["text"][:100] + "...") if last and len(last["text"]) > 100 else last["text"] if last else "No posts yet"
                st.markdown(f'<div class="glass-card"><div class="card-title">{topic}</div><div class="card-sub">{preview}</div>', unsafe_allow_html=True)
                if st.button("Open", key=topic):
                    st.session_state.community_view_topic = topic
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

# === Logout ===
if st.button("Log Out"):
    st.session_state.clear()
    st.rerun()
