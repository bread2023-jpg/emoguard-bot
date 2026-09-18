import sqlite3
from datetime import datetime, timedelta
from datetime import datetime

# Название файла базы данных
DB_NAME = "emoguard.db"

def get_connection():
    """Создаёт подключение к базе данных"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Возвращает строки как словари
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей с подпиской
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_type TEXT DEFAULT 'free',
                subscription_expires TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица настроения
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                mood TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        conn.commit()
        print("✅ База данных инициализирована")

# === ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ===

def add_user(user_id, username=None, first_name=None):
    """Добавляет нового пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def get_user(user_id):
    """Получает информацию о пользователе"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# === ФУНКЦИИ ДЛЯ РАБОТЫ С СООБЩЕНИЯМИ ===

def save_message(user_id, role, content):
    """Сохраняет сообщение в историю"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content)
    )
    conn.commit()
    conn.close()

def get_recent_messages(user_id, limit=15):
    """Получает последние N сообщений пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT role, content FROM messages 
           WHERE user_id = ? 
           ORDER BY timestamp DESC 
           LIMIT ?""",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    # Возвращаем в правильном порядке (от старых к новым)
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

def clear_user_history(user_id):
    """Очищает историю сообщений пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def get_message_count(user_id):
    """Считает количество сообщений пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM messages WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()["count"]
    conn.close()
    return count

# === ФУНКЦИИ ДЛЯ ТРЕКЕРА НАСТРОЕНИЯ ===

def log_mood(user_id, mood, note=None):
    """Записывает настроение пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mood_logs (user_id, mood, note) VALUES (?, ?, ?)",
        (user_id, mood, note)
    )
    conn.commit()
    conn.close()

def get_mood_stats(user_id, days=7):
    """Получает статистику настроения за N дней"""
    conn = get_connection()
    cursor = conn.cursor()
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute(
        """SELECT mood, COUNT(*) as count 
           FROM mood_logs 
           WHERE user_id = ? AND timestamp > ?
           GROUP BY mood
           ORDER BY count DESC""",
        (user_id, cutoff_date)
    )
    stats = cursor.fetchall()
    conn.close()
    return stats

def get_mood_history(user_id, days=7):
    """Получает историю настроений за N дней (для графика)"""
    conn = get_connection()
    cursor = conn.cursor()
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute(
        """SELECT mood, timestamp 
           FROM mood_logs 
           WHERE user_id = ? AND timestamp > ?
           ORDER BY timestamp ASC""",
        (user_id, cutoff_date)
    )
    history = cursor.fetchall()
    conn.close()
    return history

def get_user_subscription(user_id):
    """Получить статус подписки пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT subscription_type, subscription_expires 
            FROM users 
            WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        if result:
            return {
                'type': result[0] or 'free',
                'expires': result[1]
            }
        return {'type': 'free', 'expires': None}

def set_subscription(user_id, subscription_type, expires):
    """Установить подписку"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET subscription_type = ?, subscription_expires = ?
            WHERE user_id = ?
        ''', (subscription_type, expires, user_id))
        conn.commit()

def get_daily_message_count(user_id):
    """Получить количество сообщений за сегодня"""
    with get_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM messages 
            WHERE user_id = ? AND role = 'user' 
            AND created_at LIKE ?
        ''', (user_id, f'{today}%'))
        return cursor.fetchone()[0]

def is_premium(user_id):
    """Проверить, есть ли у пользователя премиум"""
    sub = get_user_subscription(user_id)
    if sub['type'] == 'premium' and sub['expires']:
        from datetime import datetime
        expires = datetime.fromisoformat(sub['expires'])
        if expires > datetime.now():
            return True
    return False

# Инициализируем БД при импорте
init_db()
