import os
import requests
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ai_boty_kz_token")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

@app.route("/", methods=["GET"])
def home():
    return "Instagram AI Bot is running!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    try:
        if data.get("object") == "instagram":
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    sender_id = messaging.get("sender", {}).get("id")
                    message_text = messaging.get("message", {}).get("text")

                    if sender_id and message_text:
                        ai_reply = generate_ai_response(message_text)
                        send_instagram_message(sender_id, ai_reply)
    except Exception as e:
        print("Error:", e)
    return jsonify({"status": "ok"}), 200

def generate_ai_response(prompt):
    if not groq_client:
        return "AI is not configured."
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Ты вежливый ИИ-ассистент для Instagram-аккаунта @ai_boty_kz."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print("Groq error:", e)
        return "Извините, сервис временно занят."

def send_instagram_message(recipient_id, text):
    url = f"https://graph.facebook.com/v18.0/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "access_token": META_ACCESS_TOKEN
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
