import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import av
import uuid
from datetime import datetime
import sqlite3
import json
import asyncio
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Video Meeting", layout="centered")
st.title("� CONTEXT: 09:37 AM IST, Monday, July 21, 2025")
st.title("🎥 Gmail-based Video Meeting")

# SQLite database setup
DB_FILE = "meeting.db"

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
                timestamp TEXT,
                FOREIGN KEY (room_code) REFERENCES rooms (room_code)
            )
        """)
        conn.commit()

# Initialize database
init_db()

# Database functions
def save_room(room_code, participants):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO rooms (room_code, participants) VALUES (?, ?)",
                  (room_code, json.dumps(participants)))
        conn.commit()

def load_rooms():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT room_code, participants FROM rooms")
        rooms = {row[0]: json.loads(row[1]) for row in c.fetchall()}
    return rooms

def delete_room(room_code):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
        c.execute("DELETE FROM messages WHERE room_code = ?", (room_code,))
        conn.commit()

def add_message(room_code, sender, message, timestamp):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (room_code, sender, message, timestamp) VALUES (?, ?, ?, ?)",
                  (room_code, sender, message, timestamp))
        conn.commit()

def load_messages(room_code):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT sender, message, timestamp FROM messages WHERE room_code = ? ORDER BY timestamp", (room_code,))
        return [(row[0], row[1], row[2]) for row in c.fetchall()]

# Initialize session state
if "joined_room" not in st.session_state:
    st.session_state.joined_room = None
if "video_enabled" not in st.session_state:
    st.session_state.video_enabled = True
if "audio_enabled" not in st.session_state:
    st.session_state.audio_enabled = True
if "device_check_done" not in st.session_state:
    st.session_state.device_check_done = False
if "has_camera" not in st.session_state:
    st.session_state.has_camera = False
if "has_microphone" not in st.session_state:
    st.session_state.has_microphone = False

# Auto-refresh for chat updates (every 5 seconds)
st_autorefresh(interval=5000, key="chat_refresh")

# Check for media devices
async def check_media_devices():
    try:
        js_code = """
        async function getDevices() {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const hasCamera = devices.some(device => device.kind === 'videoinput');
                const hasMicrophone = devices.some(device => device.kind === 'audioinput');
                return { hasCamera, hasMicrophone };
            } catch (e) {
                return { hasCamera: false, hasMicrophone: false };
            }
        }
        getDevices();
        """
        result = await st.components.v1.html(js_code, height=0, width=0, scrolling=False)
        return result or {"hasCamera": False, "hasMicrophone": False}
    except Exception:
        return {"hasCamera": False, "hasMicrophone": False}

# Run device check
if not st.session_state.device_check_done:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    devices = loop.run_until_complete(check_media_devices())
    st.session_state.has_camera = devices.get("hasCamera", False)
    st.session_state.has_microphone = devices.get("hasMicrophone", False)
    st.session_state.device_check_done = True
    if not st.session_state.has_camera:
        st.session_state.video_enabled = False
    if not st.session_state.has_microphone:
        st.session_state.audio_enabled = False

# Login
gmail = st.text_input("Enter your Gmail ID to continue")

# Room actions
room_action = st.radio("Choose an action:", ("Create a Room", "Join a Room"))

if gmail:
    rooms = load_rooms()
    if room_action == "Create a Room":
        if st.button("➕ Create Room"):
            room_code = str(uuid.uuid4())[:6]
            rooms[room_code] = [gmail]
            save_room(room_code, rooms[room_code])
            st.session_state.joined_room = room_code
            st.success(f"✅ Room Created: `{room_code}`")

    elif room_action == "Join a Room":
        room_code = st.text_input("Enter Room Code:")
        if st.button("🔗 Join Room"):
            if room_code in rooms:
                if gmail not in rooms[room_code]:
                    rooms[room_code].append(gmail)
                    save_room(room_code, rooms[room_code])
                st.session_state.joined_room = room_code
                st.success(f"✅ Joined Room: `{room_code}`")
            else:
                st.error("❌ Room not found! Please check the room code.")

# Meeting UI
if st.session_state.joined_room:
    room_id = st.session_state.joined_room
    rooms = load_rooms()
    if room_id not in rooms:
        st.error("❌ Room no longer exists. Please create or join another room.")
        st.session_state.joined_room = None
        st.rerun()
    else:
        st.subheader(f"🟢 You are in Room: `{room_id}`")
        st.markdown("**Participants:** " + ", ".join(set(rooms[room_id])))

        # Device availability feedback
        if not st.session_state.has_camera and not st.session_state.has_microphone:
            st.warning("⚠️ No camera or microphone detected. Using chat for communication.")
        elif not st.session_state.has_camera:
            st.warning("⚠️ No camera detected. Audio and chat are available.")
        elif not st.session_state.has_microphone:
            st.warning("⚠️ No microphone detected. Video and chat are available.")

        # Media controls
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.session_state.has_microphone:
                if st.session_state.audio_enabled:
                    if st.button("🔇 Mute Mic"):
                        st.session_state.audio_enabled = False
                else:
                    if st.button("🎤 Unmute Mic"):
                        st.session_state.audio_enabled = True
        with col2:
            if st.session_state.has_camera:
                if st.session_state.video_enabled:
                    if st.button("📵 Turn Off Video"):
                        st.session_state.video_enabled = False
                else:
                    if st.button("📹 Turn On Video"):
                        st.session_state.video_enabled = True
        with col3:
            if st.button("🔄 Refresh Chat"):
                st.rerun()
        with col4:
            if st.button("❌ Leave Room"):
                if room_id in rooms and gmail in rooms[room_id]:
                    rooms[room_id].remove(gmail)
                    if not rooms[room_id]:  # Delete room if empty
                        delete_room(room_id)
                    else:
                        save_room(room_id, rooms[room_id])
                st.session_state.joined_room = None
                st.session_state.video_enabled = st.session_state.has_camera
                st.session_state.audio_enabled = st.session_state.has_microphone
                st.rerun()

        # WebRTC streamer
        webrtc_ctx = None
        if (st.session_state.video_enabled and st.session_state.has_camera) or (st.session_state.audio_enabled and st.session_state.has_microphone):
            try:
                class VideoProcessor:
                    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
                        return frame

                webrtc_ctx = webrtc_streamer(
                    key=f"stream_{room_id}",
                    mode=WebRtcMode.SENDRECV,
                    video_processor_factory=VideoProcessor,
                    media_stream_constraints={
                        "video": st.session_state.video_enabled if st.session_state.has_camera else False,
                        "audio": st.session_state.audio_enabled if st.session_state.has_microphone else False
                    },
                    async_processing=True,
                )
                if webrtc_ctx and webrtc_ctx.state.playing:
                    st.success("✅ Live video/audio call is active")
            except Exception as e:
                st.error(f"❌ Failed to start video/audio call: {str(e)}")
                st.info("ℹ️ Using chat for communication.")
        else:
            st.info("ℹ️ Video and audio are disabled or unavailable. Use the chat below to communicate.")

        # Messaging system
        st.subheader("💬 Chat")
        st.markdown("Click 'Refresh Chat' or wait for auto-refresh (every 5 seconds) to see new messages.")
        message_input = st.text_input("Type your message:", key=f"msg_input_{room_id}")
        if st.button("📩 Send Message"):
            if message_input:
                timestamp = datetime.now().strftime("%H:%M:%S")
                add_message(room_id, gmail, message_input, timestamp)
                st.rerun()

        # Display messages
        messages = load_messages(room_id)
        if messages:
            st.markdown("**Messages:**")
            for sender, msg, time in messages:
                st.markdown(f"**{sender}** ({time}): {msg}")
        else:
            st.markdown("No messages yet.")

else:
    st.warning("You are not in a room yet.")