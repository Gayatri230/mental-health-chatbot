# mychatbot.py — Final: Soft Frosted Glass UI, single background r1.avif, expanded Tools (modified)
import base64
import json
import uuid
import random
import hashlib
from datetime import datetime
import os
import streamlit as st
from groq import Groq

# Load API key securely
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Model
GROQ_MODEL = "llama-3.1-8b-instant"


# Use the project's r1.avif background image — make sure file exists in same folder or in /mnt/data
BACKGROUND_IMAGE_PATH = "r1.avif"  # or "/mnt/data/r1.avif"
HISTORY_FILE = "chat_history.json"
APPOINTMENTS_FILE = "appointments.json"
COMMENTS_FILE = "comments.json"  # <-- persistent community comments (must exist or will be created)

SYSTEM_PROMPT = """
You are a confidential, non-judgmental Mental Health Support Chatbot.
You are not a substitute for a professional. Respond with empathy, calm, concise steps and safety guidance when needed.
"""

# ----------------------------
# Helpers: load background as base64 (guaranteed to work)
# ----------------------------
def load_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

BG_BASE64 = load_image_base64(BACKGROUND_IMAGE_PATH)

# Soft frosted glass CSS (style B)
def apply_soft_frosted_ui(bg_base64):
    css = f"""
    <style>
    /* Background (base64 embedded: ensures it always loads) */
    .stApp {{
        background: linear-gradient(rgba(6,10,14,0.45), rgba(6,10,14,0.45)),
                    url("data:image/avif;base64,{bg_base64}") no-repeat center center fixed;
        background-size: cover;
    }}

    /* Frosted container that wraps page */
    .block-container {{
        background: rgba(10,12,14,0.38);
        backdrop-filter: blur(8px) saturate(120%);
        -webkit-backdrop-filter: blur(8px) saturate(120%);
        border-radius: 14px;
        padding: 20px 28px;
        border: 1px solid rgba(255,255,255,0.04);
    }}

    /* Glass card */
    .glass-card {{
        background: linear-gradient(rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 18px;
        border: 1px solid rgba(255,255,255,0.03);
        box-shadow: 0 8px 30px rgba(2,6,12,0.6);
        color: #e9f0f5;
    }}

    .card-title {{
        font-size: 18px;
        font-weight: 700;
        color: #f3fbff;
        margin-bottom: 6px;
    }}
    .card-sub {{
        color: #c6d0d7;
        margin-bottom: 10px;
    }}

    /* Chat message style (makes chat bubbles readable) */
    .stChatMessage {{
        background: rgba(17,20,22,0.55) !important;
        border-radius: 12px !important;
        padding: 10px !important;
        color: #eef6fb !important;
    }}

    /* Inputs & buttons */
    textarea, input, .stTextInput > div > div {{
        background: rgba(15,18,20,0.6) !important;
        color: #eef6fb !important;
        border-radius: 10px !important;
    }}

    .stButton>button {{
        background: linear-gradient(180deg, rgba(16,163,127,0.95), rgba(10,120,90,0.95)) !important;
        color: white !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
        border: none !important;
        box-shadow: 0 6px 18px rgba(10,120,90,0.18);
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        margin-bottom: 12px;
    }}

    .stTabs [data-baseweb="tab"] {{
        background: rgba(12,14,16,0.45);
        color: #eaf6fb !important;
        padding: 6px 12px;
        border-radius: 10px;
        font-weight: 600;
    }}

    .stTabs [aria-selected="true"] {{
        border-bottom: 3px solid rgba(16,163,127,0.95);
    }}

    .streamlit-expanderHeader {{
        color: #eaf6fb !important;
    }}
    .streamlit-expanderContent {{
        color: #cbd6db !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

apply_soft_frosted_ui(BG_BASE64)

# ----------------------------
# Session defaults
# ----------------------------
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("username", None)
st.session_state.setdefault("conversation_history", [])
st.session_state.setdefault("resources_for_session", None)
st.session_state.setdefault("tools_for_session", None)
st.session_state.setdefault("auto_threads_for_session", None)
st.session_state.setdefault("community_view", None)

# ----------------------------
# Persistence helpers
# ----------------------------
def safe_load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def safe_save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_history(username):
    data = safe_load_json(HISTORY_FILE)
    return data.get(username, [])

def save_history(username, history):
    all_history = safe_load_json(HISTORY_FILE)
    all_history[username] = history
    safe_save_json(HISTORY_FILE, all_history)

# ----------------------------
# Comments persistence for Community wall
# ----------------------------
def load_comments():
    """
    Returns list of comment dicts:
    [
      {"id": "<uuid>", "user": "alice", "text": "nice!", "created_at": "ISO timestamp"}
    ]
    """
    data = safe_load_json(COMMENTS_FILE)
    # If file contains a list (older simple file), accept it.
    if isinstance(data, list):
        # migrate list of strings into structured objects if needed
        out = []
        for item in data:
            if isinstance(item, str):
                out.append({
                    "id": str(uuid.uuid4()),
                    "user": "anonymous",
                    "text": item,
                    "created_at": datetime.utcnow().isoformat()
                })
            elif isinstance(item, dict):
                out.append(item)
        return out
    # if dict, expect {"comments": [...]}
    if isinstance(data, dict):
        comments = data.get("comments")
        if isinstance(comments, list):
            return comments
    # fallback: empty list
    return []

def save_comments(comments):
    # save as simple dict wrapper for forward-compat
    payload = {"comments": comments}
    safe_save_json(COMMENTS_FILE, payload)

# ----------------------------
# Deterministic seed helper (changes every login day)
# ----------------------------
def seed_from_username(username):
    if not username:
        username = str(uuid.uuid4())
    key = f"{username}-{datetime.utcnow().date().isoformat()}"
    h = hashlib.sha256(key.encode()).hexdigest()
    return int(h[:16], 16)

# ----------------------------
# Local fallback resource generator (includes youtube)
# ----------------------------
def generate_resources_fallback(username, n=6):
    rnd = random.Random(seed_from_username(username))
    youtube_links = [
        {"title":"10-Minute Anxiety Relief","summary":"Short breathing & grounding.","link":"https://www.youtube.com/watch?v=O-6f5wQXSu8"},
        {"title":"Guided Meditation for Stress","summary":"Calming guided meditation.","link":"https://www.youtube.com/watch?v=inpok4MKVLM"},
        {"title":"How to Stop Overthinking","summary":"Practical steps to reduce rumination.","link":"https://www.youtube.com/watch?v=1B8dZas2qg8"},
        {"title":"Depression – Understanding the Basics","summary":"Psychoeducation content.","link":"https://www.youtube.com/watch?v=z-IR48Mb3W0"},
        {"title":"Box Breathing Exercise","summary":"Box breathing guide.","link":"https://www.youtube.com/watch?v=FJJazKtH_9I"},
    ]
    ai_resources = [
        ("Grounding Breath Practice","A simple 4-4-4 breathing exercise to calm the nervous system."),
        ("Short Body Scan","A quick 5-minute body scan to notice and release tension."),
        ("CBT Thought Log","How to track negative thoughts and gently reframe them."),
        ("Sleep Hygiene Tips","Practical bedtime habits to improve sleep quality."),
        ("Micro-activity Plan","Start with 5 minutes of activity to build momentum."),
        ("Social Re-connection Steps","Small ways to reach out to one person this week.")
    ]
    out = []
    for i in range(n):
        if rnd.random() > 0.45:
            out.append(rnd.choice(youtube_links))
        else:
            t, s = rnd.choice(ai_resources)
            out.append({"title": t, "summary": s, "link": f"search:{t.replace(' ', '+')}"})
    return out

# ----------------------------
# Local fallback threads generator
# ----------------------------
def generate_threads_fallback(username, n_threads=5):
    rnd = random.Random(seed_from_username(username) + 17)
    titles = [
        "Night anxiety—how do you cope?",
        "Anyone else struggle with overthinking?",
        "Small habits that improved my mood",
        "How to set boundaries with family",
        "Sleep routine tips that helped me"
    ]
    snippets = [
        "I used weighted blankets and it helped me sleep a bit better.",
        "Short walks in morning made a difference for me.",
        "Talking to one trusted person weekly helped.",
        "Breathing exercises calm me within minutes.",
        "Micro tasks helped me start my day without pressure."
    ]
    threads = {}
    for i in range(1, n_threads+1):
        title = rnd.choice(titles)
        posts = []
        count = rnd.choice([2,3])
        for _ in range(count):
            user = rnd.choice(["UserA","UserB","SupportSam","PeerJess"])
            time = f"{rnd.randint(1,48)} hours ago"
            content = rnd.choice(snippets)
            posts.append({"user": user, "time": time, "content": content})
        threads[f"auto_thread_{i}"] = {"title": title, "posts": posts}
    return threads

# ----------------------------
# Groq wrapper with safe fallback
# ----------------------------
def groq_chat(messages, model=GROQ_MODEL, temperature=0.6):
    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
        try:
            return resp.choices[0].message.content
        except Exception:
            return str(resp)
    except Exception as e:
        return f"Error: {e}"

# ----------------------------
# Generate session resources/tools/threads using Groq when available
# with deterministic local fallback
# ----------------------------
def generate_resources_for_session(username, n=6):
    prompt = (
        f"Create {n} concise, safe mental-health self-help resources suitable for a peer support app. "
        "Return JSON array with keys title, summary, link (link may be a keyword or URL)."
    )
    messages = [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":prompt}]
    resp = groq_chat(messages)
    try:
        parsed = json.loads(resp)
        if isinstance(parsed, list) and parsed:
            cleaned = []
            for item in parsed[:n]:
                title = item.get("title") or item.get("name") or "Resource"
                summary = item.get("summary") or item.get("desc") or ""
                link = item.get("link") or item.get("url") or f"search:{title.replace(' ', '+')}"
                cleaned.append({"title": title, "summary": summary, "link": link})
            return cleaned
    except Exception:
        return generate_resources_fallback(username, n=n)

def generate_tools_for_session(username):
    # We keep this function for backward compatibility, but it will not be used to populate the Tools tab.
    prompt = (
        "Generate 6 short self-help tools (title + 1-line description + command name) for a mental health app. "
        "Return JSON array with keys: title, summary, command."
    )
    messages = [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":prompt}]
    resp = groq_chat(messages)
    try:
        parsed = json.loads(resp)
        if isinstance(parsed, list) and parsed:
            cleaned = []
            for item in parsed[:6]:
                title = item.get("title") or item.get("name") or "Tool"
                summary = item.get("summary") or item.get("desc") or ""
                command = item.get("command") or title
                cleaned.append({"title": title, "summary": summary, "command": command})
            return cleaned
    except Exception:
        return generate_tools_fallback(username)

def generate_auto_threads_for_session(username, n_threads=5):
    prompt = (
        f"Create {n_threads} short community discussion threads focused on mental health topics. "
        "Return JSON array with title and posts (posts: user, time, content)."
    )
    messages = [{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":prompt}]
    resp = groq_chat(messages)
    try:
        arr = json.loads(resp)
        threads = {}
        for i, t in enumerate(arr, 1):
            threads[f"auto_thread_{i}"] = {"title": t.get("title", f"Thread {i}"), "posts": t.get("posts", [])}
        return threads
    except Exception:
        return generate_threads_fallback(username, n_threads=n_threads)

# ----------------------------
# Ensure session generation each login (fresh content)
# ----------------------------
def ensure_session_resources_and_threads(username):
    st.session_state['resources_for_session'] = generate_resources_for_session(username, n=6)
    st.session_state['tools_for_session'] = generate_tools_for_session(username)
    st.session_state['auto_threads_for_session'] = generate_auto_threads_for_session(username, n_threads=5)

# ----------------------------
# Appointments (same as before)
# ----------------------------
DOCTOR_PROFILES = [
    {"id":"doc1","name":"Dr. Asha Rao","specialty":"Anxiety, CBT Therapy","location":"Ballari, Karnataka","phone":"+91-90000-00001","image":"https://i.ibb.co/3chGS5k/doctor1.png"},
    {"id":"doc2","name":"Dr. Kiran Dev","specialty":"Depression, Mood Disorders","location":"Ballari, Karnataka","phone":"+91-90000-00002","image":"https://i.ibb.co/Zcp99sM/doctor2.png"},
    {"id":"doc3","name":"Dr. Meera Iyer","specialty":"Sleep Issues & Stress","location":"Ballari, Karnataka","phone":"+91-90000-00003","image":"https://i.ibb.co/7vbL8jr/doctor3.png"}
]

def load_appointments():
    try:
        with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_appointments(lst):
    try:
        with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(lst, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

def book_appointment_ui():
    st.subheader("📅 Book a Mental Health Appointment")
    st.markdown("Professionals located in *Ballari, Karnataka*")

    for doc in DOCTOR_PROFILES:
        with st.container():
            col1, col2 = st.columns([1,3])
            with col1:
                st.image(doc["image"], width=110)
            with col2:
                st.markdown(f"### *{doc['name']}*")
                st.markdown(f"*Specialty:* {doc['specialty']}")
                st.markdown(f"*Location:* {doc['location']}")
                st.markdown(f"*Contact:* {doc['phone']}")
        st.markdown("---")

    st.markdown("### 📝 Request Appointment")
    with st.form("appt_form"):
        name = st.text_input("Your Name")
        contact = st.text_input("Phone or Email")
        selected = st.selectbox("Choose Doctor", DOCTOR_PROFILES, format_func=lambda d: d["name"])
        date = st.date_input("Preferred Date")
        time = st.time_input("Preferred Time")
        reason = st.text_area("Reason for Visit")
        submit = st.form_submit_button("Request Appointment")
        if submit:
            appt = {
                "id": str(uuid.uuid4()),
                "name": name,
                "contact": contact,
                "doctor": selected["name"],
                "date": date.isoformat(),
                "time": time.strftime("%H:%M"),
                "reason": reason,
                "created_at": datetime.utcnow().isoformat()
            }
            all_appts = load_appointments()
            all_appts.append(appt)
            save_appointments(all_appts)
            st.success(f"Appointment request sent to *{selected['name']}* for *{date} at {time.strftime('%H:%M')}*.")
            st.markdown(f"*Reference ID:* {appt['id']}")

# ----------------------------
# Chat & Tool execution
# ----------------------------
def generate_response(user_input):
    history = st.session_state["conversation_history"]
    messages = [{"role":"system","content":SYSTEM_PROMPT}] + history + [{"role":"user","content":user_input}]
    history.append({"role":"user","content":user_input})
    reply = groq_chat(messages)
    history.append({"role":"assistant","content":reply})
    save_history(st.session_state.get("username","anonymous"), history)
    return reply

def run_tool_command(command):
    # This function is retained for compatibility but is not used for the Tools tab.
    cmd = (command or "").lower()
    if "affirm" in cmd or "affirmation" in cmd:
        return "You are capable, you are enough, and you deserve care. 💚"
    if "breath" in cmd or "breathing2" in cmd:
        return "Try: breathe in 4 — hold 2 — out 6. Repeat 6 times."
    if "body" in cmd or "bodyscan" in cmd:
        return "Start at your toes — notice sensations slowly upward — release tension as you go."
    if "journal" in cmd or "journal_prompt" in cmd:
        prompts = [
            "What is one small win from today?",
            "Name one thing you felt grateful for today.",
            "What thought would I like to challenge and why?"
        ]
        return random.choice(prompts)
    if "micro" in cmd or "activity" in cmd:
        activities = ["5-minute walk", "tidy one shelf", "call one friend for 2 minutes", "drink a glass of water"]
        return f"Try this micro-activity: {random.choice(activities)}"
    if "sleep" in cmd or "sleep_tips" in cmd:
        return "Sleep tip: Reduce screens 60 min before bed, cool room, consistent time."
    if "ground" in cmd or "grounding" in cmd:
        return "Grounding 5-4-3-2-1: name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, 1 you taste."
    if "social" in cmd or "social_reach" in cmd:
        return "Send a short message: 'Thinking of you — hope you're well.' Keep it simple."
    # fallback: call Groq for a one-liner tip
    try:
        resp = groq_chat([{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":f"Provide a concise one-line self-help tip for: {command}"}], temperature=0.5)
        return resp
    except Exception:
        return "Tool unavailable right now."

# ----------------------------
# Positive Affirmations & Guided Meditations (kept tools)
# ----------------------------
AFFIRMATIONS = [
    "I am capable of handling whatever today brings.",
    "I deserve kindness — from myself and others.",
    "Small steps forward are progress.",
    "I am not my thoughts; I am the observer of them.",
    "My feelings are valid and temporary.",
    "I choose to be gentle with myself today.",
    "I have overcome hard things before; I can do it again.",
    "I breathe in calm and breathe out tension."
]

MEDITATIONS = [
    "Close your eyes. Take 3 deep breaths. On each exhale, feel your shoulders drop. Imagine a warm light filling your chest.",
    "Sit comfortably. Breathe in for 4, hold 2, out for 6. With each breath, imagine calm spreading from head to toe.",
    "Find your breath. Count to 4 on the inhale, 4 on the exhale. Let thoughts pass like clouds — return to the breath.",
    "Scan your body from toes to head. Notice tension, breathe into it, imagine it softening and releasing.",
    "Picture yourself beside a calm lake. Hear the water, feel the breeze. Breathe slowly and rest in that image."
]

def get_random_affirmation():
    # return a new random affirmation each time
    return random.choice(AFFIRMATIONS)

def get_random_meditation():
    return random.choice(MEDITATIONS)

# ----------------------------
# Community thread UI (soft frosted card style) — retains mock auto threads
# ----------------------------
def community_thread_page(key):
    threads = st.session_state.get("auto_threads_for_session", {})
    thread = threads.get(key)
    if not thread:
        st.error("Thread not found.")
        return

    # Explanation card
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">👥 Community Forums — What this area is</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-sub">These threads are mock-generated to model real peer-support discussions for privacy and demo purposes. They are illustrative, not professional advice.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.subheader(thread.get("title","Discussion"))
    if st.button("⬅ Back"):
        st.session_state["community_view"] = None
        st.rerun()

    for post in thread.get("posts", []):
        role = "assistant" if "Bot" in post.get("user","") else "user"
        with st.chat_message(role):
            st.markdown(f"**{post.get('user','unknown')}** ({post.get('time','')})")
            st.markdown(post.get("content",""))

    st.markdown("---")
    reply = st.text_area("Write a reply (mock)")
    if st.button("Post"):
        if reply.strip():
            st.success("Reply posted (mock). This demo does not persist user-generated thread replies.")
        else:
            st.warning("Write something before posting.")

# ----------------------------
# Login page
# ----------------------------
def login_page():
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.title("🔐 Mental Health Portal Login")
    with st.form("loginform"):
        user = st.text_input("Username (max 8 chars)")
        pw = st.text_input("Password (6 digits)", type="password")
        sub = st.form_submit_button("Login")
        if sub:
            if len(user) <= 8 and len(pw) == 6:
                st.session_state["username"] = user
                st.session_state["conversation_history"] = load_history(user)
                st.session_state["logged_in"] = True
                ensure_session_resources_and_threads(user)
                st.success("Login successful! Loading...")
                st.rerun()
            else:
                st.error("❌ Username or password invalid.")
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Main App
# ----------------------------
def main_app():
    u = st.session_state.get("username","")
    st.title(f"Welcome, {u} 🫂")
    st.markdown("Your AI-supported mental health space.")

    tab1, tab2, tab3, tab4 = st.tabs(["🤖 Chatbot","✨ Wellness Tools","📚 Resources","👥 Community"])

    # Chatbot tab
    with tab1:
        st.subheader("🧠 Mental Health Support Chatbot")
        for msg in st.session_state.get("conversation_history", []):
            with st.chat_message(msg.get("role","assistant")):
                st.markdown(msg.get("content",""))

        if user_msg := st.chat_input("Type here…"):
            with st.chat_message("user"):
                st.markdown(user_msg)
            with st.spinner("Thinking…"):
                bot = generate_response(user_msg)
            with st.chat_message("assistant"):
                st.markdown(bot)
            st.rerun()

    # Tools tab — only Affirmation & Guided Meditation (per your request)
    with tab2:
        st.subheader("Instant Self-care Tools")
        # Affirmation card
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">💛 Positive Affirmation</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-sub">Click to receive a fresh positive affirmation each time.</div>', unsafe_allow_html=True)
        if st.button("Give me an affirmation", key="affirm_btn"):
            af = get_random_affirmation()
            st.success(af)
        st.markdown('</div>', unsafe_allow_html=True)

        # Guided Meditation card
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🧘 Guided Meditation</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-sub">Click to receive a new short guided meditation/script each time.</div>', unsafe_allow_html=True)
        if st.button("Start Meditation", key="meditate_btn"):
            med = get_random_meditation()
            st.info(med)
        st.markdown('</div>', unsafe_allow_html=True)

    # Resources tab
    with tab3:
        st.subheader("Recommended Resources")
        for r in st.session_state.get("resources_for_session", []) or []:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown(f"<div class='card-title'>{r.get('title')}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card-sub'>{r.get('summary')}</div>", unsafe_allow_html=True)
            link = r.get("link","")
            if link.startswith("http"):
                st.markdown(f"[Open resource]({link})")
            else:
                st.markdown(f"🔗 Try searching: *{link}*")
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
        book_appointment_ui()

    # Community tab — persistent comment wall + mock threads
    with tab4:
        st.subheader("Community Discussions")

        # --- Persistent Community Wall (saved to comments.json) ---
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🌱 Community Wall</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-sub">Share supportive messages. All posts are saved and visible to everyone.</div>', unsafe_allow_html=True)

        comments = load_comments()  # list of dicts
        # Input area
        with st.form("community_post_form"):
            st.text_input("Display name (optional)", value=st.session_state.get("username",""), key="post_name_input")
            comment_text = st.text_area("Write something kind, supportive, or share a short experience:", height=100)
            submit_post = st.form_submit_button("Post to Community")
            if submit_post:
                if comment_text and comment_text.strip():
                    poster = st.session_state.get("post_name_input") or st.session_state.get("username") or "anonymous"
                    new_comment = {
                        "id": str(uuid.uuid4()),
                        "user": poster,
                        "text": comment_text.strip(),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    comments.append(new_comment)
                    save_comments(comments)
                    st.success("Your comment has been posted to the Community Wall.")
                    # refresh state to show new comment immediately
                    st.experimental_rerun()
                else:
                    st.error("Comment cannot be empty.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Display comments (most recent first)
        st.markdown('<div style="margin-top:12px;">', unsafe_allow_html=True)
        if comments:
            for c in reversed(comments):
                created = c.get("created_at","")
                user = c.get("user","anonymous")
                text = c.get("text","")
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown(f"<div style='font-weight:700'>{user} <span style='color:#c6d0d7;font-weight:400;font-size:12px'> — {created}</span></div>", unsafe_allow_html=True)
                st.markdown(f"<div style='margin-top:6px'>{text}</div>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No community posts yet — be the first to share some positivity.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # --- Mock auto-generated threads (kept for demo) ---
        threads = st.session_state.get("auto_threads_for_session", {}) or {}
        for key, t in threads.items():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown(f"<div class='card-title'>{t.get('title')}</div>", unsafe_allow_html=True)
            last = t.get("posts", [])[-1].get("user","") if t.get("posts") else ""
            st.markdown(f"<div class='card-sub'>Last reply: {last}</div>", unsafe_allow_html=True)
            if st.button("Open Thread", key=f"thread_{key}"):
                st.session_state["community_view"] = key
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.get("community_view"):
            community_thread_page(st.session_state.get("community_view"))

    # Logout
    if st.button("🚪 Log Out"):
        st.session_state.clear()
        st.rerun()

# ----------------------------
# Entry point
# ----------------------------
if not st.session_state.get("logged_in"):
    login_page()
    st.stop()
else:
    main_app()
