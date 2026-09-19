import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import OpenAI
import database as db

# === ПЕРЕМЕННЫЕ ===
TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

if not TOKEN:
    print("❌ BOT_TOKEN не задан!")
    exit(1)
if not OPENROUTER_API_KEY:
    print("❌ OPENROUTER_API_KEY не задан!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === OPENROUTER (БЕЗ ПРОКСИ!) ===
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

SYSTEM_PROMPT = "Ты — EmoGuard, эмпатичный ИИ-помощник. Поддерживай, задавай вопросы, предлагай техники. Не ставь диагнозы."

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
        print(f"Ошибка: {e}")
        return "😔 Проблема. Попробуй ещё раз."

# === КРИЗИС ===
CRISIS = ["суицид", "самоубийство", "убить себя", "не хочу жить"]
def check_crisis(text):
    return any(kw in text.lower() for kw in CRISIS)

def crisis_response():
    return "⚠️ <b>Позвони:</b>\n📞 8-800-2000-122\n🚑 112\n\nТы не один! 💙"

# === КЛАВИАТУРА ===
kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😊 Настроение", callback_data="mood")],
    [InlineKeyboardButton(text="🧘 Техники", callback_data="techniques")]
])

# === ОБРАБОТЧИКИ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(f"👋 Привет! Я EmoGuard 💙\n\nНапиши мне или выбери кнопку.", reply_markup=kb)

@dp.callback_query(F.data == "mood")
async def mood(callback_query: types.CallbackQuery):
    k = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="", callback_data="mood_😄")],
        [InlineKeyboardButton(text="😢", callback_data="mood_")]
    ])
    await callback_query.message.answer("Как ты?", reply_markup=k)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("mood_"))
async def mood_sel(callback_query: types.CallbackQuery):
    mood = callback_query.data.split("_", 1)[1]
    db.log_mood(callback_query.from_user.id, mood)
    await callback_query.message.answer(f"Записал: {mood} 💙")
    await callback_query.answer()

@dp.callback_query(F.data == "techniques")
async def tech(callback_query: types.CallbackQuery):
    await callback_query.message.answer("🧘 Попробуй:\n• /breathing\n• /grounding")
    await callback_query.answer()

# === ГЛАВНЫЙ ОБРАБОТЧИК ===
@dp.message()
async def chat(message: types.Message):
    if message.text.startswith('/'):
        return
    
    uid = message.from_user.id
    db.add_user(uid, message.from_user.username, message.from_user.first_name)
    
    if check_crisis(message.text):
        await message.answer(crisis_response(), parse_mode="HTML")
        return
    
    db.save_message(uid, "user", message.text)
    history = db.get_recent_messages(uid, limit=10)
    
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history:
        msgs.append({"role": m["role"], "content": m["content"]})
    
    status = await message.answer("🧠 Думаю...")
    
    try:
        answer = call_ai(msgs)
        db.save_message(uid, "assistant", answer)
        await status.delete()
        await message.answer(answer)
    except:
        await status.edit_text("😔 Проблема.")

async def main():
    print("✅ База готова")
    print("🛡️ EmoGuard запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
