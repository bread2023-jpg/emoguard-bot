from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram import Bot
import database as db
from datetime import datetime, timedelta

# Цена подписки в копейках (299 рублей = 29900 копеек)
PREMIUM_PRICE = 29900
PREMIUM_CURRENCY = "RUB"

async def cmd_subscription(message: types.Message, bot: Bot):
    """Показать информацию о подписке"""
    user_id = message.from_user.id
    sub = db.get_user_subscription(user_id)
    
    if db.is_premium(user_id):
        text = (
            "⭐ <b>У вас уже есть Premium подписка!</b>\n\n"
            f"Действует до: {sub['expires'][:10]}\n\n"
            "Спасибо за поддержку EmoGuard! 💙"
        )
    else:
        text = (
            "⭐ <b>Premium подписка EmoGuard</b>\n\n"
            "<b>Что вы получаете:</b>\n"
            "✅ Безлимит сообщений с ИИ\n"
            "✅ Расширенная аналитика (30 дней)\n"
            "✅ Персональные планы работы с эмоциями\n"
            "✅ Приоритетная поддержка\n"
            "✅ Эксклюзивные техники\n\n"
            "<b>Цена:</b> 299₽/месяц\n\n"
            "Нажмите кнопку ниже, чтобы оформить подписку:"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оформить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton(text="📊 Мои лимиты", callback_data="check_limits")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

async def process_buy_premium(callback_query: types.CallbackQuery, bot: Bot):
    """Обработка покупки премиума"""
    user_id = callback_query.from_user.id
    
    # Создаем инвойс для оплаты
    prices = [LabeledPrice(label="Premium подписка EmoGuard", amount=PREMIUM_PRICE)]
    
    await bot.send_invoice(
        chat_id=user_id,
        title="Premium подписка EmoGuard",
        description="Безлимит сообщений, расширенная аналитика и персональные планы на 1 месяц",
        payload="premium_subscription",
        provider_token="381764678:TEST:123456789",  # Замени на свой токен от ЮKassa или другого провайдера
        currency=PREMIUM_CURRENCY,
        prices=prices,
        start_parameter="premium-subscription",
        need_name=False,
        need_email=False,
        need_phone_number=False,
        need_shipping_address=False
    )
    
    await callback_query.answer()

async def process_pre_checkout(pre_checkout_query, bot: Bot):
    """Обработка перед оплатой"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

async def process_successful_payment(message: types.Message, bot: Bot):
    """Обработка успешной оплаты"""
    user_id = message.from_user.id
    
    # Устанавливаем премиум на 30 дней
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.set_subscription(user_id, 'premium', expires)
    
    text = (
        "🎉 <b>Поздравляем! Premium подписка активирована!</b>\n\n"
        f"Действует до: {expires[:10]}\n\n"
        "Теперь вам доступны:\n"
        "✅ Безлимит сообщений\n"
        "✅ Расширенная аналитика\n"
        "✅ Персональные планы\n"
        "✅ Приоритетная поддержка\n\n"
        "Спасибо за поддержку EmoGuard! 💙"
    )
    
    await message.answer(text, parse_mode="HTML")

def check_message_limit(user_id):
    """Проверить лимит сообщений"""
    if db.is_premium(user_id):
        return True, 0  # Безлимит
    
    count = db.get_daily_message_count(user_id)
    limit = 10  # 10 сообщений в день для бесплатных
    
    if count >= limit:
        return False, limit - count
    return True, limit - count
