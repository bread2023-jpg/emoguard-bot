import asyncio
import os
import random
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (без load_dotenv - в Railway он не нужен!) ===
TOKEN = os.environ.get('BOT_TOKEN')
YANDEX_API_KEY = os.environ.get('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.environ.get('YANDEX_FOLDER_ID')

if not TOKEN:
    print(" ОШИБКА: BOT_TOKEN не задан в переменных окружения Railway!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === YANDEXGPT API (вместо Ollama!) ===
SYSTEM_PROMPT = "Ты — EmoGuard, эмпатичный ИИ-помощник по психологии. Выслушивай с теплом, задавай вопросы, предлагай техники. Не ставь диагнозы."

def call_yandexgpt(messages):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "x-folder-id": YANDEX_FOLDER_ID
    }
    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite/latest",
        "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": "1000"},
        "messages": messages
    }
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    if "result" in result and "alternatives" in result["result"]:
        return result["result"]["alternatives"][0]["message"]["text"]
    return "😔 Проблема с ответом. Попробуй ещё раз."

# === КРИЗИСНЫЕ ТРИГГЕРЫ ===
CRISIS_KEYWORDS = ["суицид", "самоубийство", "убить себя", "не хочу жить", "покончить с собой"]
def check_crisis_level(text):
    text_lower = text.lower()
    for keyword in CRISIS_KEYWORDS:
        if keyword in text_lower:
            return 2
    return 0

def get_crisis_response(level):
    return "⚠️ <b>Я вижу, что тебе очень плохо.</b>\n\nПожалуйста, позвони:\n📞 8-800-2000-122\n🚑 112\n\nТы не один! 💙"

# === КЛАВИАТУРА ===
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😊 Как я себя чувствую?", callback_data="mood")],
    [InlineKeyboardButton(text="🧘 Техники", callback_data="techniques")],
    [InlineKeyboardButton(text=" Настроение", callback_data="mood_stats")]
])

# === ОБРАБОТЧИКИ ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(f"👋 Привет! Я EmoGuard \n\nПросто напиши мне или выбери кнопку.", reply_markup=main_keyboard)

@dp.callback_query(F.data == "mood")
async def process_mood(callback_query: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😄 Отлично", callback_data="mood_")],
        [InlineKeyboardButton(text="😢 Грустно", callback_data="mood_😢")]
    ])
    await callback_query.message.answer("Как ты себя чувствуешь?", reply_markup=kb)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("mood_"))
async def process_mood_selection(callback_query: types.CallbackQuery):
    mood = callback_query.data.split("_", 1)[1]
    db.log_mood(callback_query.from_user.id, mood)
    await callback_query.message.answer(f"Записал: {mood} 💙")
    await callback_query.answer()

@dp.callback_query(F.data == "techniques")
async def process_techniques_button(callback_query: types.CallbackQuery):
    await callback_query.message.answer("🧘 Попробуй:\n• /breathing — Дыхание\n• /grounding — Заземление")
    await callback_query.answer()

@dp.callback_query(F.data == "mood_stats")
async def process_mood_stats(callback_query: types.CallbackQuery):
    stats = db.get_mood_stats(callback_query.from_user.id, days=7)
    if not stats:
        await callback_query.message.answer("📊 Пока нет данных")
    else:
        text = "📊 <b>За 7 дней:</b>\n" + "\n".join([f"{r['mood']}: {r['count']} раз" for r in stats])
        await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

# === ГЛАВНЫЙ ОБРАБОТЧИК ===
@dp.message()
async def chat_handler(message: types.Message):
    if message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    if check_crisis_level(message.text) > 0:
        await message.answer(get_crisis_response(2), parse_mode="HTML")
        return
    
    db.save_message(user_id, "user", message.text)
    history = db.get_recent_messages(user_id, limit=10)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": m["role"], "content": m["content"]} for m in history]
    
    status_msg = await message.answer("🧠 Думаю...")
    try:
        ai_response = call_yandexgpt(messages)  # YandexGPT вместо Ollama!
        db.save_message(user_id, "assistant", ai_response)
        await status_msg.delete()
        await message.answer(ai_response)
    except Exception as e:
        print(f"Ошибка: {e}")
        await status_msg.edit_text(" Проблема. Попробуй ещё раз.")

async def main():
    print("✅ База данных инициализирована")
    print("🛡️ EmoGuard запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
