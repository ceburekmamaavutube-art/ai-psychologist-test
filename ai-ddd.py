from __future__ import annotations

import os
import sys
import time
import queue
import wave
import platform
import subprocess
import threading

import sounddevice as sd
import speech_recognition as sr
from openai import OpenAI

try:
    import pyttsx3
    _HAS_PYTTSX3 = True
except ImportError:
    _HAS_PYTTSX3 = False


# ─── НАСТРОЙКИ ─────────────────────────────────────────────────────────────
# ВНИМАНИЕ! СЮДА НУЖНО ВСТАВИТЬ ССЫЛКУ С ТВОЕГО СЕРВЕРА (Replit / Render / Ngrok)
# Обязательно оставь /v1 в конце ссылки!
PRANKSTER_URL = "https://tvoy-proekt.replit.app/v1" 
FAKE_API_KEY  = "sk-fake-key-for-local-testing"

client = OpenAI(api_key=FAKE_API_KEY, base_url=PRANKSTER_URL)

CHAT_MODEL  = "openai/gpt-4o-mini"
RECORD_RATE = 16000
CHANNELS    = 1

SYSTEM_PROMPT = "Ты психолог."


# ─── ЦВЕТА ─────────────────────────────────────────────────────────────────
class C:
    PINK   = "\033[95m"
    CYAN   = "\033[96m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"


def enable_ansi() -> None:
    if os.name == "nt":
        os.system("")


# ─── ЛОКАЛЬНАЯ ОЗВУЧКА ─────────────────────────────────────────────────────
def init_engine():
    if not _HAS_PYTTSX3:
        return None
    try:
        engine = pyttsx3.init()
    except Exception:
        return None
    engine.setProperty("rate", 175)
    engine.setProperty("volume", 1.0)
    try:
        voices = engine.getProperty("voices") or []
        for v in voices:
            name = (v.name or "").lower()
            vid  = (v.id or "").lower()
            if ("russian" in name or "ru-ru" in vid or "ru_ru" in vid
                    or "irina" in name or "pavel" in name):
                engine.setProperty("voice", v.id)
                break
    except Exception:
        pass
    return engine


def speak(text: str, engine) -> None:
    print(f"\n{C.CYAN}{C.BOLD}Психолог ♥{C.RESET} {C.CYAN}{text}{C.RESET}")
    if engine is not None:
        try:
            engine.say(text)
            engine.runAndWait()
            return
        except Exception:
            pass
    # Если pyttsx3 сдох, юзаем PowerShell (резерв на Windows)
    if platform.system() == "Windows":
        try:
            safe = text.replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                f"$s.Speak('{safe}');"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", script], 
                           check=True, capture_output=True)
        except Exception:
            print(f"{C.RED}[TTS] Голос недоступен.{C.RESET}")


# ─── МИКРОФОН И РАСПОЗНАВАНИЕ ──────────────────────────────────────────────
def record_audio(filename: str = "input.wav") -> str | None:
    q: queue.Queue[bytes] = queue.Queue()
    recording = threading.Event()

    def callback(indata, frames, time_info, status):
        if recording.is_set():
            q.put(bytes(indata))

    print(f"\n{C.YELLOW}[Запись] Enter — начать говорить...{C.RESET}")
    input()

    try:
        with sd.RawInputStream(samplerate=RECORD_RATE, channels=CHANNELS,
                               dtype="int16", callback=callback):
            recording.set()
            print(f"{C.YELLOW}[Запись] Говорите... Enter — стоп.{C.RESET}")
            input()
            recording.clear()
    except Exception as e:
        print(f"{C.RED}[Запись] Ошибка микрофона: {e}{C.RESET}")
        return None

    chunks = []
    while not q.empty():
        chunks.append(q.get())

    if not chunks:
        return None

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(RECORD_RATE)
        for c in chunks:
            wf.writeframes(c)

    return filename


def transcribe(file_path: str) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio, language="ru-RU")
    except Exception:
        return ""


# ─── ОТПРАВКА НА ТВОЙ СЕРВЕР ───────────────────────────────────────────────
def ask_ai(messages) -> str:
    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"{C.RED}[Сеть] Ошибка связи с сервером: {e}{C.RESET}")
        return "Извините, связь прервалась. Повторите, пожалуйста."


# ─── СЕАНС ─────────────────────────────────────────────────────────────────
def run_session(engine) -> None:
    greeting = "Здравствуйте, Дима. Я вас слушаю."
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": greeting},
    ]
    speak(greeting, engine)

    while True:
        audio_file = record_audio()
        if not audio_file:
            continue

        user_text = transcribe(audio_file)
        if not user_text:
            print(f"{C.YELLOW}[STT] Не расслышал.{C.RESET}")
            continue

        print(f"\n{C.GREEN}{C.BOLD}Дима:{C.RESET} {C.GREEN}{user_text}{C.RESET}")

        if user_text.lower().strip() in {"пока", "выход", "до свидания", "стоп"}:
            speak("До свидания, Дима.", engine)
            return

        messages.append({"role": "user", "content": user_text})
        
        # Отправляем текст Димы тебе, ждем ответ
        print(f"{C.YELLOW}[Ожидание ответа психолога...]{C.RESET}")
        ai_text = ask_ai(messages)
        
        messages.append({"role": "assistant", "content": ai_text})
        speak(ai_text, engine)


# ─── МЕНЮ ──────────────────────────────────────────────────────────────────
def main() -> None:
    enable_ansi()
    os.system("cls" if os.name == "nt" else "clear")

    print(f"\n{C.PINK}══════════════════════════════════════════════{C.RESET}")
    print(f"{C.PINK}  ♥  {C.BOLD}СЕАНС ПСИХОЛОГА ♥{C.RESET}")
    print(f"{C.PINK}══════════════════════════════════════════════{C.RESET}\n")

    engine = init_engine()

    while True:
        print(f"  {C.BOLD}1{C.RESET}. Начать сеанс")
        print(f"  {C.BOLD}2{C.RESET}. Выход")
        choice = input(f"{C.BOLD}Выбор:{C.RESET} ").strip()
        
        if choice == "1":
            run_session(engine)
        elif choice == "2":
            print("Выход...")
            break


if __name__ == "__main__":
    main()