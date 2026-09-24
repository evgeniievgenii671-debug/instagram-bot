import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Загружаем ключи из переменных окружения Render
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ai_boty_kz_token")

@app.route("/", methods=["GET"])
def home():
    return "Instagram AI Bot is running!", 200

# 1. Верификация вебхука от Meta (GET)
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Verification failed", 403
    return "Hello, this is webhook endpoint!", 200

# 2. Обработка входящих сообщений и интеграция с Groq (POST)
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    print("Incoming webhook data:", data)

    try:
        if data.get("object") == "instagram":
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    # Проверяем текст сообщения от пользователя
                    if "message" in messaging and "text" in messaging["message"]:
                        sender_id = messaging["sender"]["id"]
                        message_text = messaging["message"]["text"]
                        
                        # Игнорируем эхо-сообщения (отправленные самим ботом)
                        if "is_echo" in messaging["message"] and messaging["message"]["is_echo"]:
                            return "EVENT_RECEIVED", 200

                        # Получаем ответ от Groq API
                        ai_response = ask_groq(message_text)

                        # Отправляем ответ пользователю в Instagram
                        send_instagram_message(sender_id, ai_response)

        return "EVENT_RECEIVED", 200
    except Exception as e:
        print(f"Error handling webhook: {e}")
        return "EVENT_RECEIVED", 200

def ask_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Ты полезный AI-ассистент для Instagram-аккаунта @ai_boty_kz. Отвечай вежливо, кратко и по делу."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        return res_data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq API error: {e}")
        return "Извините, сейчас не могу ответить, попробуйте позже."

def send_instagram_message(recipient_id, text_message):
    url = "https://graph.facebook.com/v19.0/me/messages"
    params = {
        "access_token": META_ACCESS_TOKEN
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text_message}
    }
    response = requests.post(url, params=params, json=payload)
    print("Send message response:", response.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
