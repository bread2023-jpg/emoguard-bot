import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import OpenAI
import database as db

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не задан!")
    exit(1)
if not OPENROUTER_API_KEY:
    print("❌ ОШИБКА: OPENROUTER_API_KEY не задан!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === OPENROUTER API (БЕЗ ПРОКСИ!) ===
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

SYSTEM_PROMPT = """Ты — EmoGuard, эмпатичный ИИ-помощник по психологии.
Выслушивай с теплом, задавай вопросы, предлагай техники. Не ставь диагнозы.
Отвечай кратко (2-3 абзаца), поддерживающе."""

def call_ai(messages):
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct:free",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка OpenRouter: {e}")
        return "😔 Проблема с ответом. Попробуй ещё раз."

# === КРИЗИС ===
CRISIS_KEYWORDS = ["суицид", "самоубийство", "убить себя", "не хочу жить", "покончить с собой"]
def check_crisis(text):
    return any(kw in text.lower() for kw in CRISIS_KEYWORDS)

def get_crisis_response():
    return "⚠️ <b>Я вижу, что тебе очень плохо.</b>\n\nПожалуйста, позвони:\n📞 8-800-2000-122\n🚑 112\n\nТы не один! 💙"

# === КЛАВИАТУРА ===
main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😊 Настроение", callback_data="mood")],
    [InlineKeyboardButton(text="🧘 Техники", callback_data="techniques")]
])

# === ОБРАБОТЧИКИ ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(f"👋 Привет! Я EmoGuard 💙\n\nПросто напиши мне или выбери кнопку.", reply_markup=main_kb)

@dp.callback_query(F.data == "mood")
async def process_mood(callback_query: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="", callback_data="mood_😄")],
        [InlineKeyboardButton(text="😢", callback_data="mood_😢")]
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
    await callback_query.message.answer("🧘 Попробуй:\n• /breathing\n• /grounding")
    await callback_query.answer()

# === ГЛАВНЫЙ ОБРАБОТЧИК ===
@dp.message()
async def chat_handler(message: types.Message):
    if message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    if check_crisis(message.text):
        await message.answer(get_crisis_response(), parse_mode="HTML")
        return
    
    db.save_message(user_id, "user", message.text)
    history = db.get_recent_messages(user_id, limit=10)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    status_msg = await message.answer("🧠 Думаю...")
    
    try:
        ai_response = call_ai(messages)  # OpenRouter БЕЗ прокси!
        db.save_message(user_id, "assistant", ai_response)
        await status_msg.delete()
        await message.answer(ai_response)
    except Exception as e:
        print(f"Ошибка: {e}")
        await status_msg.edit_text("😔 Проблема. Попробуй ещё раз.")

async def main():
    print("✅ База данных инициализирована")
    print("🛡️ EmoGuard запущен с OpenRouter!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
