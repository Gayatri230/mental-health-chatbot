# mychatbot.py — Final: Soft Frosted Glass UI, single background r1.avif, topic-based Community threads, trimmed tools
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
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (st.secrets.get("GROQ_API_KEY") if hasattr(st, "secrets") else None)

# Initialize Groq client (wrapped to avoid crash when key missing)
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None

# Model
GROQ_MODEL = "llama-3.1-8b-instant"

# Use the project's r1.avif background image — make sure file exists in same folder or in /mnt/data
BACKGROUND_IMAGE_PATH = "r1.avif"  # or "/mnt/data/r1.avif"
HISTORY_FILE = "chat_history.json"
APPOINTMENTS_FILE = "appointments.json"
COMMENTS_FILE = "comments.json"  # persistent community comments

SYSTEM_PROMPT = """
You are a confidential, non-judgmental Mental Health Support Chatbot.
You are not a substitute for a professional. Respond with empathy, calm, concise steps and safety guidance when needed.
"""

# ----------------------------
# Topics (confirmed final list)
# ----------------------------
TOPICS = [
    "Depression",
    "Anxiety",
    "Feeling Isolated?",
    "Family Issues",
    "Boundaries",
    "Late night sleep problems",
    "How to overcome anxiety?",
    "Having arguments in family daily",
    "How to overcome late night sleep?",
    "Recovering from panic attack?"
]

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
st.session_state.setdefault("community_view_topic", None)

# ----------------------------
# Persistence helpers
# ----------------------------
def safe_load_json(path):
    try:
        if not os.path.exists(path):
            return {}
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
# Comments persistence for Community (topic-based, Option A)
# ----------------------------
def _make_empty_comments_structure():
    return {t: [] for t in TOPICS}

def load_comments():
    """
    Returns a dict: topic -> list[comment dicts].
    Auto-creates the structure if file missing or invalid.
    Accepts legacy formats and migrates where reasonable.
    """
    data = safe_load_json(COMMENTS_FILE)
    # If missing or empty, create structure
    if not data:
        out = _make_empty_comments_structure()
        # Save immediately to ensure file exists
        safe_save_json(COMMENTS_FILE, out)
        return out

    # If data is a list (legacy), migrate into first topic
    if isinstance(data, list):
        out = _make_empty_comments_structure()
        for item in data:
            if isinstance(item, str):
                out[TOPICS[0]].append({
                    "id": str(uuid.uuid4()),
                    "user": "anonymous",
                    "text": item,
                    "created_at": datetime.utcnow().isoformat()
                })
            elif isinstance(item, dict):
                out[TOPICS[0]].append(item)
        safe_save_json(COMMENTS_FILE, out)
        return out

    # If dict, and keys look like topics (subset), normalize and ensure all topics present
    if isinstance(data, dict):
        # If data already is in expected format (topic -> list)
        if all(isinstance(v, list) for v in data.values()) and set(TOPICS).intersection(set(data.keys())):
            out = {t: [] for t in TOPICS}
            for k, v in data.items():
                if k in out and isinstance(v, list):
                    # keep only dict/list items
                    clean_list = []
                    for item in v:
                        if isinstance(item, dict):
                            # normalize essential fields
                            clean_list.append({
                                "id": item.get("id", str(uuid.uuid4())),
                                "user": item.get("user", "anonymous"),
                                "text": item.get("text", ""),
                                "created_at": item.get("created_at", datetime.utcnow().isoformat())
                            })
                    out[k] = clean_list
            # Save normalized structure
            safe_save_json(COMMENTS_FILE, out)
            return out
        # If wrapper or other dict format (e.g., {"comments": [...]})
        if "comments" in data and isinstance(data["comments"], list):
            out = _make_empty_comments_structure()
            for item in data["comments"]:
                if isinstance(item, dict):
                    out[TOPICS[0]].append({
                        "id": item.get("id", str(uuid.uuid4())),
                        "user": item.get("user", "anonymous"),
                        "text": item.get("text", ""),
                        "created_at": item.get("created_at", datetime.utcnow().isoformat())
                    })
                elif isinstance(item, str):
                    out[TOPICS[0]].append({
                        "id": str(uuid.uuid4()),
                        "user": "anonymous",
                        "text": item,
                        "created_at": datetime.utcnow().isoformat()
                    })
            safe_save_json(COMMENTS_FILE, out)
            return out

    # Unknown format: overwrite with empty structure to be safe
    out = _make_empty_comments_structure()
    safe_save_json(COMMENTS_FILE, out)
    return out

def save_comments(comments_by_topic):
    """
    Save the dict topic -> list-of-comments.
    Only known topics are saved (prevents accidental keys).
    """
    payload = {t: comments_by_topic.get(t, []) for t in TOPICS}
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
# Groq wrapper with safe fallback
# ----------------------------
def groq_chat(messages, model=GROQ_MODEL, temperature=0.6):
    if client is None:
        return "Error: Groq client not configured."
    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
        try:
            return resp.choices[0].message.content
        except Exception:
            return str(resp)
    except Exception as e:
        return f"Error: {e}"

# ----------------------------
# Generate session resources using Groq when available
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
    # fallback if Groq returned something not JSON
    return generate_resources_fallback(username, n=n)

# ----------------------------
# Ensure session generation each login (fresh content)
# ----------------------------
def ensure_session_resources_and_threads(username):
    # Only resources are generated for a session — no tools/auto-threads
    st.session_state['resources_for_session'] = generate_resources_for_session(username, n=6)

# ----------------------------
# Appointments
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
    # minimal compatibility — not used in UI
    cmd = (command or "").lower()
    if "affirm" in cmd or "affirmation" in cmd:
        return "You are capable, you are enough, and you deserve care. 💚"
    if "breath" in cmd or "breathing2" in cmd:
        return "Try: breathe in 4 — hold 2 — out 6. Repeat 6 times."
    # fallback
    return "Tool unavailable."

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

    # Community tab — topic cards & thread pages (user-only comments)
    with tab4:
        st.subheader("Community Discussions")

        # Top explanation card
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🌱 Community Topics</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-sub">Choose a topic, read what others have shared, or add your own supportive message. Only users can post — no bot replies here.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Load comments (topic -> list)
        comments_by_topic = load_comments()

        # If user has selected a topic to view, show thread view
        current_topic = st.session_state.get("community_view_topic", None)

        if current_topic:
            # Thread view for the selected topic
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown(f"<div class='card-title'>📂 {current_topic}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='card-sub'>Showing all user posts for: <strong>{current_topic}</strong></div>", unsafe_allow_html=True)
            if st.button("⬅ Back to topics", key="back_to_topics"):
                st.session_state["community_view_topic"] = None
                st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            # Display existing comments (most recent first)
            topic_comments = comments_by_topic.get(current_topic, []) or []
            st.markdown('<div style="margin-top:12px;">', unsafe_allow_html=True)
            if topic_comments:
                for c in reversed(topic_comments):
                    created = c.get("created_at", "")
                    user = c.get("user", "anonymous")
                    text = c.get("text", "")
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.markdown(f"<div style='font-weight:700'>{user} <span style='color:#c6d0d7;font-weight:400;font-size:12px'> — {created}</span></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin-top:6px'>{text}</div>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("No posts yet in this topic — share your experience or encouragement below.")

            # Posting form (only users)
            with st.form(f"post_form_{current_topic}"):
                poster = st.text_input("Display name (optional)", value=st.session_state.get("username", ""), key=f"post_name_{current_topic}")
                comment_text = st.text_area("Write your message (be kind, supportive, and respectful):", height=140, key=f"post_text_{current_topic}")
                submitted = st.form_submit_button("Post")
                if submitted:
                    if not comment_text or not comment_text.strip():
                        st.error("Comment cannot be empty.")
                    else:
                        poster_name = poster or st.session_state.get("username") or "anonymous"
                        new_comment = {
                            "id": str(uuid.uuid4()),
                            "user": poster_name,
                            "text": comment_text.strip(),
                            "created_at": datetime.utcnow().isoformat()
                        }
                        comments_by_topic.setdefault(current_topic, []).append(new_comment)
                        save_comments(comments_by_topic)
                        st.success("Your message has been posted.")
                        # clear the text area and refresh to show new post
                        st.session_state[f"post_text_{current_topic}"] = ""
                        st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # Topics overview: show big clickable cards with latest user comment as description
            st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;">', unsafe_allow_html=True)
            for topic in TOPICS:
                # get last comment preview
                lst = comments_by_topic.get(topic, []) or []
                preview = ""
                if lst:
                    last = lst[-1]  # newest at the end
                    preview = last.get("text", "")[:280]  # preview length
                # render card
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown(f"<div class='card-title'>{topic}</div>", unsafe_allow_html=True)
                if preview:
                    st.markdown(f"<div style='margin-bottom:10px;font-size:14px'>{preview}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='card-sub'>Last by: {lst[-1].get('user','anonymous')} — {lst[-1].get('created_at','')}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='margin-bottom:10px;font-size:14px;color:#c6d0d7'>No posts yet — be the first to share something supportive.</div>", unsafe_allow_html=True)
                if st.button("Open Topic", key=f"open_{topic}"):
                    st.session_state["community_view_topic"] = topic
                    st.experimental_rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

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
