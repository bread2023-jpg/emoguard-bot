import sqlite3
from datetime import datetime

DB_NAME = "emoguard.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
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
        
        # Таблица настроения (БЕЗ колонки note!)
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

def add_user(user_id, username, first_name):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        conn.commit()

def get_user_subscription(user_id):
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
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET subscription_type = ?, subscription_expires = ?
            WHERE user_id = ?
        ''', (subscription_type, expires, user_id))
        conn.commit()

def is_premium(user_id):
    sub = get_user_subscription(user_id)
    if sub['type'] == 'premium' and sub['expires']:
        try:
            expires = datetime.fromisoformat(sub['expires'])
            if expires > datetime.now():
                return True
        except:
            pass
    return False

def get_daily_message_count(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM messages 
            WHERE user_id = ? AND role = 'user' 
            AND created_at LIKE ?
        ''', (user_id, f'{today}%'))
        return cursor.fetchone()[0]

def save_message(user_id, role, content):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (user_id, role, content) 
            VALUES (?, ?, ?)
        ''', (user_id, role, content))
        conn.commit()

def get_recent_messages(user_id, limit=15):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content FROM messages 
            WHERE user_id = ? 
            ORDER BY id DESC 
            LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        return [{'role': row['role'], 'content': row['content']} for row in reversed(rows)]

def get_message_count(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM messages 
            WHERE user_id = ? AND role = 'user'
        ''', (user_id,))
        return cursor.fetchone()[0]

def clear_user_history(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
        deleted = cursor.rowcount
        conn.commit()
        return deleted

def log_mood(user_id, mood):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mood_logs (user_id, mood) 
            VALUES (?, ?)
        ''', (user_id, mood))
        conn.commit()

def get_mood_stats(user_id, days=7):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT mood, COUNT(*) as count 
            FROM mood_logs 
            WHERE user_id = ? 
            AND created_at >= datetime('now', '-{} days')
            GROUP BY mood 
            ORDER BY count DESC
        '''.format(days), (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_mood_history(user_id, days=7):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT mood, created_at 
            FROM mood_logs 
            WHERE user_id = ? 
            AND created_at >= datetime('now', '-{} days')
            ORDER BY created_at
        '''.format(days), (user_id,))
        return [dict(row) for row in cursor.fetchall()]

# Инициализируем БД при импорте
init_db()
