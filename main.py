import os
import time
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# ============ НАСТРОЙКИ (из переменных окружения Render) ============
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ai_boty_kz_token")
INSTAGRAM_BUSINESS_ID = os.environ.get("INSTAGRAM_BUSINESS_ID")

GRAPH_API_URL = "https://graph.facebook.com/v19.0"

# ============ ПАМЯТЬ КЛИЕНТОВ (в оперативке) ============
user_memory = {}

SYSTEM_PROMPT = """Ты — AI-менеджер Instagram-аккаунта @ai_boty_kz.

Твоя задача:
- Вежливо приветствовать, знакомиться
- Узнать: имя, чем занимается, город
- Рассказать, что мы делаем AI-ботов для бизнеса (как живой менеджер, 24/7)
- НЕ называть цены — говори: "Стоимость зависит от задачи, давайте обсудим"
- НЕ выдумывать услуги, которых нет
- В конце вести клиента в Telegram: @Evgeniy_Assistant_bot
- Отвечай коротко (2-4 предложения), дружелюбно, с эмодзи
- Если клиент готов — дай ссылку: https://t.me/Evgeniy_Assistant_bot
"""

# ============ ОЧЕРЕДЬ ПОСТОВ (сюда добавляй свои Reels и фото) ============
REELS_QUEUE = [
    # Пример:
    # {"type": "reel", "url": "https://твой-сайт/video1.mp4", "caption": "Текст поста #хэштеги"},
    # {"type": "photo", "url": "https://твой-сайт/photo1.jpg", "caption": "Текст поста #хэштеги"},
]

current_post_index = 0

# ============ ГЛАВНАЯ ============
@app.route("/", methods=["GET"])
def home():
    return "Instagram AI Bot is running!", 200

# ============ ВЕРИФИКАЦИЯ ВЕБХУКА ============
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

# ============ ОБРАБОТКА СООБЩЕНИЙ ============
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    print("Incoming webhook data:", data)

    try:
        if data.get("object") == "instagram":
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    if "message" in messaging and "text" in messaging["message"]:
                        sender_id = messaging["sender"]["id"]
                        message_text = messaging["message"]["text"]

                        # Игнорируем эхо
                        if messaging["message"].get("is_echo"):
                            return "EVENT_RECEIVED", 200

                        ai_response = ask_groq(sender_id, message_text)
                        send_instagram_message(sender_id, ai_response)

        return "EVENT_RECEIVED", 200
    except Exception as e:
        print(f"Error handling webhook: {e}")
        return "EVENT_RECEIVED", 200

# ============ ЗАПРОС К GROQ ============
def ask_groq(sender_id, message_text):
    if sender_id not in user_memory:
        user_memory[sender_id] = []

    user_memory[sender_id].append({"role": "user", "content": message_text})
    history = user_memory[sender_id][-10:]  # последние 10 сообщений

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        ai_text = res_data["choices"][0]["message"]["content"]
        user_memory[sender_id].append({"role": "assistant", "content": ai_text})
        return ai_text
    except Exception as e:
        print(f"Groq error: {e}")
        return "Извините, сейчас не могу ответить, попробуйте позже."

# ============ ОТПРАВКА СООБЩЕНИЯ В INSTAGRAM ============
def send_instagram_message(recipient_id, text_message):
    url = f"{GRAPH_API_URL}/me/messages"
    params = {"access_token": META_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text_message}
    }
    try:
        response = requests.post(url, params=params, json=payload)
        print("Send message response:", response.json())
    except Exception as e:
        print(f"Send error: {e}")

# ============ ПУБЛИКАЦИЯ REELS ============
def publish_reel(video_url, caption):
    create_url = f"{GRAPH_API_URL}/{INSTAGRAM_BUSINESS_ID}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": META_ACCESS_TOKEN
    }
    r = requests.post(create_url, params=params)
    creation_id = r.json().get("id")
    print("Reel container:", r.json())

    if not creation_id:
        return False

    # Ждём обработки видео
    for _ in range(20):
        status_url = f"{GRAPH_API_URL}/{creation_id}"
        status_params = {"fields": "status_code", "access_token": META_ACCESS_TOKEN}
        status = requests.get(status_url, params=status_params).json()
        print("Reel status:", status)
        if status.get("status_code") == "FINISHED":
            break
        time.sleep(10)

    publish_url = f"{GRAPH_API_URL}/{INSTAGRAM_BUSINESS_ID}/media_publish"
    pub_params = {"creation_id": creation_id, "access_token": META_ACCESS_TOKEN}
    result = requests.post(publish_url, params=pub_params)
    print("Publish result:", result.json())
    return result.json().get("id") is not None

# ============ ПУБЛИКАЦИЯ ФОТО ============
def publish_photo(image_url, caption):
    create_url = f"{GRAPH_API_URL}/{INSTAGRAM_BUSINESS_ID}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": META_ACCESS_TOKEN
    }
    r = requests.post(create_url, params=params)
    creation_id = r.json().get("id")
    if not creation_id:
        return False

    publish_url = f"{GRAPH_API_URL}/{INSTAGRAM_BUSINESS_ID}/media_publish"
    pub_params = {"creation_id": creation_id, "access_token": META_ACCESS_TOKEN}
    result = requests.post(publish_url, params=pub_params)
    print("Publish result:", result.json())
    return result.json().get("id") is not None

# ============ ЭНДПОИНТ ДЛЯ АВТОПОСТИНГА (вызывать через cron-job.org) ============
@app.route("/publish", methods=["GET", "POST"])
def publish_next():
    global current_post_index
    if not REELS_QUEUE:
        return "Очередь пуста", 200

    item = REELS_QUEUE[current_post_index % len(REELS_QUEUE)]
    current_post_index += 1

    if item["type"] == "reel":
        publish_reel(item["url"], item["caption"])
    elif item["type"] == "photo":
        publish_photo(item["url"], item["caption"])

    return "Опубликовано", 200

# ============ РАЗДАЧА ВИДЕО ИЗ ПАПКИ videos (если нужно) ============
@app.route("/videos/<filename>")
def serve_video(filename):
    return send_from_directory("videos", filename)

# ============ ЗАПУСК ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
