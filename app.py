from flask import Flask, render_template
from flask_sock import Sock
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI
import tempfile, os, json
from models import init_db, get_db  # ✅ DB setup

# ENV and OpenAI setup
load_dotenv()
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Init app and DB
app = Flask(__name__, static_folder="static", template_folder="templates")
sock = Sock(app)
init_db()  # ✅ Initialize DB

# Track clients and ongoing calls
clients = {}
active_calls = {}  # ✅ Maps (caller, callee) → call_id
call_end_flags = {}  # ✅ Track call end confirmations

@app.route("/")
def index():
    return render_template("index.html")

# Google Cloud Speech-to-Text
from google.cloud import speech

def transcribe_chunk(audio_path):
    try:
        client = speech.SpeechClient()
        with open(audio_path, "rb") as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code="en-US",
        )
        response = client.recognize(config=config, audio=audio)
        transcript = " ".join([r.alternatives[0].transcript for r in response.results])
        return transcript.strip()
    except Exception as e:
        print("❌ Google STT error:", e)
        return ""
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except:
            pass

client = OpenAI()

# DALL·E Image Generator
def enhance_prompt(prompt: str) -> str:
    return (
        f"Ultra-detailed cinematic illustration of {prompt.strip().capitalize()}, "
        f"in sharp focus, colorful, highly realistic, soft lighting, trending on ArtStation, "
        f"wide angle, intricate details"
    )

import re
import random

# Add some dreamy themes and modifiers
dream_adjectives = [
    "surreal", "magical", "futuristic", "mystical", "celestial", "dreamlike", "whimsical",
    "colorful", "vibrant", "fantasy-inspired", "serene", "haunting", "cosmic"
]

visual_themes = [
    "forest", "sky", "ocean", "space", "castle", "robot world", "floating city",
    "ancient temple", "neon street", "dreamscape", "cloud island", "starry desert"
]

def generate_image(prompt):
    try:
        # 1. Clean transcript input
        cleaned = prompt.strip().lower()
        cleaned = re.sub(r"[^\w\s]", "", cleaned)

        # 2. Create a dream-like visual prompt
        adjective = random.choice(dream_adjectives)
        theme = random.choice(visual_themes)

        visual_prompt = f"{adjective} {theme} inspired by the thought: '{cleaned}'"

        # 3. Enhance for DALL·E
        formatted = enhance_prompt(visual_prompt)

        print("🎨 Dream Prompt:", formatted)

        # 4. Generate image
        res = client.images.generate(
            model="dall-e-3",
            prompt=formatted,
            size="1024x1024",
            quality="standard",
            n=1
        )
        return res.data[0].url

    except Exception as e:
        print("❌ Image generation error:", e)


# GPT Summary Generator
import re

def generate_summary(call_id):
    try:
        conn = get_db()
        rows = conn.execute("SELECT text FROM transcripts WHERE call_id = ?", (call_id,)).fetchall()
        conn.close()

        if not rows:
            return None

        full_text = "\n".join([r["text"] for r in rows])

        prompt = f"""
You are an assistant that summarizes conversations. Here's a full transcript:

\"\"\"
{full_text}
\"\"\"

Provide:
1. A concise summary (2-4 lines)
2. Three follow-up suggestions or creative ideas that emerged
"""

        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        response_text = completion.choices[0].message.content.strip()

        # Extract summary and follow-ups
        import re
        summary_match = re.search(r"1\..*?\n(.+?)(?:\n|$)", response_text, re.DOTALL)
        followups = re.findall(r"- (.+)", response_text)
        summary = summary_match.group(1).strip() if summary_match else response_text

        # ✅ Save to DB
        try:
            conn = get_db()
            conn.execute("""
                INSERT INTO summaries (call_id, summary, followups, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                call_id,
                summary,
                json.dumps(followups),
                datetime.utcnow().isoformat()
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print("❌ Failed to save summary to DB:", e)

        return {
            "Summary": summary,
            "Follow-up Suggestions": followups
        }

    except Exception as e:
        print("❌ Error generating summary:", e)
        return None

    
# WebSocket Handler
@sock.route("/ws")
def handle_socket(ws):
    user_id = None
    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break

            if isinstance(msg, str):
                data = json.loads(msg)

                if data["type"] == "register":
                    user_id = data["user"]
                    clients[user_id] = ws
                    print(f"[+] {user_id} registered")

                elif data["type"] == "call":
                    to = data["to"]
                    if to in clients:
                        clients[to].send(json.dumps({
                            "type": "incoming_call",
                            "from": data["from"]
                        }))
                    else:
                        ws.send(json.dumps({
                            "type": "call_failed",
                            "reason": f"User '{to}' is offline."
                        }))

                elif data["type"] == "accept":
                    if data["to"] in clients:
                        clients[data["to"]].send(json.dumps({"type": "call_accepted"}))
                        conn = get_db()
                        conn.execute("INSERT INTO calls (caller, callee, start_time) VALUES (?, ?, ?)",
                                     (data["to"], data["from"], datetime.utcnow().isoformat()))
                        conn.commit()
                        call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                        conn.close()
                        active_calls[(data["to"], data["from"])] = call_id

                elif data["type"] == "reject":
                    if data["to"] in clients:
                        clients[data["to"]].send(json.dumps({"type": "call_rejected"}))

                elif data["type"] == "signal":
                    if data["to"] in clients:
                        clients[data["to"]].send(json.dumps({
                            "type": "signal",
                            "from": data["from"],
                            "data": data["data"]
                        }))

                elif data["type"] == "end":
                    from_user = data["from"]
                    to_user = data["to"]
                    call_key = tuple(sorted((from_user, to_user)))
                    call_end_flags.setdefault(call_key, set()).add(from_user)

                    if len(call_end_flags[call_key]) == 2:
                        call_id = active_calls.pop(call_key, None)
                        call_end_flags.pop(call_key, None)
                        if call_id:
                            try:
                                conn = get_db()
                                conn.execute("UPDATE calls SET end_time = ? WHERE id = ?",
                                             (datetime.utcnow().isoformat(), call_id))
                                conn.commit()
                                conn.close()

                                summary = generate_summary(call_id)
                                if summary:
                                    print(f"\n📋 Summary for Call {call_id}:\n{summary}\n")
                                    for uid in (from_user, to_user):
                                        if uid in clients:
                                            clients[uid].send(json.dumps({
                                                "type": "summary",
                                                "text": json.dumps(summary)
                                            }))
                            except Exception as e:
                                print("❌ Error saving call end:", e)

            elif isinstance(msg, bytes) and user_id:
                print(f"📥 Received audio chunk ({len(msg)} bytes) from {user_id}")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(msg)
                    wav_path = f.name

                text = transcribe_chunk(wav_path)
                if text:
                    print(f"📝 Transcribed: {text}")
                    image_url = generate_image(text)
                    if image_url:
                        for uid, client_ws in clients.items():
                            try:
                                client_ws.send(json.dumps({
                                    "type": "dream",
                                    "text": text,
                                    "image": image_url
                                }))
                            except Exception as send_err:
                                print(f"❌ Send error to {uid}:", send_err)

                    try:
                        for key, call_id in active_calls.items():
                            if user_id in key:
                                conn = get_db()
                                conn.execute("INSERT INTO transcripts (call_id, timestamp, text) VALUES (?, ?, ?)",
                                             (call_id, datetime.utcnow().isoformat(), text))
                                conn.execute("INSERT INTO dreams (call_id, prompt, image_url, timestamp) VALUES (?, ?, ?, ?)",
                                             (call_id, text, image_url, datetime.utcnow().isoformat()))
                                conn.commit()
                                conn.close()
                    except Exception as err:
                        print("❌ DB save error:", err)

    finally:
        if user_id in clients:
            del clients[user_id]
            print(f"[-] Disconnected: {user_id}")

        for key in list(active_calls.keys()):
            if user_id in key:
                call_id = active_calls.pop(key)
                try:
                    conn = get_db()
                    conn.execute("UPDATE calls SET end_time = ? WHERE id = ?",
                                 (datetime.now(timezone.utc).isoformat(), call_id))
                    conn.commit()
                    conn.close()

                    summary = generate_summary(call_id)
                    if summary:
                        print(f"\n📋 Summary for Call {call_id}:\n{summary}\n")
                except Exception as e:
                    print("❌ Call end/save error:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
