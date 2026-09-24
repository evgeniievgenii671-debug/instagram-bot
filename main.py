import requests

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    print("Incoming webhook data:", data)

    try:
        # Проверяем, что это сообщение из Instagram
        if data.get("object") == "instagram":
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    # Проверяем наличие текста сообщения и что оно от пользователя (а не от самого бота)
                    if "message" in messaging and "text" in messaging["message"]:
                        sender_id = messaging["sender"]["id"]
                        message_text = messaging["message"]["text"]
                        
                        # Не отвечаем сами себе
                        if "is_echo" in messaging["message"] and messaging["message"]["is_echo"]:
                            return "EVENT_RECEIVED", 200

                        # 1. Получаем ответ от Groq API
                        ai_response = ask_groq(message_text)

                        # 2. Отправляем ответ пользователю в Instagram
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
        "model": "llama-3.3-70b-versatile", # или другая модель Groq по вашему выбору
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
    url = f"https://graph.facebook.com/v18.0/me/messages"
    params = {
        "access_token": META_ACCESS_TOKEN
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text_message}
    }
    response = requests.post(url, params=params, json=payload)
    print("Send message response:", response.json())
