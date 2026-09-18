import asyncio
import os
import random
import json
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
TOKEN = os.environ.get('BOT_TOKEN')
YANDEX_API_KEY = os.environ.get('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.environ.get('YANDEX_FOLDER_ID')

bot = Bot(token=TOKEN)
dp = Dispatcher()

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

# === YANDEXGPT API ===
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
• Эмодзи — умеренно и к месту"""

def call_yandexgpt(messages):
    """Вызов YandexGPT API"""
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "x-folder-id": YANDEX_FOLDER_ID
    }
    
    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": "1000"
        },
        "messages": messages
    }
    
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    if "result" in result and "alternatives" in result["result"]:
        return result["result"]["alternatives"][0]["message"]["text"]
    else:
        return "😔 Извини, у меня возникла проблема. Попробуй ещё раз."

# === БАЗА ТЕХНИК ===
TECHNIQUES = {
    "breathing": {
        "name": "️ Дыхание 4-7-8",
        "description": "<b>Дыхательная техника для быстрого успокоения</b>\n\n1️⃣ Сядь удобно\n2️⃣ Вдох через нос на <b>4 счёта</b>\n3️⃣ Задержка на <b>7 счетов</b>\n4️⃣ Выдох через рот на <b>8 счетов</b>\n\nПовтори 4-6 циклов."
    },
    "grounding": {
        "name": " Заземление 5-4-3-2-1",
        "description": "<b>Техника при тревоге</b>\n\nНайди вокруг:\n👀 <b>5 вещей</b>, которые видишь\n👂 <b>4 звука</b>\n✋ <b>3 ощущения</b>\n👃 <b>2 запаха</b>\n👅 <b>1 вкус</b>"
    },
    "pmr": {
        "name": "💪 Прогрессивная мышечная релаксация",
        "description": "<b>Расслабление через напряжение</b>\n\n1️⃣ Напряги мышцы стоп на 5 сек\n2️⃣ Расслабь на 10 сек\n3️⃣ Поднимайся: икры → бёдра → живот → руки → плечи → лицо"
    },
    "safe_place": {
        "name": "🏝️ Безопасное место",
        "description": "<b>Визуализация</b>\n\n1️⃣ Закрой глаза\n2️⃣ Представь место, где безопасно\n3️⃣ Детализируй: звуки, запахи, ощущения\n4️⃣ Побудь там 2-3 минуты"
    },
    "gratitude": {
        "name": "📔 Дневник благодарности",
        "description": "<b>Смещение фокуса на позитив</b>\n\nНапиши 3 вещи, за которые благодарен сегодня. Даже маленькие: вкусный кофе, улыбка, тёплая одежда."
    },
    "reframing": {
        "name": "🔄 Когнитивный рефрейминг",
        "description": "<b>Переосмысление мыслей</b>\n\n1️⃣ Запиши мысль\n2️⃣ Спроси: это факт или интерпретация?\n3️⃣ Найди альтернативный взгляд"
    },
    "five_minutes": {
        "name": "⏱️ Правило 5 минут",
        "description": "<b>Борьба с прокрастинацией</b>\n\nСкажи: 'Я позанимаюсь этим 5 минут'. Поставь таймер. Начни. Чаще всего ты продолжишь."
    },
    "body_scan": {
        "name": "🧘 Сканирование тела",
        "description": "<b>Осознанность</b>\n\n1️⃣ Ляг удобно\n2️⃣ Начни с макушки\n3️⃣ Двигайся вниз, расслабляя зоны\n4️⃣ 5-10 минут. Отлично перед сном."
    }
}

# === КЛАВИАТУРЫ ===
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😊 Как я себя чувствую?", callback_data="mood")],
    [InlineKeyboardButton(text=" Техники самопомощи", callback_data="techniques")],
    [InlineKeyboardButton(text=" Моё настроение", callback_data="mood_stats")],
    [InlineKeyboardButton(text=" Экстренная помощь", callback_data="crisis")],
])

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def show_techniques_list(message):
    text = "<b>🧘 Техники самопомощи</b>\n\nВыбери технику:\n\n"
    for key, technique in TECHNIQUES.items():
        text += f"• /{key} — {technique['name']}\n"
    text += "\nИли нажми кнопку для случайной техники "
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" Случайная техника", callback_data="random_technique")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# === ОБРАБОТЧИКИ КОМАНД ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
