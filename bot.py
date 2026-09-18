import asyncio
import os
import random
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем наши модули
from subscription import cmd_subscription, process_buy_premium, process_pre_checkout, process_successful_payment, check_message_limit
import database as db

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
TOKEN = os.environ.get('BOT_TOKEN')
YANDEX_API_KEY = os.environ.get('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.environ.get('YANDEX_FOLDER_ID')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === КРИЗИСНЫЕ ТРИГГЕРЫ ===
CRISIS_KEYWORDS = ["суицид", "самоубийство", "убить себя", "не хочу жить", "покончить с собой", "свести счеты с жизнью", "конец всему", "лучше бы не родился", "хочу умереть", "жизнь не имеет смысла", "всё бессмысленно", "никто не поймёт", "я никому не нужен"]
SOFT_CRISIS_KEYWORDS = ["очень плохо", "невыносимо", "больно жить", "устал жить", "нет сил", "всё надоело", "хочется исчезнуть", "лучше бы меня не было"]

def check_crisis_level(text):
    text_lower = text.lower()
    for keyword in CRISIS_KEYWORDS:
        if keyword in text_lower: return 2
    for keyword in SOFT_CRISIS_KEYWORDS:
        if keyword in text_lower: return 1
    return 0

def get_crisis_response(level):
    if level == 2:
        return "⚠️ <b>Я вижу, что тебе очень плохо.</b>\n\nПожалуйста, прямо сейчас обратись за помощью:\n📞 <b>Телефон доверия:</b> 8-800-2000-122\n🚑 <b>Экстренные службы:</b> 112 или 103\n\nТы не один. Твоя жизнь важна 💙"
    return "💙 <b>Я слышу, что тебе тяжело.</b>\n\nЕсли тебе очень плохо, пожалуйста, поговори с кем-то:\n📞 Телефон доверия: 8-800-2000-122\n🚑 Экстренная помощь: 112\n\nА я здесь, чтобы выслушать."

# === YANDEXGPT API (Вместо Ollama!) ===
SYSTEM_PROMPT = "Ты — EmoGuard, эмпатичный ИИ-помощник по психологии. Выслушивай с теплом, задавай мягкие вопросы, предлагай техники КПТ. Не ставь диагнозы. Отвечай кратко (2-3 абзаца), тепло и поддерживающе."

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
    return "😔 Извини, у меня возникла проблема с ответом. Попробуй ещё раз."

# === ТЕХНИКИ ===
TECHNIQUES = {
    "breathing": {"name": "🌬️ Дыхание 4-7-8", "description": "1️⃣ Вдох на 4 счёта\n2️⃣ Задержка на 7\n3️⃣ Выдох на 8\nПовтори 4 раза."},
    "grounding": {"name": "🌍 Заземление 5-4-3-2-1", "description": "Найди: 5 вещей, которые видишь, 4 звука, 3 ощущения, 2 запаха, 1 вкус."}
}

main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😊 Как я себя чувствую?", callback_data="mood")],
    [InlineKeyboardButton(text="🧘 Техники", callback_data="techniques")],
    [InlineKeyboardButton(text="📊 Настроение", callback_data="mood_stats")],
    [InlineKeyboardButton(text="🆘 Помощь", callback_data="crisis")]
])

# === ОБРАБОТЧИКИ ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(f"👋 Привет, <b>{message.from_user.first_name or 'друг'}</b>! Я EmoGuard 💙\n\nВыбери, что нужно, или просто напиши мне.", parse_mode="HTML", reply_markup=main_keyboard)

@dp.message(Command("subscription"))
async def cmd_sub(message: types.Message):
    await cmd_subscription(message, bot)

@dp.callback_query(F.data == "buy_premium")
async def buy_premium_callback(callback_query: types.CallbackQuery):
    await process_buy_premium(callback_query, bot)

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query):
    await process_pre_checkout(pre_checkout_query, bot)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    await process_successful_payment(message, bot)

@dp.callback_query(F.data == "check_limits")
async def check_limits_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    count = db.get_daily_message_count(user_id)
    if db.is_premium(user_id):
        text = "⭐ <b>Premium</b>\n\nСообщений сегодня: безлимит"
    else:
        text = f"📊 <b>Бесплатный тариф</b>\n\nИспользовано: {count}/10\nОсталось: {max(0, 10 - count)}"
    await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(F.data == "mood")
async def process_mood(callback_query: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😄 Отлично", callback_data="mood_😄")],
        [InlineKeyboardButton(text="😢 Грустно", callback_data="mood_😢")],
        [InlineKeyboardButton(text="😰 Тревожно", callback_data="mood_😰")]
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
    text = "<b>Техники:</b>\n• /breathing — Дыхание\n• /grounding — Заземление"
    await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(F.data == "crisis")
async def process_crisis(callback_query: types.CallbackQuery):
    await callback_query.message.answer("📞 Телефон доверия: 8-800-2000-122\n🚑 Экстренные службы: 112", parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(F.data == "mood_stats")
async def process_mood_stats(callback_query: types.CallbackQuery):
    stats = db.get_mood_stats(callback_query.from_user.id, days=7)
    if not stats:
        await callback_query.message.answer("📊 Пока нет данных. Используй кнопку 'Как я себя чувствую?'")
    else:
        text = "📊 <b>За 7 дней:</b>\n" + "\n".join([f"{r['mood']}: {r['count']} раз" for r in stats])
        await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

# === ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ (ЗДЕСЬ РАБОТАЕТ YANDEXGPT) ===
@dp.message()
async def chat_handler(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text
    
    if user_text.startswith('/'):
        return
    
    # 1. ПРОВЕРКА ЛИМИТА
    can_send, _ = check_message_limit(user_id)
    if not can_send:
        await message.answer("⚠️ <b>Лимит исчерпан</b>\n\nИспользовано 10/10 сообщений сегодня.\nОформи Premium: /subscription", parse_mode="HTML")
        return

    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # 2. КРИЗИС
    if check_crisis_level(user_text) > 0:
        await message.answer(get_crisis_response(check_crisis_level(user_text)), parse_mode="HTML")
        db.save_message(user_id, "user", user_text)
        return
    
    # 3. YANDEXGPT
    db.save_message(user_id, "user", user_text)
    history = db.get_recent_messages(user_id, limit=10)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": m["role"], "content": m["content"]} for m in history]
    
    status_msg = await message.answer("🧠 Думаю...")
    try:
        ai_response = call_yandexgpt(messages) # <-- ВОТ ОНА, РАБОЧАЯ ФУНКЦИЯ ЯНДЕКСА!
        db.save_message(user_id, "assistant", ai_response)
        await status_msg.delete()
        await message.answer(ai_response)
    except Exception as e:
        print(f"Ошибка YandexGPT: {e}")
        await status_msg.edit_text("😔 Проблема. Попробуй ещё раз.")

async def main():
    print("✅ База данных инициализирована")
    print("🛡️ EmoGuard запущен с YandexGPT и лимитами!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
