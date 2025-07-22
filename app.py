import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av
import uuid
import sqlite3
from datetime import datetime
import json
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="🎥 Gmail Video Meet", layout="centered")
st.title("🎥 Gmail-based Video Meeting")

DB_FILE = "meeting.db"

# ---------- Database Setup ----------
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                room_code TEXT PRIMARY KEY,
                participants TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT,
                sender TEXT,
                message TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()

init_db()

def save_room(room_code, participants):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO rooms VALUES (?, ?)", (room_code, json.dumps(participants)))
        conn.commit()

def load_rooms():
    with sqlite3.connect(DB_FILE) as conn:
        data = conn.execute("SELECT room_code, participants FROM rooms").fetchall()
        return {row[0]: json.loads(row[1]) for row in data}

def delete_room(room_code):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
        conn.execute("DELETE FROM messages WHERE room_code = ?", (room_code,))
        conn.commit()

def add_message(room_code, sender, message, timestamp):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO messages (room_code, sender, message, timestamp) VALUES (?, ?, ?, ?)",
                     (room_code, sender, message, timestamp))
        conn.commit()

def load_messages(room_code):
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT sender, message, timestamp FROM messages WHERE room_code = ? ORDER BY timestamp",
                            (room_code,)).fetchall()

# ---------- Streamlit Session State ----------
if "joined_room" not in st.session_state:
    st.session_state.joined_room = None
if "video_enabled" not in st.session_state:
    st.session_state.video_enabled = True
if "audio_enabled" not in st.session_state:
    st.session_state.audio_enabled = True

# ---------- Auto-refresh Chat ----------
st_autorefresh(interval=5000, key="chat_refresh")

# ---------- Login & Room Selection ----------
gmail = st.text_input("Enter your Gmail to continue")

action = st.radio("Action:", ["Create Room", "Join Room"])

rooms = load_rooms()

if gmail:
    if action == "Create Room":
        if st.button("➕ Create"):
            room_code = str(uuid.uuid4())[:6]
            save_room(room_code, [gmail])
            st.session_state.joined_room = room_code
            st.success(f"Room Created: `{room_code}`")
    elif action == "Join Room":
        code = st.text_input("Enter Room Code")
        if st.button("🔗 Join"):
            if code in rooms:
                if gmail not in rooms[code]:
                    rooms[code].append(gmail)
                    save_room(code, rooms[code])
                st.session_state.joined_room = code
                st.success(f"Joined Room: `{code}`")
            else:
                st.error("Room not found")

# ---------- Meeting Interface ----------
if st.session_state.joined_room:
    room = st.session_state.joined_room
    rooms = load_rooms()

    if room not in rooms:
        st.error("Room doesn't exist.")
        st.session_state.joined_room = None
        st.rerun()

    st.subheader(f"🟢 Room `{room}`")
    st.write("**Participants:**", ", ".join(set(rooms[room])))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.session_state.audio_enabled:
            if st.button("🔇 Mute Mic"):
                st.session_state.audio_enabled = False
        else:
            if st.button("🎤 Unmute Mic"):
                st.session_state.audio_enabled = True
    with col2:
        if st.session_state.video_enabled:
            if st.button("📵 Video Off"):
                st.session_state.video_enabled = False
        else:
            if st.button("📹 Video On"):
                st.session_state.video_enabled = True
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()
    with col4:
        if st.button("❌ Leave"):
            rooms[room].remove(gmail)
            if not rooms[room]:
                delete_room(room)
            else:
                save_room(room, rooms[room])
            st.session_state.joined_room = None
            st.rerun()

    # ---------- WebRTC Stream ----------
    rtc_config = RTCConfiguration(
        {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
    )

    class VideoProcessor:
        def recv(self, frame):
            return frame

    webrtc_ctx = webrtc_streamer(
        key=f"webrtc_{room}",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=rtc_config,
        video_processor_factory=VideoProcessor,
        media_stream_constraints={
            "video": st.session_state.video_enabled,
            "audio": st.session_state.audio_enabled,
        },
        async_processing=True,
    )

    if webrtc_ctx.state.playing:
        st.success("✅ Live Call is Active")

    # ---------- Chat ----------
    st.subheader("💬 Chat")
    msg = st.text_input("Message", key=f"msg_input_{room}")
    if st.button("📩 Send"):
        if msg:
            add_message(room, gmail, msg, datetime.now().strftime("%H:%M:%S"))
            st.rerun()

    messages = load_messages(room)
    if messages:
        for sender, text, time in messages:
            st.markdown(f"**{sender}** ({time}): {text}")
    else:
        st.markdown("No messages yet.")
else:
    st.info("Join or Create a room to start a meeting.")
