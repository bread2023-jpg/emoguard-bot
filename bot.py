import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from dotenv import load_dotenv
import ollama
import database as db
from mood_chart import generate_mood_chart

# === КРИЗИСНЫЕ ТРИГГЕРЫ ===
CRISIS_KEYWORDS = [
    "суицид", "самоубийство", "убить себя", "не хочу жить", "покончить с собой",
    "свести счеты с жизнью", "конец всему", "лучше бы не родился", "хочу умереть",
    "жизнь не имеет смысла", "всё бессмысленно", "никто не поймёт", "я никому не нужен"
]

SOFT_CRISIS_KEYWORDS = [
    "очень плохо", "невыносимо", "больно жить", "устал жить", "нет сил",
    "всё надоело", "хочется исчезнуть", "лучше бы меня не было"
]

def check_crisis_level(text):
    text_lower = text.lower()
    for keyword in CRISIS_KEYWORDS:
        if keyword in text_lower:
            return 2
    for keyword in SOFT_CRISIS_KEYWORDS:
        if keyword in text_lower:
            return 1
    return 0

def get_crisis_response(level):
    if level == 2:
        return (
            "⚠️ <b>Я вижу, что тебе очень плохо.</b>\n\n"
            "Пожалуйста, прямо сейчас обратись за помощью:\n\n"
            "📞 <b>Телефон доверия (круглосуточно, бесплатно):</b>\n"
            "• 8-800-2000-122 (для детей и подростков)\n"
            "• 8-800-333-44-34 (для взрослых)\n\n"
            "🚑 <b>Экстренные службы:</b>\n"
            "• 112 — с мобильного (бесплатно)\n"
            "• 103 — скорая помощь\n\n"
            "Ты не один. Пожалуйста, позвони. Твоя жизнь важна 💙"
        )
    else:
        return (
            "💙 <b>Я слышу, что тебе тяжело.</b>\n\n"
            "Если тебе очень плохо, пожалуйста, поговори с кем-то:\n\n"
            "📞 Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)\n"
            "🚑 Экстренная помощь: 112\n\n"
            "А я здесь, чтобы выслушать. Расскажи, что происходит?"
        )

# Загружаем токен
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyConnector

# Создаём сессию с прокси
connector = ProxyConnector.from_url("socks5://логин:пароль@хост:порт")
session = AiohttpSession(connector=connector)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

# === УЛУЧШЕННЫЙ ПРОМПТ ===
SYSTEM_PROMPT = """Ты — EmoGuard, эмпатичный и профессиональный ИИ-помощник по психологии.

ОСНОВНЫЕ ПРИНЦИПЫ:
• Выслушивай с теплом, эмпатией и без осуждения
• Задавай мягкие уточняющие вопросы
• Помогай разобраться в чувствах методами КПТ
• Предлагай практические техники (дыхание, заземление, рефрейминг)
• Никогда не ставь диагнозы и не заменяй врача
• При упоминании суицида/самоповреждения — мягко направляй к специалисту

СТИЛЬ ОТВЕТОВ:
• Отвечай на русском языке
• Кратко (2-4 абзаца)
• Тепло, поддерживающе, без токсичной позитивности
• Эмодзи — умеренно и к месту
• Избегай клише вроде "всё будет хорошо"

ПРИМЕРЫ ХОРОШИХ ОТВЕТОВ:

Пользователь: "Мне тревожно перед экзаменом"
EmoGuard: "Понимаю, тревога перед важным событием — это нормально. Давай разберёмся: что именно тебя беспокоит больше всего? 

А пока попробуй технику дыхания 4-7-8: вдох на 4 счёта, задержка на 7, выдох на 8. Это быстро снизит физическое напряжение. 💙"

Пользователь: "Я ни на что не способен"
EmoGuard: "Мне жаль, что ты так себя чувствуешь. Такие мысли часто приходят, когда мы устаём. Но давай проверим: это абсолютный факт или твоё текущее состояние?

Вспомни хотя бы одну ситуацию, где ты справился — даже маленькую. Наши мысли часто преувеличивают негатив. Расскажи, что произошло?"

Пользователь: "Не могу уснуть, мысли лезут в голову"
EmoGuard: "Бессонница из-за мыслей — очень распространённая проблема. Попробуй технику 'выгрузки мозга': выпиши всё, что крутится в голове. Не редактируй, просто вылей.

Ещё помогает сканирование тела: начни с макушки и медленно 'пройдись' вниманием вниз, расслабляя каждую зону. Хочешь, я проведу тебя через эту технику? 🌙"""

# === БАЗА ТЕХНИК ===
TECHNIQUES = {
    "breathing": {
        "name": "🌬️ Дыхание 4-7-8",
        "description": "<b>Дыхательная техника для быстрого успокоения</b>\n\n1️⃣ Сядь удобно, спина прямая\n2️ Вдох через нос на <b>4 счёта</b>\n3️⃣ Задержка дыхания на <b>7 счетов</b>\n4️⃣ Медленный выдох через рот на <b>8 счетов</b>\n\nПовтори 4-6 циклов. Активирует парасимпатическую нервную систему."
    },
    "grounding": {
        "name": "🌍 Заземление 5-4-3-2-1",
        "description": "<b>Техника при сильной тревоге или панике</b>\n\nНайди вокруг:\n️ <b>5 вещей</b>, которые видишь\n👂 <b>4 звука</b>, которые слышишь\n✋ <b>3 ощущения</b> в теле\n👃 <b>2 запаха</b>\n👅 <b>1 вкус</b>\n\nЭто возвращает в настоящий момент."
    },
    "pmr": {
        "name": "💪 Прогрессивная мышечная релаксация",
        "description": "<b>Расслабление через напряжение мышц</b>\n\n1️⃣ Напряги мышцы стоп на <b>5 секунд</b>\n2️⃣ Резко расслабь на <b>10 секунд</b>\n3️⃣ Поднимайся: икры → бёдра → живот → руки → плечи → лицо\n\nСнимает физическое напряжение и тревогу."
    },
    "safe_place": {
        "name": "🏝️ Безопасное место",
        "description": "<b>Визуализация для успокоения</b>\n\n1️⃣ Закрой глаза, сделай глубокие вдохи\n2️⃣ Представь место, где <b>абсолютно безопасно</b>\n3️⃣ Детализируй: звуки, запахи, ощущения\n4️ Побудь там 2-3 минуты\n\nЭто место всегда с тобой."
    },
    "gratitude": {
        "name": "📔 Дневник благодарности",
        "description": "<b>Смещение фокуса на позитив</b>\n\nНапиши <b>3 вещи</b>, за которые благодарен сегодня:\n1. ...\n2. ...\n3. ...\n\nДаже маленькие: вкусный кофе, улыбка, тёплая одежда. Практикуй каждый вечер — через 2 недели заметишь изменения."
    },
    "reframing": {
        "name": "🔄 Когнитивный рефрейминг",
        "description": "<b>Переосмысление негативных мыслей</b>\n\n1️ Запиши мысль: <i>\"Я провалился\"</i>\n2️⃣ Спроси: <b>Это факт или интерпретация?</b>\n3️⃣ Найди альтернативу:\n   • <i>\"Я нервничал, но донёс идею\"</i>\n   • <i>\"Это опыт для роста\"</i>\n\nМысли — не факты. Их можно менять."
    },
    "five_minutes": {
        "name": "⏱️ Правило 5 минут",
        "description": "<b>Борьба с прокрастинацией</b>\n\n1️⃣ Скажи: <b>\"Я позанимаюсь этим 5 минут\"</b>\n2️⃣ Поставь таймер\n3️⃣ Начни делать\n4️⃣ Через 5 минут разреши остановиться\n\nЧаще всего ты продолжишь — самое сложное это начать."
    },
    "body_scan": {
        "name": "🧘 Сканирование тела",
        "description": "<b>Осознанность и расслабление</b>\n\n1️⃣ Ляг удобно, закрой глаза\n2️ Начни с макушки: почувствуй эту область\n3️⃣ Двигайся вниз: лицо → шея → плечи → руки → грудь → живот → ноги\n4️⃣ Расслабляй зоны напряжения\n\n5-10 минут. Отлично перед сном."
    }
}

# === КЛАВИАТУРЫ ===
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😊 Как я себя чувствую?", callback_data="mood")],
    [InlineKeyboardButton(text="🧘 Техники самопомощи", callback_data="techniques")],
    [InlineKeyboardButton(text=" Моё настроение", callback_data="mood_stats")],
    [InlineKeyboardButton(text=" Экстренная помощь", callback_data="crisis")],
])

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def show_techniques_list(message):
    text = "<b>🧘 Техники самопомощи</b>\n\nВыбери технику:\n\n"
    for key, technique in TECHNIQUES.items():
        text += f"• /{key} — {technique['name']}\n"
    text += "\nИли нажми кнопку для случайной техники 🎲"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Случайная техника", callback_data="random_technique")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# === ОБРАБОТЧИКИ КОМАНД ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Регистрируем пользователя в БД
    db.add_user(user_id, username, first_name)
    
    text = (
        f"👋 Привет, <b>{first_name or 'друг'}</b>! Я <b>EmoGuard</b> — твой ИИ-помощник по эмоциональному здоровью.\n\n"
        "⚠️ <b>Важно:</b> я ИИ, а не врач. Мои ответы поддерживают, но не заменяют терапию.\n\n"
        "Теперь я запоминаю наши разговоры и твоё настроение. Выбери, что нужно, или просто напиши 💙"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    msg_count = db.get_message_count(message.from_user.id)
    text = (
        "📖 <b>Возможности EmoGuard:</b>\n\n"
        "• 💬 Выслушать и поддержать\n"
        "•  Предложить техники самопомощи\n"
        "• 📊 Отслеживать твоё настроение\n"
        "• 🔄 Очищать историю (/reset)\n\n"
        f"📝 Ты отправил сообщений: <b>{msg_count}</b>\n\n"
        "🔒 Всё хранится локально на твоём устройстве."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)

@dp.message(Command("mood"))
async def cmd_mood(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😄 Отлично", callback_data="mood_😄")],
        [InlineKeyboardButton(text="🙂 Нормально", callback_data="mood_🙂")],
        [InlineKeyboardButton(text="😐 Так себе", callback_data="mood_😐")],
        [InlineKeyboardButton(text="😢 Грустно", callback_data="mood_😢")],
        [InlineKeyboardButton(text="😰 Тревожно", callback_data="mood_😰")],
        [InlineKeyboardButton(text="😡 Злюсь", callback_data="mood_😡")],
    ])
    text = "😊 <b>Как ты себя чувствуешь прямо сейчас?</b>\n\nВыбери эмоцию или опиши словами:"
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("techniques"))
async def cmd_techniques_list(message: types.Message):
    await show_techniques_list(message)

@dp.message(Command("crisis"))
async def cmd_crisis(message: types.Message):
    text = (
        "⚠️ <b>Экстренная помощь</b>\n\n"
        "Если ты в кризисе, обратись к специалистам:\n\n"
        "📞 <b>Телефон доверия (Россия):</b>\n"
        "• 8-800-2000-122 (дети и подростки)\n"
        "• 8-800-333-44-34 (взрослые)\n\n"
        "🚑 <b>Экстренные службы:</b>\n"
        "• 112 — единый номер\n"
        "• 103 — скорая помощь"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показывает статистику настроения"""
    user_id = message.from_user.id
    stats = db.get_mood_stats(user_id, days=7)
    
    if not stats:
        await message.answer(
            "📊 <b>Статистика пуста</b>\n\n"
            "Ты ещё не отмечал своё настроение. Используй команду /mood, чтобы начать!",
            parse_mode="HTML"
        )
        return
    
    text = "📊 <b>Твоё настроение за последние 7 дней:</b>\n\n"
    total = sum(row["count"] for row in stats)
    
    for row in stats:
        mood = row["mood"]
        count = row["count"]
        percentage = int((count / total) * 100)
        bar = "█" * (percentage // 5)
        text += f"{mood} <b>{count} раз</b> ({percentage}%)\n{bar}\n\n"
    
    # Генерируем график
    history = db.get_mood_history(user_id, days=7)
    chart_path = generate_mood_chart(user_id, history)
    
    if chart_path and os.path.exists(chart_path):
        photo = FSInputFile(chart_path)
        await message.answer_photo(photo, caption=text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    deleted = db.clear_user_history(user_id)
    
    text = (
        f"🔄 <b>История очищена</b>\n\n"
        f"Удалено сообщений: {deleted}\n"
        "Начнём с чистого листа? 💙"
    )
    await message.answer(text, parse_mode="HTML")

# Команды для отдельных техник
@dp.message(Command("breathing"))
async def cmd_technique_breathing(message: types.Message):
    await message.answer(TECHNIQUES["breathing"]["description"], parse_mode="HTML")

@dp.message(Command("grounding"))
async def cmd_technique_grounding(message: types.Message):
    await message.answer(TECHNIQUES["grounding"]["description"], parse_mode="HTML")

@dp.message(Command("pmr"))
async def cmd_technique_pmr(message: types.Message):
    await message.answer(TECHNIQUES["pmr"]["description"], parse_mode="HTML")

@dp.message(Command("safe_place"))
async def cmd_technique_safe_place(message: types.Message):
    await message.answer(TECHNIQUES["safe_place"]["description"], parse_mode="HTML")

@dp.message(Command("gratitude"))
async def cmd_technique_gratitude(message: types.Message):
    await message.answer(TECHNIQUES["gratitude"]["description"], parse_mode="HTML")

@dp.message(Command("reframing"))
async def cmd_technique_reframing(message: types.Message):
    await message.answer(TECHNIQUES["reframing"]["description"], parse_mode="HTML")

@dp.message(Command("five_minutes"))
async def cmd_technique_five_minutes(message: types.Message):
    await message.answer(TECHNIQUES["five_minutes"]["description"], parse_mode="HTML")

@dp.message(Command("body_scan"))
async def cmd_technique_body_scan(message: types.Message):
    await message.answer(TECHNIQUES["body_scan"]["description"], parse_mode="HTML")

# === ОБРАБОТЧИКИ КНОПОК ===

@dp.callback_query(F.data == "mood")
async def process_mood(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😄 Отлично", callback_data="mood_😄")],
        [InlineKeyboardButton(text="🙂 Нормально", callback_data="mood_🙂")],
        [InlineKeyboardButton(text="😐 Так себе", callback_data="mood_😐")],
        [InlineKeyboardButton(text="😢 Грустно", callback_data="mood_")],
        [InlineKeyboardButton(text=" Тревожно", callback_data="mood_")],
        [InlineKeyboardButton(text=" Злюсь", callback_data="mood_")],
    ])
    text = "😊 <b>Как ты себя чувствуешь прямо сейчас?</b>\n\nВыбери эмоцию:"
    await callback_query.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("mood_"))
async def process_mood_selection(callback_query: types.CallbackQuery):
    """Сохраняет выбранное настроение в БД"""
    mood = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    
    db.log_mood(user_id, mood)
    
    responses = {
        "😄": "Отлично! Рад за тебя! 🌟 Что сделало твой день таким хорошим?",
        "🙂": "Хорошо! Стабильность — это тоже ценно. Есть что-то, что хочешь обсудить?",
        "": "Понимаю, бывают такие дни. Хочешь поговорить о том, что на душе?",
        "😢": "Мне жаль, что тебе грустно. Я здесь. Хочешь рассказать, что случилось?",
        "😰": "Тревога — это тяжело. Давай попробуем разобраться вместе. Что тебя беспокоит?",
        "": "Злость — нормальная эмоция. Важно её не подавлять. Что тебя разозлило?",
    }
    
    text = f"Записал твоё настроение: {mood}\n\n{responses.get(mood, '')}"
    await callback_query.message.answer(text)
    await callback_query.answer()

@dp.callback_query(F.data == "techniques")
async def process_techniques_button(callback_query: types.CallbackQuery):
    await show_techniques_list(callback_query.message)
    await callback_query.answer()

@dp.callback_query(F.data == "mood_stats")
async def process_mood_stats(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    stats = db.get_mood_stats(user_id, days=7)
    
    if not stats:
        text = "📊 <b>Пока нет данных</b>\n\nИспользуй /mood, чтобы отмечать настроение!"
        await callback_query.message.answer(text, parse_mode="HTML")
    else:
        text = " <b>Твоё настроение за 7 дней:</b>\n\n"
        total = sum(row["count"] for row in stats)
        for row in stats:
            mood = row["mood"]
            count = row["count"]
            percentage = int((count / total) * 100)
            bar = "█" * (percentage // 5)
            text += f"{mood} <b>{count} раз</b> ({percentage}%)\n{bar}\n\n"
        
        history = db.get_mood_history(user_id, days=7)
        chart_path = generate_mood_chart(user_id, history)
        
        if chart_path and os.path.exists(chart_path):
            photo = FSInputFile(chart_path)
            await callback_query.message.answer_photo(photo, caption=text, parse_mode="HTML")
        else:
            await callback_query.message.answer(text, parse_mode="HTML")
    
    await callback_query.answer()

@dp.callback_query(F.data == "crisis")
async def process_crisis(callback_query: types.CallbackQuery):
    text = (
        "⚠️ <b>Экстренная помощь</b>\n\n"
        "Если ты в кризисе:\n\n"
        "📞 <b>Телефон доверия:</b>\n"
        "• 8-800-2000-122\n"
        "• 8-800-333-44-34\n\n"
        " <b>Экстренные службы:</b>\n"
        "• 112\n"
        "• 103"
    )
    await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(F.data == "random_technique")
async def cmd_random_technique(callback_query: types.CallbackQuery):
    technique_key = random.choice(list(TECHNIQUES.keys()))
    technique = TECHNIQUES[technique_key]
    text = f"<b>🎲 Случайная техника:</b>\n\n{technique['description']}"
    await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()

# === ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА ===

@dp.message()
async def chat_handler(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text
    
    # Проверяем, не команда ли это (команды обрабатываются отдельно)
    if user_text and user_text.startswith('/'):
        return
    
    # Регистрируем пользователя, если ещё не в БД
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # === КРИЗИС ===
    crisis_level = check_crisis_level(user_text)
    if crisis_level > 0:
        await message.answer(get_crisis_response(crisis_level), parse_mode="HTML")
        db.save_message(user_id, "user", user_text)
        return
    
    # Сохраняем сообщение пользователя
    db.save_message(user_id, "user", user_text)
    
    # Загружаем историю из БД
    history = db.get_recent_messages(user_id, limit=15)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    status_msg = await message.answer("🧠 EmoGuard думает...")

    try:
        response = ollama.chat(model='llama3.1', messages=messages, stream=False)
        ai_response = response['message']['content']
        
        # Сохраняем ответ ИИ
        db.save_message(user_id, "assistant", ai_response)
        
        await status_msg.delete()
        await message.answer(ai_response)
        
    except Exception as e:
        print(f"Ошибка Ollama: {e}")
        await status_msg.edit_text("😔 Проблема. Убедись, что Ollama запущена.")

async def main():
    print("🛡️ EmoGuard запущен с базой данных!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())