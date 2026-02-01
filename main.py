import asyncio
import sqlite3
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8531868933:AAF9Qrld-gsy1lUi7lqOQTgP9fzYJOfbFpQ"
ADMIN_ID = 8152056819  # Ваш ID

STAR_PRICE = 1.37  # 1 звезда = 1.37 руб
MIN_BUY_STARS = 50  # Минимальная покупка
MIN_SELL_STARS = 100  # Минимальная продажа
MIN_PAYMENT = 10  # Минимальное пополнение в рублях


# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self, db_path: str = "harnel.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        print("✅ База данных инициализирована")

    def _init_tables(self):
        cursor = self.conn.cursor()

        # Пользователи
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS users
                       (
                           user_id
                           INTEGER
                           PRIMARY
                           KEY,
                           username
                           TEXT,
                           balance
                           REAL
                           DEFAULT
                           0.0,
                           reg_date
                           TEXT
                       )
                       ''')

        # NFT подарки для продажи
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS nft_gift_sale
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT,
                           url
                           TEXT,
                           price
                           REAL,
                           available
                           INTEGER
                           DEFAULT
                           1
                       )
                       ''')

        # NFT подарки для аренды
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS nft_gift_rent
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT,
                           url
                           TEXT,
                           price_per_day
                           REAL,
                           available
                           INTEGER
                           DEFAULT
                           1
                       )
                       ''')

        # NFT юзы для продажи
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS nft_use_sale
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT,
                           url
                           TEXT,
                           price
                           REAL,
                           available
                           INTEGER
                           DEFAULT
                           1
                       )
                       ''')

        # NFT юзы для аренды
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS nft_use_rent
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT,
                           url
                           TEXT,
                           price_per_day
                           REAL,
                           available
                           INTEGER
                           DEFAULT
                           1
                       )
                       ''')

        # Заказы на звезды
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS star_orders
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           order_type
                           TEXT,
                           amount
                           REAL,
                           total_rub
                           REAL,
                           target_username
                           TEXT,
                           status
                           TEXT
                           DEFAULT
                           'pending',
                           payment_proof
                           TEXT,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        # Платежи
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS payments
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           amount
                           REAL,
                           method
                           TEXT,
                           status
                           TEXT
                           DEFAULT
                           'pending',
                           proof_text
                           TEXT,
                           confirmed
                           INTEGER
                           DEFAULT
                           0,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        # Пользовательские NFT
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS user_nft
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           nft_id
                           INTEGER,
                           nft_type
                           TEXT,
                           expires_at
                           TEXT,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        self.conn.commit()
        print("✅ Таблицы созданы")

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def create_user(self, user_id: int, username: str):
        cursor = self.conn.cursor()
        reg_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            cursor.execute('''
                           INSERT
                           OR IGNORE INTO users (user_id, username, reg_date) 
                VALUES (?, ?, ?)
                           ''', (user_id, username, reg_date))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Ошибка создания пользователя: {e}")

    def update_balance(self, user_id: int, amount: float):
        cursor = self.conn.cursor()
        cursor.execute('''
                       UPDATE users
                       SET balance = balance + ?
                       WHERE user_id = ?
                       ''', (amount, user_id))
        self.conn.commit()

    def create_star_order(self, user_id: int, order_type: str, amount: float,
                          total_rub: float, target_username: str = ""):
        cursor = self.conn.cursor()
        cursor.execute('''
                       INSERT INTO star_orders (user_id, order_type, amount, total_rub, target_username, status)
                       VALUES (?, ?, ?, ?, ?, 'pending')
                       ''', (user_id, order_type, amount, total_rub, target_username))
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_orders(self):
        cursor = self.conn.cursor()
        cursor.execute('''
                       SELECT so.*, u.username
                       FROM star_orders so
                                JOIN users u ON so.user_id = u.user_id
                       WHERE so.status = 'pending'
                       ORDER BY so.created_at DESC
                       ''')
        return [dict(row) for row in cursor.fetchall()]

    def get_user_orders(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
                       SELECT *
                       FROM star_orders
                       WHERE user_id = ?
                       ORDER BY created_at DESC LIMIT 10
                       ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def complete_order(self, order_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
                       UPDATE star_orders
                       SET status = 'completed'
                       WHERE id = ?
                       ''', (order_id,))
        self.conn.commit()

    def get_nft_gift_sale(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nft_gift_sale WHERE available = 1")
        return [dict(row) for row in cursor.fetchall()]

    def get_nft_gift_rent(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nft_gift_rent WHERE available = 1")
        return [dict(row) for row in cursor.fetchall()]

    def get_nft_use_sale(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nft_use_sale WHERE available = 1")
        return [dict(row) for row in cursor.fetchall()]

    def get_nft_use_rent(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nft_use_rent WHERE available = 1")
        return [dict(row) for row in cursor.fetchall()]

    def add_nft_gift_sale(self, name: str, url: str, price: float):
        cursor = self.conn.cursor()
        cursor.execute('''
                       INSERT INTO nft_gift_sale (name, url, price)
                       VALUES (?, ?, ?)
                       ''', (name, url, price))
        self.conn.commit()

    def add_nft_gift_rent(self, name: str, url: str, price_per_day: float):
        cursor = self.conn.cursor()
        cursor.execute('''
                       INSERT INTO nft_gift_rent (name, url, price_per_day)
                       VALUES (?, ?, ?)
                       ''', (name, url, price_per_day))
        self.conn.commit()

    def add_nft_use_sale(self, name: str, url: str, price: float):
        cursor = self.conn.cursor()
        cursor.execute('''
                       INSERT INTO nft_use_sale (name, url, price)
                       VALUES (?, ?, ?)
                       ''', (name, url, price))
        self.conn.commit()

    def add_nft_use_rent(self, name: str, url: str, price_per_day: float):
        cursor = self.conn.cursor()
        cursor.execute('''
                       INSERT INTO nft_use_rent (name, url, price_per_day)
                       VALUES (?, ?, ?)
                       ''', (name, url, price_per_day))
        self.conn.commit()

    def delete_nft_gift_sale(self, nft_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nft_gift_sale WHERE id = ?", (nft_id,))
        self.conn.commit()

    def delete_nft_gift_rent(self, nft_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nft_gift_rent WHERE id = ?", (nft_id,))
        self.conn.commit()

    def delete_nft_use_sale(self, nft_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nft_use_sale WHERE id = ?", (nft_id,))
        self.conn.commit()

    def delete_nft_use_rent(self, nft_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM nft_use_rent WHERE id = ?", (nft_id,))
        self.conn.commit()

    def get_nft_gift_sale_list(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM nft_gift_sale")
        return [dict(row) for row in cursor.fetchall()]

    def get_nft_gift_rent_list(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM nft_gift_rent")
        return [dict(row) for row in cursor.fetchall()]

    def get_nft_use_sale_list(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM nft_use_sale")
        return [dict(row) for row in cursor.fetchall()]

    def get_nft_use_rent_list(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM nft_use_rent")
        return [dict(row) for row in cursor.fetchall()]

    def buy_nft_gift_sale(self, user_id: int, nft_id: int):
        cursor = self.conn.cursor()
        cursor.execute("SELECT price FROM nft_gift_sale WHERE id = ? AND available = 1", (nft_id,))
        nft_row = cursor.fetchone()

        if nft_row:
            nft = dict(nft_row)
            price = nft['price']
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if user_row:
                user = dict(user_row)
                if user['balance'] >= price:
                    try:
                        cursor.execute('''
                                       UPDATE users
                                       SET balance = balance - ?
                                       WHERE user_id = ?
                                       ''', (price, user_id))

                        cursor.execute('''
                                       INSERT INTO user_nft (user_id, nft_id, nft_type)
                                       VALUES (?, ?, 'gift_sale')
                                       ''', (user_id, nft_id))

                        self.conn.commit()

                        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                        updated_user = cursor.fetchone()
                        new_balance = updated_user['balance'] if updated_user else 0

                        return True, f"✅ NFT подарок успешно куплен!\n💰 Новый баланс: {new_balance:.2f} руб"
                    except Exception as e:
                        self.conn.rollback()
                        print(f"❌ Ошибка покупки NFT: {e}")
                        return False, f"❌ Ошибка при покупке: {str(e)}"
                else:
                    return False, f"❌ Недостаточно средств! Нужно: {price:.2f} руб, на балансе: {user['balance']:.2f} руб"

        return False, "❌ Недостаточно средств или NFT не найден!"

    def rent_nft_gift(self, user_id: int, nft_id: int, days: int):
        cursor = self.conn.cursor()
        cursor.execute("SELECT price_per_day FROM nft_gift_rent WHERE id = ? AND available = 1", (nft_id,))
        nft_row = cursor.fetchone()

        if nft_row:
            nft = dict(nft_row)
            total_price = nft['price_per_day'] * days
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if user_row:
                user = dict(user_row)
                if user['balance'] >= total_price:
                    try:
                        cursor.execute('''
                                       UPDATE users
                                       SET balance = balance - ?
                                       WHERE user_id = ?
                                       ''', (total_price, user_id))

                        expires = datetime.now().timestamp() + (days * 86400)
                        expires_str = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M")

                        cursor.execute('''
                                       INSERT INTO user_nft (user_id, nft_id, nft_type, expires_at)
                                       VALUES (?, ?, 'gift_rent', ?)
                                       ''', (user_id, nft_id, expires_str))

                        self.conn.commit()

                        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                        updated_user = cursor.fetchone()
                        new_balance = updated_user['balance'] if updated_user else 0

                        return True, f"✅ NFT подарок арендован на {days} дней!\n💰 Новый баланс: {new_balance:.2f} руб"
                    except Exception as e:
                        self.conn.rollback()
                        print(f"❌ Ошибка аренды NFT: {e}")
                        return False, f"❌ Ошибка при аренде: {str(e)}"
                else:
                    return False, f"❌ Недостаточно средств! Нужно: {total_price:.2f} руб, на балансе: {user['balance']:.2f} руб"

        return False, "❌ Недостаточно средств или NFT не найден!"

    def buy_nft_use_sale(self, user_id: int, nft_id: int):
        cursor = self.conn.cursor()
        cursor.execute("SELECT price FROM nft_use_sale WHERE id = ? AND available = 1", (nft_id,))
        nft_row = cursor.fetchone()

        if nft_row:
            nft = dict(nft_row)
            price = nft['price']
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if user_row:
                user = dict(user_row)
                if user['balance'] >= price:
                    try:
                        cursor.execute('''
                                       UPDATE users
                                       SET balance = balance - ?
                                       WHERE user_id = ?
                                       ''', (price, user_id))

                        cursor.execute('''
                                       INSERT INTO user_nft (user_id, nft_id, nft_type)
                                       VALUES (?, ?, 'use_sale')
                                       ''', (user_id, nft_id))

                        self.conn.commit()

                        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                        updated_user = cursor.fetchone()
                        new_balance = updated_user['balance'] if updated_user else 0

                        return True, f"✅ NFT юз успешно куплен!\n💰 Новый баланс: {new_balance:.2f} руб"
                    except Exception as e:
                        self.conn.rollback()
                        print(f"❌ Ошибка покупки NFT: {e}")
                        return False, f"❌ Ошибка при покупке: {str(e)}"
                else:
                    return False, f"❌ Недостаточно средств! Нужно: {price:.2f} руб, на балансе: {user['balance']:.2f} руб"

        return False, "❌ Недостаточно средств или NFT не найден!"

    def rent_nft_use(self, user_id: int, nft_id: int, days: int):
        cursor = self.conn.cursor()
        cursor.execute("SELECT price_per_day FROM nft_use_rent WHERE id = ? AND available = 1", (nft_id,))
        nft_row = cursor.fetchone()

        if nft_row:
            nft = dict(nft_row)
            total_price = nft['price_per_day'] * days
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if user_row:
                user = dict(user_row)
                if user['balance'] >= total_price:
                    try:
                        cursor.execute('''
                                       UPDATE users
                                       SET balance = balance - ?
                                       WHERE user_id = ?
                                       ''', (total_price, user_id))

                        expires = datetime.now().timestamp() + (days * 86400)
                        expires_str = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M")

                        cursor.execute('''
                                       INSERT INTO user_nft (user_id, nft_id, nft_type, expires_at)
                                       VALUES (?, ?, 'use_rent', ?)
                                       ''', (user_id, nft_id, expires_str))

                        self.conn.commit()

                        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                        updated_user = cursor.fetchone()
                        new_balance = updated_user['balance'] if updated_user else 0

                        return True, f"✅ NFT юз арендован на {days} дней!\n💰 Новый баланс: {new_balance:.2f} руб"
                    except Exception as e:
                        self.conn.rollback()
                        print(f"❌ Ошибка аренды NFT: {e}")
                        return False, f"❌ Ошибка при аренде: {str(e)}"
                else:
                    return False, f"❌ Недостаточно средств! Нужно: {total_price:.2f} руб, на балансе: {user['balance']:.2f} руб"

        return False, "❌ Недостаточно средств или NFT не найден!"

    def create_payment(self, user_id: int, amount: float, method: str, proof: str = ""):
        cursor = self.conn.cursor()
        cursor.execute('''
                       INSERT INTO payments (user_id, amount, method, proof_text, status)
                       VALUES (?, ?, ?, ?, 'pending')
                       ''', (user_id, amount, method, proof))
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_payments(self):
        cursor = self.conn.cursor()
        cursor.execute('''
                       SELECT p.*, u.username
                       FROM payments p
                                JOIN users u ON p.user_id = u.user_id
                       WHERE p.status = 'pending'
                       ORDER BY p.created_at DESC
                       ''')
        return [dict(row) for row in cursor.fetchall()]

    def confirm_payment(self, payment_id: int):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, amount FROM payments WHERE id = ?", (payment_id,))
        payment = cursor.fetchone()

        if payment:
            user_id = payment['user_id']
            amount = payment['amount']
            cursor.execute('''
                           UPDATE users
                           SET balance = balance + ?
                           WHERE user_id = ?
                           ''', (amount, user_id))
            cursor.execute('''
                           UPDATE payments
                           SET status    = 'completed',
                               confirmed = 1
                           WHERE id = ?
                           ''', (payment_id,))
            self.conn.commit()
            return True
        return False

    def reject_payment(self, payment_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
                       UPDATE payments
                       SET status    = 'rejected',
                           confirmed = 0
                       WHERE id = ?
                       ''', (payment_id,))
        self.conn.commit()
        return True

    def get_all_users(self):
        """Получить всех пользователей для рассылки"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [row['user_id'] for row in cursor.fetchall()]


# ========== СОСТОЯНИЯ ==========
class OrderStates(StatesGroup):
    waiting_buy_amount = State()
    waiting_sell_amount = State()
    waiting_target_user = State()
    waiting_calculator = State()
    waiting_gift_sale_name = State()
    waiting_gift_sale_url = State()
    waiting_gift_sale_price = State()
    waiting_gift_rent_name = State()
    waiting_gift_rent_url = State()
    waiting_gift_rent_price = State()
    waiting_use_sale_name = State()
    waiting_use_sale_url = State()
    waiting_use_sale_price = State()
    waiting_use_rent_name = State()
    waiting_use_rent_url = State()
    waiting_use_rent_price = State()
    waiting_gift_rent_days = State()
    waiting_use_rent_days = State()
    waiting_payment_amount = State()
    waiting_payment_method = State()
    waiting_broadcast_message = State()  # Добавлено для рассылки


# ========== ИНИЦИАЛИЗАЦИЯ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализируем базу данных
try:
    db = Database()
    print("✅ База данных подключена")
except Exception as e:
    print(f"❌ Ошибка подключения БД: {e}")
    db = None


# ========== КЛАВИАТУРЫ ==========
def main_menu_keyboard(user_id: int):
    """Главное меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🧮 Калькулятор")],
            [KeyboardButton(text="⭐ Купить звезды"), KeyboardButton(text="💎 Продать звезды")],
            [KeyboardButton(text="🎁 NFT Магазин"), KeyboardButton(text="💰 Пополнить баланс")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

    if user_id == ADMIN_ID:
        keyboard.keyboard.append([KeyboardButton(text="🔧 Админ панель")])

    keyboard.keyboard.append([KeyboardButton(text="🏠 В меню")])
    return keyboard


def nft_categories_keyboard():
    """Клавиатура с 4 категориями NFT"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Покупка NFT подарка"), KeyboardButton(text="🏠 Аренда NFT подарка")],
            [KeyboardButton(text="🎮 Покупка NFT юза"), KeyboardButton(text="⚡ Аренда NFT юза")],
            [KeyboardButton(text="↩️ Назад"), KeyboardButton(text="🏠 В меню")]
        ],
        resize_keyboard=True
    )


def payment_methods_keyboard():
    """Клавиатура с методами оплаты"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Перевод на карту"), KeyboardButton(text="₿ Криптовалюта")],
            [KeyboardButton(text="↩️ Назад к сумме")],
            [KeyboardButton(text="🏠 В меню")]
        ],
        resize_keyboard=True
    )


def admin_menu_keyboard():
    """Меню админа - 8 кнопок"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Просмотр заказов"), KeyboardButton(text="💰 Платежи на проверку")],
            [KeyboardButton(text="🎁 NFT подарок в продажу"), KeyboardButton(text="🏠 NFT подарок в аренду")],
            [KeyboardButton(text="🎮 NFT юз в продажу"), KeyboardButton(text="⚡ NFT юз в аренду")],
            [KeyboardButton(text="🗑️ Удаление NFT"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🏠 В меню")]
        ],
        resize_keyboard=True
    )


def delete_nft_menu_keyboard():
    """Меню удаления NFT - 4 категории"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить NFT подарок в продаже", callback_data="delete_gift_sale_menu")],
        [InlineKeyboardButton(text="🗑️ Удалить NFT подарок в аренде", callback_data="delete_gift_rent_menu")],
        [InlineKeyboardButton(text="🗑️ Удалить NFT юз в продаже", callback_data="delete_use_sale_menu")],
        [InlineKeyboardButton(text="🗑️ Удалить NFT юз в аренде", callback_data="delete_use_rent_menu")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")]
    ])


def back_to_menu_keyboard():
    """Кнопка 'В меню'"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 В меню")]],
        resize_keyboard=True
    )


def payment_keyboard(amount: int):
    """Клавиатура для оплаты звездами"""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {amount} ⭐️", pay=True)
    return builder.as_markup()


def confirm_payment_keyboard(payment_id: int):
    """Клавиатура для подтверждения платежа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_payment_{payment_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_payment_{payment_id}")
        ]
    ])


def confirm_broadcast_keyboard():
    """Клавиатура для подтверждения рассылки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_broadcast"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")
        ]
    ])


def nft_gift_sale_keyboard(nft_id: int):
    """Клавиатура для покупки NFT подарка"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить подарок", callback_data=f"buy_gift_sale_{nft_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_nft_categories")]
    ])


def nft_gift_rent_keyboard(nft_id: int):
    """Клавиатура для аренды NFT подарка"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Арендовать подарок", callback_data=f"rent_gift_{nft_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_nft_categories")]
    ])


def nft_use_sale_keyboard(nft_id: int):
    """Клавиатура для покупки NFT юза"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Купить юз", callback_data=f"buy_use_sale_{nft_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_nft_categories")]
    ])


def nft_use_rent_keyboard(nft_id: int):
    """Клавиатура для аренды NFT юза"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Арендовать юз", callback_data=f"rent_use_{nft_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_nft_categories")]
    ])


# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(Command("start"))
@dp.message(F.text == "🏠 В меню")
async def start_cmd(message: types.Message):
    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=back_to_menu_keyboard())
        return

    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    db.create_user(user_id, username)

    user = db.get_user(user_id)
    balance = user.get('balance', 0.0) if user else 0.0

    text = f"""
🏪 *Harnel.M Shop*

💰 Ваш баланс: *{balance:.2f} руб*

*Покупка звезд:* Через Telegram Stars
*Продажа звезд:* Через Telegram Stars → баланс в рублях

Выберите действие:"""

    await message.answer(text, reply_markup=main_menu_keyboard(user_id), parse_mode="Markdown")


@dp.message(F.text == "👤 Профиль")
async def profile_cmd(message: types.Message):
    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=back_to_menu_keyboard())
        return

    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Пользователь не найден!", reply_markup=back_to_menu_keyboard())
        return

    orders = db.get_user_orders(user_id)

    text = f"""
👤 *Профиль*

🆔 ID: `{user['user_id']}`
👤 Username: @{user['username']}
💰 Баланс: *{user['balance']:.2f} руб*
📅 Регистрация: {user['reg_date']}

📦 *Последние заказы:*"""

    if orders:
        for order in orders[:5]:
            text += f"\n• {order['order_type']} {order['amount']} зв - {order['status']}"
    else:
        text += "\n• Нет заказов"

    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "🧮 Калькулятор")
async def calculator_cmd(message: types.Message, state: FSMContext):
    text = f"""
🧮 *Калькулятор звезд*

💰 Курс: 1 звезда = {STAR_PRICE:.2f} руб
⭐ 1 руб = {1 / STAR_PRICE:.2f} звезд

Введите сумму в рублях чтобы узнать сколько это звезд:

*Пример:* 100

*Можно вводить сколько угодно чисел*
*Для выхода нажмите "В меню"*"""

    await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_calculator)


@dp.message(F.text == "⭐ Купить звезды")
async def buy_stars_cmd(message: types.Message, state: FSMContext):
    text = f"""
⭐ *Покупка звезд*

💰 Цена: {STAR_PRICE:.2f} руб за 1 звезду
📊 Минимальная покупка: {MIN_BUY_STARS} зв

Введите количество звезд для покупки:"""

    await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_buy_amount)


@dp.message(F.text == "💎 Продать звезды")
async def sell_stars_cmd(message: types.Message, state: FSMContext):
    text = f"""
💎 *Продажа звезд*

💰 Цена: {STAR_PRICE:.2f} руб за 1 звезду
📊 Минимальная продажа: {MIN_SELL_STARS} зв

*Как это работает:*
1. Вы указываете сколько звезд хотите продать
2. Мы создаем счет на оплату звездами
3. Вы оплачиваете через Telegram Stars
4. Получаете рубли на баланс в боте

Введите количество звезд для продажи:"""

    await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_sell_amount)


# ========== NFT МАГАЗИН ==========
@dp.message(F.text == "🎁 NFT Магазин")
async def nft_shop_cmd(message: types.Message):
    text = "🎁 *NFT Магазин*\n\n*Выберите категорию:*\n\n1) 🎁 Покупка NFT подарка\n2) 🏠 Аренда NFT подарка\n3) 🎮 Покупка NFT юза\n4) ⚡ Аренда NFT юза"
    await message.answer(text, reply_markup=nft_categories_keyboard(), parse_mode="Markdown")


@dp.message(F.text == "🎁 Покупка NFT подарка")
async def nft_gift_sale_cmd(message: types.Message):
    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=nft_categories_keyboard())
        return

    nft_items = db.get_nft_gift_sale()

    if not nft_items:
        text = "🎁 *Покупка NFT подарков*\n\nНет доступных NFT подарков для покупки."
        await message.answer(text, reply_markup=nft_categories_keyboard())
    else:
        text = "🎁 *Покупка NFT подарков*\n\nВыберите NFT подарок для покупки:"
        await message.answer(text, reply_markup=nft_categories_keyboard())

        for item in nft_items:
            item_text = f"""
📦 *{item['name']}*

🔗 Ссылка: {item['url']}
💰 Цена: {item['price']:.2f} руб

Нажмите кнопку ниже для покупки:"""

            keyboard = nft_gift_sale_keyboard(item['id'])
            await message.answer(item_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(F.text == "🏠 Аренда NFT подарка")
async def nft_gift_rent_cmd(message: types.Message):
    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=nft_categories_keyboard())
        return

    nft_items = db.get_nft_gift_rent()

    if not nft_items:
        text = "🏠 *Аренда NFT подарков*\n\nНет доступных NFT подарков для аренды."
        await message.answer(text, reply_markup=nft_categories_keyboard())
    else:
        text = "🏠 *Аренда NFT подарков*\n\nВыберите NFT подарок для аренды:"
        await message.answer(text, reply_markup=nft_categories_keyboard())

        for item in nft_items:
            item_text = f"""
📦 *{item['name']}*

🔗 Ссылка: {item['url']}
💰 Цена: {item['price_per_day']:.2f} руб/день

Нажмите кнопку ниже для аренды:"""

            keyboard = nft_gift_rent_keyboard(item['id'])
            await message.answer(item_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(F.text == "🎮 Покупка NFT юза")
async def nft_use_sale_cmd(message: types.Message):
    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=nft_categories_keyboard())
        return

    nft_items = db.get_nft_use_sale()

    if not nft_items:
        text = "🎮 *Покупка NFT юзов*\n\nНет доступных NFT юзов для покупки."
        await message.answer(text, reply_markup=nft_categories_keyboard())
    else:
        text = "🎮 *Покупка NFT юзов*\n\nВыберите NFT юз для покупки:"
        await message.answer(text, reply_markup=nft_categories_keyboard())

        for item in nft_items:
            item_text = f"""
📦 *{item['name']}*

🔗 Ссылка: {item['url']}
💰 Цена: {item['price']:.2f} руб

Нажмите кнопку ниже для покупки:"""

            keyboard = nft_use_sale_keyboard(item['id'])
            await message.answer(item_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(F.text == "⚡ Аренда NFT юза")
async def nft_use_rent_cmd(message: types.Message):
    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=nft_categories_keyboard())
        return

    nft_items = db.get_nft_use_rent()

    if not nft_items:
        text = "⚡ *Аренда NFT юзов*\n\nНет доступных NFT юзов для аренды."
        await message.answer(text, reply_markup=nft_categories_keyboard())
    else:
        text = "⚡ *Аренда NFT юзов*\n\nВыберите NFT юз для аренды:"
        await message.answer(text, reply_markup=nft_categories_keyboard())

        for item in nft_items:
            item_text = f"""
📦 *{item['name']}*

🔗 Ссылка: {item['url']}
💰 Цена: {item['price_per_day']:.2f} руб/день

Нажмите кнопку ниже для аренды:"""

            keyboard = nft_use_rent_keyboard(item['id'])
            await message.answer(item_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(F.text == "↩️ Назад")
async def back_cmd(message: types.Message):
    await start_cmd(message)


# ========== ПОПОЛНЕНИЕ БАЛАНСА ==========
@dp.message(F.text == "💰 Пополнить баланс")
async def add_balance_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Пользователь не найден!", reply_markup=back_to_menu_keyboard())
        return

    balance = user.get('balance', 0.0)

    text = f"""
💰 *Пополнение баланса*

📊 Ваш текущий баланс: *{balance:.2f} руб*
💰 Минимальное пополнение: *{MIN_PAYMENT} руб*

Введите сумму в рублях, которую хотите пополнить:"""

    await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_payment_amount)


# ========== ОБРАБОТКА ВВОДА ДАННЫХ ==========
@dp.message(OrderStates.waiting_calculator)
async def process_calculator(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        rub_amount = float(message.text)
        stars = rub_amount / STAR_PRICE
        rub_per_star = 1 / STAR_PRICE

        text = f"""
🧮 *Результат расчета:*

💰 {rub_amount:.2f} руб = {stars:.2f} ⭐️
⭐️ 1 руб = {rub_per_star:.3f} звезд
🌟 1 звезда = {STAR_PRICE:.2f} руб

Введите еще сумму в рублях или нажмите "В меню":"""

        await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_buy_amount)
async def process_buy_stars(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        stars_amount = float(message.text)

        if stars_amount < MIN_BUY_STARS:
            await message.answer(f"❌ Минимальная покупка {MIN_BUY_STARS} звезд!", reply_markup=back_to_menu_keyboard())
            return

        total_rub = stars_amount * STAR_PRICE

        text = f"""
⭐️ *Детали покупки:*

Количество: {stars_amount:.0f} ⭐️
Цена: {STAR_PRICE:.2f} руб за 1 звезду
Итого: {total_rub:.2f} руб

Введите @username получателя или 'себе' для покупки себе:"""

        await state.update_data(stars_amount=stars_amount, total_rub=total_rub)
        await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderStates.waiting_target_user)

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_target_user)
async def process_target_user(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    data = await state.get_data()
    stars_amount = data.get('stars_amount', 0)
    total_rub = data.get('total_rub', 0)

    target_user = message.text

    if target_user.lower() == 'себе':
        target_user = ""

    order_id = db.create_star_order(
        user_id=message.from_user.id,
        order_type="buy",
        amount=stars_amount,
        total_rub=total_rub,
        target_username=target_user
    )

    user = db.get_user(message.from_user.id)

    text = f"""
✅ *Заказ создан!*

🆔 Номер заказа: #{order_id}
⭐️ Количество: {stars_amount:.0f} звезд
💰 Сумма: {total_rub:.2f} руб
👤 Получатель: {'себе' if not target_user else target_user}
📊 Ваш баланс: {user['balance']:.2f} руб

Админ скоро обработает ваш заказ!"""

    # УВЕДОМЛЕНИЕ АДМИНУ О НОВОМ ЗАКАЗЕ
    admin_text = f"""
🆕 *Новый заказ на покупку звезд!*

🆔 Заказ: #{order_id}
👤 Пользователь: @{user['username']} (ID: {message.from_user.id})
⭐ Количество: {stars_amount:.0f} зв
💰 Сумма: {total_rub:.2f} руб
🎯 Получатель: {'себе' if not target_user else target_user}
📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}

Для обработки перейдите в "Админ панель" → "Просмотр заказов"."""

    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")

    await message.answer(text, reply_markup=main_menu_keyboard(message.from_user.id), parse_mode="Markdown")
    await state.clear()


@dp.message(OrderStates.waiting_sell_amount)
async def process_sell_stars(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        stars_amount = float(message.text)

        if stars_amount < MIN_SELL_STARS:
            await message.answer(f"❌ Минимальная продажа {MIN_SELL_STARS} звезд!", reply_markup=back_to_menu_keyboard())
            return

        total_rub = stars_amount * STAR_PRICE

        text = f"""
💎 *Детали продажи:*

Количество: {stars_amount:.0f} ⭐️
Цена: {STAR_PRICE:.2f} руб за 1 звезду
Итого к получению: {total_rub:.2f} руб

Заказ будет создан и отправлен админу на обработку."""

        order_id = db.create_star_order(
            user_id=message.from_user.id,
            order_type="sell",
            amount=stars_amount,
            total_rub=total_rub,
            target_username=""
        )

        user = db.get_user(message.from_user.id)

        text += f"""

✅ *Заказ создан!*

🆔 Номер заказа: #{order_id}
⭐️ Количество: {stars_amount:.0f} звезд
💰 К получению: {total_rub:.2f} руб
📊 Ваш баланс: {user['balance']:.2f} руб

Админ скоро создаст счет для оплаты!"""

        # УВЕДОМЛЕНИЕ АДМИНУ О НОВОМ ЗАКАЗЕ
        admin_text = f"""
🆕 *Новый заказ на продажу звезд!*

🆔 Заказ: #{order_id}
👤 Пользователь: @{user['username']} (ID: {message.from_user.id})
⭐ Количество: {stars_amount:.0f} зв
💰 К получению: {total_rub:.2f} руб
📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}

Для обработки перейдите в "Админ панель" → "Просмотр заказов"."""

        try:
            await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")

        await message.answer(text, reply_markup=main_menu_keyboard(message.from_user.id), parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_payment_amount)
async def process_payment_amount(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        amount = float(message.text)

        if amount < MIN_PAYMENT:
            await message.answer(f"❌ Минимальная сумма пополнения {MIN_PAYMENT} рублей!",
                                 reply_markup=back_to_menu_keyboard())
            return

        await state.update_data(payment_amount=amount)

        text = f"""
💰 *Сумма к пополнению:* {amount:.2f} руб

Выберите способ оплаты:"""

        await message.answer(text, reply_markup=payment_methods_keyboard(), parse_mode="Markdown")
        await state.set_state(OrderStates.waiting_payment_method)

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число.",
                             reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_payment_method)
async def process_payment_method(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    if message.text == "↩️ Назад к сумме":
        await add_balance_cmd(message, state)
        return

    user_id = message.from_user.id
    user = db.get_user(user_id)

    data = await state.get_data()
    amount = data.get('payment_amount', 0)

    if amount == 0:
        await message.answer("❌ Ошибка получения суммы!", reply_markup=back_to_menu_keyboard())
        await state.clear()
        return

    if message.text == "💳 Перевод на карту":
        text = f"""
💳 *Перевод на карту*

💰 *Сумма к оплате:* {amount:.2f} руб

📋 *Реквизиты для оплаты:*
🔹 Банк: Ozon
🔹 Номер карты: `2204320607305531`
🔸 Получатель: Дмитрий Ф.

📝 *Инструкция:*
1. Переведите *{amount:.2f} руб* на указанную карту
2. Сделайте скриншот чека об оплате
3. Отправьте скриншот в этот чат

*После отправки скриншота админ проверит платеж и пополнит ваш баланс.*"""

        await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
        await state.clear()

    elif message.text == "₿ Криптовалюта":
        text = f"""
₿ *Оплата криптовалютой*

💰 *Сумма к оплате:* {amount:.2f} руб

📋 *Ссылка для оплаты:*
👉 [Оплатить через CryptoBot](http://t.me/send?start=IVcSJGoqKwkK)

📝 *Инструкция:*
1. Перейдите по ссылке выше
2. Оплатите *{amount:.2f} руб* в USDT/TON
3. Сделайте скриншот подтверждения оплаты
4. Отправьте скриншот в этот чат

*После отправки скриншота админ проверит платеж и пополнит ваш баланс.*"""

        await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown",
                             disable_web_page_preview=True)
        await state.clear()

    else:
        await message.answer("❌ Выберите способ оплаты из предложенных!",
                             reply_markup=payment_methods_keyboard())


# ========== ОБРАБОТКА ФОТО И ДОКУМЕНТОВ ==========
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Пользователь не найден!", reply_markup=back_to_menu_keyboard())
        return

    chat_history = await bot.get_chat_history(message.chat.id, limit=15)
    amount = 0
    payment_method = "unknown"

    async for msg in chat_history:
        if msg.text and "Сумма к оплате:" in msg.text:
            match = re.search(r"Сумма к оплате:\s*\*\*([\d\.]+)", msg.text)
            if match:
                try:
                    amount = float(match.group(1))
                    # Определяем метод оплаты по тексту сообщения
                    if "Перевод на карту" in msg.text:
                        payment_method = "bank_transfer"
                    elif "Криптовалюта" in msg.text or "CryptoBot" in msg.text or "USDT" in msg.text or "TON" in msg.text:
                        payment_method = "crypto"
                    break
                except ValueError:
                    pass

    if amount == 0:
        await message.answer("❌ Не найдена информация о платеже! Сначала выберите сумму пополнения.",
                             reply_markup=back_to_menu_keyboard())
        return

    method_name = "перевод на карту" if payment_method == "bank_transfer" else "криптовалюта"

    payment_id = db.create_payment(
        user_id=user_id,
        amount=amount,
        method=payment_method,
        proof=f"Скриншот оплаты {method_name} на {amount} руб"
    )

    text = f"✅ Скриншот платежа ({method_name}) отправлен админу на проверку!\n\n💰 Баланс будет пополнен после подтверждения администратором."
    await message.answer(text, reply_markup=back_to_menu_keyboard())

    admin_text = f"""
📎 *Новый скриншот платежа*

🆔 Платеж: #{payment_id}
👤 *От кого:* @{user['username']}
🆔 ID пользователя: `{user_id}`
💳 Способ оплаты: {method_name}
💰 Сумма: {amount:.2f} руб
💰 Текущий баланс: {user['balance']:.2f} руб

📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"""

    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
        await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        keyboard = confirm_payment_keyboard(payment_id)
        confirm_text = f"Подтвердить платеж #{payment_id} от @{user['username']} на сумму {amount:.2f} руб?"
        await bot.send_message(ADMIN_ID, confirm_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")


@dp.message(F.document)
async def handle_document(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Пользователь не найден!", reply_markup=back_to_menu_keyboard())
        return

    chat_history = await bot.get_chat_history(message.chat.id, limit=15)
    amount = 0
    payment_method = "unknown"

    async for msg in chat_history:
        if msg.text and "Сумма к оплате:" in msg.text:
            match = re.search(r"Сумма к оплате:\s*\*\*([\d\.]+)", msg.text)
            if match:
                try:
                    amount = float(match.group(1))
                    # Определяем метод оплаты по тексту сообщения
                    if "Перевод на карту" in msg.text:
                        payment_method = "bank_transfer"
                    elif "Криптовалюта" in msg.text or "CryptoBot" in msg.text or "USDT" in msg.text or "TON" in msg.text:
                        payment_method = "crypto"
                    break
                except ValueError:
                    pass

    if amount == 0:
        await message.answer("❌ Не найдена информация о платеже! Сначала выберите сумму пополнения.",
                             reply_markup=back_to_menu_keyboard())
        return

    method_name = "перевод на карту" if payment_method == "bank_transfer" else "криптовалюта"

    payment_id = db.create_payment(
        user_id=user_id,
        amount=amount,
        method=payment_method,
        proof=f"Документ оплаты {method_name} на {amount} руб"
    )

    text = f"✅ Документ платежа ({method_name}) отправлен админу на проверку!\n\n💰 Баланс будет пополнен после подтверждения администратором."
    await message.answer(text, reply_markup=back_to_menu_keyboard())

    admin_text = f"""
📎 *Новый документ платежа*

🆔 Платеж: #{payment_id}
👤 *От кого:* @{user['username']}
🆔 ID пользователя: `{user_id}`
💳 Способ оплаты: {method_name}
💰 Сумма: {amount:.2f} руб
💰 Текущий баланс: {user['balance']:.2f} руб

📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"""

    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
        await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        keyboard = confirm_payment_keyboard(payment_id)
        confirm_text = f"Подтвердить платеж #{payment_id} от @{user['username']} на сумму {amount:.2f} руб?"
        await bot.send_message(ADMIN_ID, confirm_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")


# ========== АДМИН ПАНЕЛЬ ==========
@dp.message(F.text == "🔧 Админ панель")
async def admin_panel_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    text = "🔧 *Админ панель*\n\nВыберите действие:"
    await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")


@dp.message(F.text == "📋 Просмотр заказов")
async def view_orders_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=back_to_menu_keyboard())
        return

    orders = db.get_pending_orders()

    if not orders:
        text = "📭 *Ожидающие заказы*\n\nНет ожидающих заказов."
        await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
    else:
        for order in orders:
            text = f"""
🆔 *Заказ #{order['id']}*

👤 Пользователь: @{order['username']}
📊 Тип: {order['order_type']}
⭐ Количество: {order['amount']} зв
💰 Сумма: {order['total_rub']:.2f} руб"""

            if order['target_username']:
                text += f"\n🎯 Получатель: @{order['target_username']}"

            text += f"\n📅 Дата: {order['created_at'][:16]}"
            text += f"\nСтатус: {order['status']}"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_order_{order['id']}")]
            ])

            await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(F.text == "💰 Платежи на проверку")
async def view_payments_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=back_to_menu_keyboard())
        return

    payments = db.get_pending_payments()

    if not payments:
        text = "💰 *Платежи на проверку*\n\nНет платежей на проверку."
        await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
    else:
        for payment in payments:
            method_name = "перевод на карту" if payment['method'] == "bank_transfer" else "криптовалюта" if payment[
                                                                                                                'method'] == "crypto" else \
            payment['method']
            proof_text = payment['proof_text'][:100].replace('*', '').replace('_', '').replace('`', '') if payment[
                'proof_text'] else ""

            text = f"""💰 *Платеж #{payment['id']}*

👤 *От кого:* @{payment['username']}
🆔 ID пользователя: `{payment['user_id']}`
💳 Метод: {method_name}
💰 Сумма: {payment['amount']:.2f} руб
📅 Дата: {payment['created_at'][:16]}
📎 Комментарий: {proof_text}..."""

            keyboard = confirm_payment_keyboard(payment['id'])
            await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


# ========== РАССЫЛКА ==========
@dp.message(F.text == "📢 Рассылка")
async def broadcast_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    await message.answer("📢 *Рассылка сообщений*\n\nВведите сообщение для рассылки всем пользователям:",
                         reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_broadcast_message)


@dp.message(OrderStates.waiting_broadcast_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    broadcast_text = message.text
    users = db.get_all_users()

    keyboard = confirm_broadcast_keyboard()

    await message.answer(
        f"📢 *Предпросмотр рассылки:*\n\n{broadcast_text}\n\nКоличество пользователей: {len(users)}\n\nПодтвердить отправку?",
        reply_markup=keyboard, parse_mode="Markdown")
    await state.update_data(broadcast_text=broadcast_text)


# ========== ДОБАВЛЕНИЕ NFT ==========
@dp.message(F.text == "🎁 NFT подарок в продажу")
async def add_nft_gift_sale_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    await message.answer("Введите название NFT подарка для продажи:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_gift_sale_name)


@dp.message(F.text == "🏠 NFT подарок в аренду")
async def add_nft_gift_rent_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    await message.answer("Введите название NFT подарка для аренды:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_gift_rent_name)


@dp.message(F.text == "🎮 NFT юз в продажу")
async def add_nft_use_sale_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    await message.answer("Введите название NFT юза для продажи:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_use_sale_name)


@dp.message(F.text == "⚡ NFT юз в аренду")
async def add_nft_use_rent_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    await message.answer("Введите название NFT юза для аренды:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_use_rent_name)


# Обработчики для добавления NFT
@dp.message(OrderStates.waiting_gift_sale_name)
async def process_gift_sale_name(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(gift_sale_name=message.text)
    await message.answer("Введите ссылку на NFT подарок:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_gift_sale_url)


@dp.message(OrderStates.waiting_gift_sale_url)
async def process_gift_sale_url(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(gift_sale_url=message.text)
    await message.answer("Введите цену NFT подарка в рублях:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_gift_sale_price)


@dp.message(OrderStates.waiting_gift_sale_price)
async def process_gift_sale_price(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        price = float(message.text)
        data = await state.get_data()
        name = data.get('gift_sale_name')
        url = data.get('gift_sale_url')

        if not name or not url:
            await message.answer("❌ Ошибка получения данных!", reply_markup=back_to_menu_keyboard())
            await state.clear()
            return

        db.add_nft_gift_sale(name, url, price)

        text = f"""
✅ NFT подарок добавлен в продажу!

📦 Название: {name}
🔗 Ссылка: {url}
💰 Цена: {price:.2f} руб"""

        await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_gift_rent_name)
async def process_gift_rent_name(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(gift_rent_name=message.text)
    await message.answer("Введите ссылку на NFT подарок для аренды:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_gift_rent_url)


@dp.message(OrderStates.waiting_gift_rent_url)
async def process_gift_rent_url(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(gift_rent_url=message.text)
    await message.answer("Введите цену аренды NFT подарка за день в рублях:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_gift_rent_price)


@dp.message(OrderStates.waiting_gift_rent_price)
async def process_gift_rent_price(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        price = float(message.text)
        data = await state.get_data()
        name = data.get('gift_rent_name')
        url = data.get('gift_rent_url')

        if not name or not url:
            await message.answer("❌ Ошибка получения данных!", reply_markup=back_to_menu_keyboard())
            await state.clear()
            return

        db.add_nft_gift_rent(name, url, price)

        text = f"""
✅ NFT подарок добавлен в аренду!

📦 Название: {name}
🔗 Ссылка: {url}
💰 Цена за день: {price:.2f} руб"""

        await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_use_sale_name)
async def process_use_sale_name(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(use_sale_name=message.text)
    await message.answer("Введите ссылку на NFT юз:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_use_sale_url)


@dp.message(OrderStates.waiting_use_sale_url)
async def process_use_sale_url(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(use_sale_url=message.text)
    await message.answer("Введите цену NFT юза в рублях:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_use_sale_price)


@dp.message(OrderStates.waiting_use_sale_price)
async def process_use_sale_price(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        price = float(message.text)
        data = await state.get_data()
        name = data.get('use_sale_name')
        url = data.get('use_sale_url')

        if not name or not url:
            await message.answer("❌ Ошибка получения данных!", reply_markup=back_to_menu_keyboard())
            await state.clear()
            return

        db.add_nft_use_sale(name, url, price)

        text = f"""
✅ NFT юз добавлен в продажу!

📦 Название: {name}
🔗 Ссылка: {url}
💰 Цена: {price:.2f} руб"""

        await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_use_rent_name)
async def process_use_rent_name(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(use_rent_name=message.text)
    await message.answer("Введите ссылку на NFT юз для аренды:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_use_rent_url)


@dp.message(OrderStates.waiting_use_rent_url)
async def process_use_rent_url(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    await state.update_data(use_rent_url=message.text)
    await message.answer("Введите цену аренды NFT юза за день в рублях:", reply_markup=back_to_menu_keyboard())
    await state.set_state(OrderStates.waiting_use_rent_price)


@dp.message(OrderStates.waiting_use_rent_price)
async def process_use_rent_price(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        price = float(message.text)
        data = await state.get_data()
        name = data.get('use_rent_name')
        url = data.get('use_rent_url')

        if not name or not url:
            await message.answer("❌ Ошибка получения данных!", reply_markup=back_to_menu_keyboard())
            await state.clear()
            return

        db.add_nft_use_rent(name, url, price)

        text = f"""
✅ NFT юз добавлен в аренду!

📦 Название: {name}
🔗 Ссылка: {url}
💰 Цена за день: {price:.2f} руб"""

        await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:", reply_markup=back_to_menu_keyboard())


# ========== УДАЛЕНИЕ NFT ==========
@dp.message(F.text == "🗑️ Удаление NFT")
async def delete_nft_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен!", reply_markup=back_to_menu_keyboard())
        return

    if not db:
        await message.answer("❌ Ошибка базы данных!", reply_markup=back_to_menu_keyboard())
        return

    text = "🗑️ *Удаление NFT*\n\nВыберите категорию для удаления:"
    keyboard = delete_nft_menu_keyboard()
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


# ========== ОБРАБОТКА АРЕНДЫ NFT ==========
@dp.message(OrderStates.waiting_gift_rent_days)
async def process_gift_rent_days(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        days = int(message.text)

        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0!", reply_markup=back_to_menu_keyboard())
            return

        data = await state.get_data()
        nft_id = data.get('rent_gift_id')

        if not nft_id:
            await message.answer("❌ Ошибка получения NFT!", reply_markup=back_to_menu_keyboard())
            await state.clear()
            return

        success, message_text = db.rent_nft_gift(message.from_user.id, nft_id, days)

        if success:
            user = db.get_user(message.from_user.id)
            text = f"""
✅ {message_text}

💰 Новый баланс: {user['balance']:.2f} руб"""
            await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
        else:
            await message.answer(message_text, reply_markup=back_to_menu_keyboard())

        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите целое число дней:", reply_markup=back_to_menu_keyboard())


@dp.message(OrderStates.waiting_use_rent_days)
async def process_use_rent_days(message: types.Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await start_cmd(message)
        await state.clear()
        return

    try:
        days = int(message.text)

        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0!", reply_markup=back_to_menu_keyboard())
            return

        data = await state.get_data()
        nft_id = data.get('rent_use_id')

        if not nft_id:
            await message.answer("❌ Ошибка получения NFT!", reply_markup=back_to_menu_keyboard())
            await state.clear()
            return

        success, message_text = db.rent_nft_use(message.from_user.id, nft_id, days)

        if success:
            user = db.get_user(message.from_user.id)
            text = f"""
✅ {message_text}

💰 Новый баланс: {user['balance']:.2f} руб"""
            await message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
        else:
            await message.answer(message_text, reply_markup=back_to_menu_keyboard())

        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите целое число дней:", reply_markup=back_to_menu_keyboard())


# ========== CALLBACK ОБРАБОТЧИКИ ==========
@dp.callback_query(F.data.startswith("buy_gift_sale_"))
async def callback_buy_gift_sale(callback: types.CallbackQuery):
    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("buy_gift_sale_", ""))
        user_id = callback.from_user.id

        success, message_text = db.buy_nft_gift_sale(user_id, nft_id)
        await callback.answer(message_text, show_alert=True)

        if success:
            user = db.get_user(user_id)
            balance = user.get('balance', 0.0)
            await callback.message.answer(f"✅ Успешно!\n\n💰 Новый баланс: {balance:.2f} руб",
                                          reply_markup=back_to_menu_keyboard())
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("rent_gift_"))
async def callback_rent_gift(callback: types.CallbackQuery, state: FSMContext):
    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("rent_gift_", ""))
        await state.update_data(rent_gift_id=nft_id)
        await callback.message.answer("На сколько дней арендуем NFT подарок? (Введите число):",
                                      reply_markup=back_to_menu_keyboard())
        await state.set_state(OrderStates.waiting_gift_rent_days)
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_use_sale_"))
async def callback_buy_use_sale(callback: types.CallbackQuery):
    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("buy_use_sale_", ""))
        user_id = callback.from_user.id

        success, message_text = db.buy_nft_use_sale(user_id, nft_id)
        await callback.answer(message_text, show_alert=True)

        if success:
            user = db.get_user(user_id)
            balance = user.get('balance', 0.0)
            await callback.message.answer(f"✅ Успешно!\n\n💰 Новый баланс: {balance:.2f} руб",
                                          reply_markup=back_to_menu_keyboard())
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("rent_use_"))
async def callback_rent_use(callback: types.CallbackQuery, state: FSMContext):
    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("rent_use_", ""))
        await state.update_data(rent_use_id=nft_id)
        await callback.message.answer("На сколько дней арендуем NFT юз? (Введите число):",
                                      reply_markup=back_to_menu_keyboard())
        await state.set_state(OrderStates.waiting_use_rent_days)
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data == "back_to_nft_categories")
async def callback_back_to_nft_categories(callback: types.CallbackQuery):
    await callback.message.delete()
    await nft_shop_cmd(callback.message)


@dp.callback_query(F.data == "back_to_admin")
async def callback_back_to_admin(callback: types.CallbackQuery):
    await callback.message.delete()
    await admin_panel_cmd(callback.message)


@dp.callback_query(F.data.startswith("admin_confirm_order_"))
async def callback_admin_confirm_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        order_id = int(callback.data.replace("admin_confirm_order_", ""))

        cursor = db.conn.cursor()
        cursor.execute('''
                       SELECT so.*, u.username, u.balance
                       FROM star_orders so
                                JOIN users u ON so.user_id = u.user_id
                       WHERE so.id = ?
                       ''', (order_id,))
        order = cursor.fetchone()

        if not order:
            await callback.answer("❌ Заказ не найден!", show_alert=True)
            return

        order = dict(order)

        if order['order_type'] == 'buy':
            text = "✅ Заказ на покупку звезд подтвержден!"

        elif order['order_type'] == 'sell':
            amount = order['total_rub']
            user_id = order['user_id']

            db.update_balance(user_id, amount)

            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            new_balance = user['balance'] if user else 0

            text = f"✅ Заказ на продажу звезд подтвержден!\n\n💰 Пользователю начислено: {amount:.2f} руб\n💰 Новый баланс: {new_balance:.2f} руб"

            user_notification = f"""
✅ *Заказ #{order_id} подтвержден!*

💎 Продажа звезд: {order['amount']:.0f} ⭐️
💰 Начислено: {amount:.2f} руб
💰 Ваш новый баланс: {new_balance:.2f} руб

Спасибо за продажу!"""

            try:
                await bot.send_message(user_id, user_notification, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю: {e}")

        db.complete_order(order_id)

        await callback.answer(text, show_alert=True)
        await callback.message.delete()

    except ValueError:
        await callback.answer("❌ Ошибка!", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка подтверждения заказа: {e}")
        await callback.answer("❌ Ошибка обработки заказа!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_payment_"))
async def callback_confirm_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        payment_id = int(callback.data.replace("confirm_payment_", ""))
        if db.confirm_payment(payment_id):
            cursor = db.conn.cursor()
            cursor.execute('''
                           SELECT p.*, u.username, u.balance
                           FROM payments p
                                    JOIN users u ON p.user_id = u.user_id
                           WHERE p.id = ?
                           ''', (payment_id,))
            payment = cursor.fetchone()

            if payment:
                payment = dict(payment)
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (payment['user_id'],))
                updated_user = cursor.fetchone()
                new_balance = updated_user['balance'] if updated_user else 0

                user_text = f"""✅ *Платеж подтвержден!*

💰 Сумма: {payment['amount']:.2f} руб
💰 Новый баланс: {new_balance:.2f} руб

🆔 Номер платежа: #{payment_id}

Спасибо за оплату!"""

                try:
                    await bot.send_message(payment['user_id'], user_text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Ошибка отправки пользователю: {e}")

            await callback.answer(f"✅ Платеж #{payment_id} подтвержден!", show_alert=True)
            await callback.message.delete()
        else:
            await callback.answer("❌ Ошибка подтверждения!", show_alert=True)
    except ValueError:
        await callback.answer("❌ Ошибка!", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка подтверждения платежа: {e}")
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("reject_payment_"))
async def callback_reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    try:
        payment_id = int(callback.data.replace("reject_payment_", ""))

        cursor = db.conn.cursor()
        cursor.execute('''
                       SELECT p.*, u.username
                       FROM payments p
                                JOIN users u ON p.user_id = u.user_id
                       WHERE p.id = ?
                       ''', (payment_id,))
        payment = cursor.fetchone()

        if payment:
            payment = dict(payment)
            db.reject_payment(payment_id)

            user_text = f"""
❌ *Платеж отклонен!*

💰 Сумма: {payment['amount']:.2f} руб
🆔 Номер платежа: #{payment_id}

⚠️ Платеж был отклонен администратором.
Если вы считаете это ошибкой, свяжитесь с поддержкой."""

            try:
                await bot.send_message(payment['user_id'], user_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю: {e}")

        await callback.answer(f"❌ Платеж #{payment_id} отклонен!", show_alert=True)
        await callback.message.delete()
    except ValueError:
        await callback.answer("❌ Ошибка!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data == "confirm_broadcast")
async def callback_confirm_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    data = await state.get_data()
    broadcast_text = data.get('broadcast_text', '')

    if not broadcast_text:
        await callback.answer("❌ Текст рассылки не найден!", show_alert=True)
        await state.clear()
        return

    users = db.get_all_users()

    total_users = len(users)
    successful = 0
    failed = 0

    await callback.message.edit_text(f"📢 *Рассылка начата...*\n\nОтправка {total_users} пользователям...",
                                     parse_mode="Markdown")

    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 *Сообщение от администратора:*\n\n{broadcast_text}",
                                   parse_mode="Markdown")
            successful += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")

    result_text = f"""📢 *Рассылка завершена!*

✅ Успешно отправлено: {successful}
❌ Не отправлено: {failed}
👥 Всего пользователей: {total_users}"""

    await callback.message.edit_text(result_text, parse_mode="Markdown")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "cancel_broadcast")
async def callback_cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Рассылка отменена.")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_gift_sale_"))
async def callback_delete_gift_sale(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("delete_gift_sale_", ""))
        db.delete_nft_gift_sale(nft_id)
        await callback.answer("✅ NFT подарок в продаже удален!", show_alert=True)
        await delete_gift_sale_menu(callback)
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_gift_rent_"))
async def callback_delete_gift_rent(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("delete_gift_rent_", ""))
        db.delete_nft_gift_rent(nft_id)
        await callback.answer("✅ NFT подарок в аренде удален!", show_alert=True)
        await delete_gift_rent_menu(callback)
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_use_sale_"))
async def callback_delete_use_sale(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("delete_use_sale_", ""))
        db.delete_nft_use_sale(nft_id)
        await callback.answer("✅ NFT юз в продаже удален!", show_alert=True)
        await delete_use_sale_menu(callback)
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_use_rent_"))
async def callback_delete_use_rent(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if not db:
        await callback.answer("❌ Ошибка базы данных!", show_alert=True)
        return

    try:
        nft_id = int(callback.data.replace("delete_use_rent_", ""))
        db.delete_nft_use_rent(nft_id)
        await callback.answer("✅ NFT юз в аренде удален!", show_alert=True)
        await delete_use_rent_menu(callback)
    except ValueError:
        await callback.answer("❌ Ошибка обработки!", show_alert=True)
    await callback.answer()


@dp.callback_query(F.data == "delete_gift_sale_menu")
async def delete_gift_sale_menu(callback: types.CallbackQuery):
    nfts = db.get_nft_gift_sale_list()

    if not nfts:
        await callback.answer("❌ Нет NFT подарков в продаже для удаления!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for nft in nfts:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ {nft['name']}",
                callback_data=f"delete_gift_sale_{nft['id']}"
            )
        ])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_delete_menu")])

    await callback.message.edit_text("🗑️ *Удалить NFT подарок в продаже*\n\nВыберите NFT для удаления:",
                                     reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "delete_gift_rent_menu")
async def delete_gift_rent_menu(callback: types.CallbackQuery):
    nfts = db.get_nft_gift_rent_list()

    if not nfts:
        await callback.answer("❌ Нет NFT подарков в аренде для удаления!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for nft in nfts:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ {nft['name']}",
                callback_data=f"delete_gift_rent_{nft['id']}"
            )
        ])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_delete_menu")])

    await callback.message.edit_text("🗑️ *Удалить NFT подарок в аренде*\n\nВыберите NFT для удаления:",
                                     reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "delete_use_sale_menu")
async def delete_use_sale_menu(callback: types.CallbackQuery):
    nfts = db.get_nft_use_sale_list()

    if not nfts:
        await callback.answer("❌ Нет NFT юзов в продаже для удаления!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for nft in nfts:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ {nft['name']}",
                callback_data=f"delete_use_sale_{nft['id']}"
            )
        ])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_delete_menu")])

    await callback.message.edit_text("🗑️ *Удалить NFT юз в продаже*\n\nВыберите NFT для удаления:",
                                     reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "delete_use_rent_menu")
async def delete_use_rent_menu(callback: types.CallbackQuery):
    nfts = db.get_nft_use_rent_list()

    if not nfts:
        await callback.answer("❌ Нет NFT юзов в аренде для удаления!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for nft in nfts:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ {nft['name']}",
                callback_data=f"delete_use_rent_{nft['id']}"
            )
        ])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_delete_menu")])

    await callback.message.edit_text("🗑️ *Удалить NFT юз в аренде*\n\nВыберите NFT для удаления:",
                                     reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "back_to_delete_menu")
async def back_to_delete_menu(callback: types.CallbackQuery):
    text = "🗑️ *Удаление NFT*\n\nВыберите категорию для удаления:"
    keyboard = delete_nft_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# ========== ЗАПУСК ==========
async def main():
    print("=" * 50)
    print("🤖 Harnel.M Shop Bot")
    print("=" * 50)

    print(f"\n✅ Токен: {BOT_TOKEN[:10]}...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"⭐ Курс: 1 звезда = {STAR_PRICE} руб")
    print(f"📊 Мин. покупка: {MIN_BUY_STARS} зв")
    print(f"📊 Мин. продажа: {MIN_SELL_STARS} зв")
    print(f"💰 Мин. пополнение: {MIN_PAYMENT} руб")
    print("\n🚀 Бот запускается...")
    print("=" * 50)

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())
