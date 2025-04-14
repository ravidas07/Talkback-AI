import tkinter as tk
from tkinter import ttk
import pyttsx3
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv
import os
import threading
import tempfile
import wave
import pyaudio
from faster_whisper import WhisperModel
import math
import time

# Disable symlink warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Load API key
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenAI client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
    default_headers={
        "HTTP-Referer": "http://localhost",
        "X-Title": "TalkBackGUI"
    }
)

# Set up TTS engine
engine = pyttsx3.init()
engine.setProperty("rate", 200)

def speak(text):
    engine.say(text)
    engine.runAndWait()

# Whisper model (lazy load)
model = None

def ensure_model_loaded():
    global model
    if model is None:
        model = WhisperModel("tiny", compute_type="int8", device="cpu")

# Message history
messages = [
    {"role": "system", "content": "You are a smart, friendly assistant."}
]

# Stop audio on close
def on_close():
    engine.stop()
    root.destroy()

# Pulse animation
pulsing = False
def animate_pulse():
    global pulsing
    r = 10
    pulse_canvas.delete("all")
    for i in range(5):
        pulse_canvas.create_oval(40 - r, 40 - r, 40 + r, 40 + r, outline="#3FC1C9", width=1)
        r += 10
    if pulsing:
        root.after(500, animate_pulse)

# Listen and transcribe
def listen():
    threading.Thread(target=listen_task).start()

def listen_task():
    ensure_model_loaded()

    global pulsing
    status_label.config(text="🎙 Listening...")
    pulsing = True
    animate_pulse()

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    RECORD_SECONDS = 5

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    pulsing = False
    pulse_canvas.delete("all")
    status_label.config(text="🧠 Transcribing...")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        wf = wave.open(temp_audio.name, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        try:
            segments, _ = model.transcribe(temp_audio.name)
            full_text = " ".join(segment.text for segment in segments)
            input_text.set(full_text.strip())
            status_label.config(text="✅ Transcribed.")
            send_to_ai()
        except Exception as e:
            status_label.config(text="⚠️ Whisper failed.")
            print("Whisper error:", e)

# Send to AI
def send_to_ai():
    user_input = input_text.get().strip()
    if not user_input:
        return

    chat_log.insert(tk.END, f"\n🧑 You: {user_input}\n")
    messages.append({"role": "user", "content": user_input})
    input_text.set("")

    def process_ai():
        try:
            response = client.chat.completions.create(
                model="mistralai/mistral-7b-instruct",
                messages=messages
            )
            reply = response.choices[0].message.content.strip()
            chat_log.insert(tk.END, f"🤖 AI: {reply}\n")
            messages.append({"role": "assistant", "content": reply})
            speak(reply)
        except Exception as e:
            chat_log.insert(tk.END, "❌ AI error.\n")
            print("AI error:", e)

    threading.Thread(target=process_ai).start()

# GUI Setup (initial loading screen)
loading_root = tk.Tk()
loading_root.title("Loading TalkBack AI")
loading_root.geometry("400x150")
loading_root.configure(bg="#1e1e2e")
loading_root.attributes("-alpha", 1.0)

loading_label = tk.Label(loading_root, text="🔄 Loading model...", font=("Segoe UI", 12), fg="white", bg="#1e1e2e")
loading_label.pack(pady=20)

loading_var = tk.IntVar()
loading_bar = ttk.Progressbar(loading_root, maximum=100, variable=loading_var, length=300)
loading_bar.pack(pady=10)

def launch_main_gui():
    global root, chat_log, input_text, send_btn, voice_btn, pulse_canvas, status_label

    root = tk.Tk()
    root.title("🔊 TalkBack AI")
    root.geometry("600x720")
    root.configure(bg="#1e1e2e")
    root.protocol("WM_DELETE_WINDOW", on_close)

    style = ttk.Style()
    style.configure("TButton",
                    font=("Segoe UI", 12),
                    padding=6,
                    foreground="#ffffff",
                    background="#0055ff",
                    relief="flat")

    chat_log = tk.Text(root, wrap=tk.WORD, font=("Segoe UI", 12), bg="#2e2e3e", fg="#f8f8f2", insertbackground="white")
    chat_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    input_text = tk.StringVar()
    entry = tk.Entry(root, textvariable=input_text, font=("Segoe UI", 14), bg="#38384a", fg="white", insertbackground="white")
    entry.pack(fill=tk.X, padx=10, pady=(0, 10))

    btn_frame = tk.Frame(root, bg="#1e1e2e")
    btn_frame.pack(pady=5)

    send_btn = tk.Button(
        btn_frame,
        text="Send",
        command=send_to_ai,
        font=("Segoe UI", 12),
        bg="black",
        fg="white",
        activebackground="#0a0a0a",
        activeforeground="cyan",
        relief=tk.FLAT,
        padx=10,
        pady=5
    )
    send_btn.pack(side=tk.LEFT, padx=10)

    voice_btn = tk.Canvas(btn_frame, width=80, height=80, bg="#1e1e2e", highlightthickness=0)
    voice_btn.pack(side=tk.LEFT, padx=10)
    voice_btn.create_oval(10, 10, 70, 70, fill="#0055ff", outline="")
    voice_btn.create_text(40, 40, text="🎙️", fill="white", font=("Segoe UI", 20))
    voice_btn.bind("<Button-1>", lambda e: listen())

    pulse_canvas = tk.Canvas(root, width=80, height=80, bg="#1e1e2e", highlightthickness=0)
    pulse_canvas.pack()

    status_label = tk.Label(root, text="✅ Whisper ready", font=("Segoe UI", 10), fg="gray", bg="#1e1e2e")
    status_label.pack(pady=5)

    chat_log.insert(tk.END, "🤖 AI: Hello! I am your TalkBack assistant. Speak or type to start chatting.\n")

    import sys
    def auto_reload():
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class ReloadHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path.endswith(".py"):
                    print("🔁 Reloading...")
                    os.execv(sys.executable, ['python'] + sys.argv)

        observer = Observer()
        observer.schedule(ReloadHandler(), path='.', recursive=False)
        observer.start()

    auto_reload()
    root.mainloop()

# Preload model in background then launch main GUI
def preload_model_background():
    def load():
        for i in range(1, 101):
            time.sleep(0.01)
            loading_var.set(i)
            loading_label.config(text=f"🔄 Loading model... {i}%")
            loading_bar.update_idletasks()
        global model
        model = WhisperModel("tiny", compute_type="int8", device="cpu")
        fade_out_loading()

    threading.Thread(target=load).start()

def fade_out_loading(alpha=1.0):
    if alpha > 0:
        loading_root.attributes("-alpha", alpha)
        loading_root.after(50, lambda: fade_out_loading(alpha - 0.05))
    else:
        loading_root.destroy()
        launch_main_gui()

preload_model_background()
loading_root.mainloop()
