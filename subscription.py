from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import database as db

async def cmd_subscription(message: types.Message, bot):
    user_id = message.from_user.id
    sub = db.get_user_subscription(user_id)
    
    if db.is_premium(user_id):
        text = f"⭐ <b>У вас уже есть Premium подписка!</b>\n\nДействует до: {sub['expires'][:10]}\n\nСпасибо за поддержку EmoGuard! 💙"
    else:
        text = (
            "⭐ <b>Premium подписка EmoGuard</b>\n\n"
            "<b>Что вы получаете:</b>\n"
            "✅ Безлимит сообщений с ИИ\n"
            "✅ Расширенная аналитика (30 дней)\n"
            "✅ Персональные планы работы с эмоциями\n\n"
            "<b>Цена:</b> 299₽/месяц\n\n"
            "⚠️ Оплата временно недоступна. Скоро подключим!"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Мои лимиты", callback_data="check_limits")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

async def process_buy_premium(callback_query: types.CallbackQuery, bot):
    await callback_query.message.answer(
        "️ Оплата временно недоступна. Мы скоро подключим платёжную систему!",
        parse_mode="HTML"
    )
    await callback_query.answer()

async def process_pre_checkout(pre_checkout_query, bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

async def process_successful_payment(message: types.Message, bot):
    user_id = message.from_user.id
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.set_subscription(user_id, 'premium', expires)
    
    text = f"🎉 <b>Premium активирован!</b>\n\nДействует до: {expires[:10]}\nТеперь у вас безлимит сообщений! 💙"
    await message.answer(text, parse_mode="HTML")

def check_message_limit(user_id):
    if db.is_premium(user_id):
        return True, 0
    count = db.get_daily_message_count(user_id)
    limit = 10
    if count >= limit:
        return False, 0
    return True, limit - count
