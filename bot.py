
import os
import threading
import sqlite3
import asyncio
from datetime import datetime, timedelta
from collections import Counter



from flask import Flask

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")



ADMIN_IDS = [1288830602]
ADMIN_PASSWORD = "876543210"

MASTER_INFO = {
    "Артем": {
        "photo": "https://i.postimg.cc/YSrWb0Lc/barber-artem.jpg",
        "description": "👤 Артем\n💈 Барбер\n⭐️ Досвід: 5 років\n✂️ Спеціалізація: стрижки, fade, борода"
    },
    "Даня": {
        "photo": "https://i.postimg.cc/1Rfd5cRk/barber-dan.jpg",
        "description": "👤 Даня\n💈 Барбер\n⭐️ Досвід: 3 роки\n✂️ Спеціалізація: чоловічі стрижки, борода"
    },
    "Максим": {
        "photo": "https://i.postimg.cc/YCwD356J/barber-max.jpg",
        "description": "👤 Максим\n💈 Барбер\n⭐️ Досвід: 4 роки\n✂️ Спеціалізація: класика, fade"
    },
}

DB_FILE = "barbershop.db"

NAME, SERVICE, MASTER, DAY, TIME, COMMENT, CONFIRM, RESCHEDULE_DAY, RESCHEDULE_TIME, CONTACT_ADMIN, ADMIN_REPLY, ADMIN_CANCEL_COMMENT = range(12)



def kb(buttons):
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def back_kb(buttons):
    return ReplyKeyboardMarkup(buttons + [["⬅️ Назад"]], resize_keyboard=True)


def main_menu_kb():
    return kb([
        ["🚀 Почати"],
        ["📝 Записатися"],
        ["📋 Мої записи"],
        ["💬 Зв'язатися з адміністратором"],
        ["📞 Контакти"]
    ])


def admin_kb():
    return kb([
        ["📋 Список записів", "📊 Аналітика"],
        ["🕒 Заняті слоти"],
        ["❌ Видалити запис", "🧹 Очистити все"],
        ["⚙️ Налаштування"],
        ["🚪 Вийти з адмінки"],
    ])

def contacts_kb():
    return kb([
        ["📍 Адреса"],
        ["📞 Зателефонувати"],
        ["🌐 Соціальні мережі"],
        ["⬅️ Назад в меню"]
    ])

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    service TEXT,
    master TEXT,
    date TEXT,
    time TEXT,
    comment TEXT,
    reminded INTEGER DEFAULT 0
)
""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        price TEXT,
        duration TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS masters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master TEXT,
    date TEXT,
    time TEXT
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

    default_settings = {
    "phone": "+380 99 123 45 67",
    "address": "м. Київ, вул. Прикладна 10",
    "socials": "Instagram: @your_barbershop\nFacebook: -\nTikTok: -\nTelegram: -"
}

    for key, value in default_settings.items():
        cur.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )

    cur.execute("SELECT COUNT(*) FROM masters")
    masters_count = cur.fetchone()[0]

    if masters_count == 0:
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Артем",))
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Даня",))
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Максим",))

    cur.execute("SELECT COUNT(*) FROM services")
    services_count = cur.fetchone()[0]

    if services_count == 0:
        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Стрижка", "500 грн", "45 хв")
        )
        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Борода", "300 грн", "30 хв")
        )
        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Стрижка + борода", "700 грн", "60 хв")
        )

    cur.execute("SELECT COUNT(*) FROM schedule")
    schedule_count = cur.fetchone()[0]

    if schedule_count == 0:
        today = datetime.now()

        default_schedule = []

        for i in range(14):
            current_date = today + timedelta(days=i)

            date_str = current_date.strftime("%d.%m.%Y")

            default_schedule.append(("Артем", date_str, "10:00"))
            default_schedule.append(("Артем", date_str, "12:00"))

            default_schedule.append(("Даня", date_str, "11:00"))
            default_schedule.append(("Даня", date_str, "13:00"))

            default_schedule.append(("Максим", date_str, "14:00"))
            default_schedule.append(("Максим", date_str, "16:00"))

        cur.executemany(
            "INSERT INTO schedule (master, date, time) VALUES (?, ?, ?)",
            default_schedule
        )
    try:
        cur.execute("ALTER TABLE appointments ADD COLUMN comment TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def get_all_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, name, service, master, date, time, comment FROM appointments ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_records(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, name, service, master, date, time, comment FROM appointments WHERE user_id=? ORDER BY id",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, name, service, master, date, time, comment
        FROM appointments
        WHERE id=?
        """,
        (record_id,)
    )

    row = cur.fetchone()

    conn.close()
    return row

def add_record(user_id, name, service, master, date, time, comment):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO appointments 
        (user_id, name, service, master, date, time, comment, reminded) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, service, master, date, time, comment, 0)
    )

    conn.commit()
    conn.close()





def update_record_time(record_id, date, time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET date=?, time=?, reminded=0 WHERE id=?",
        (date, time, record_id)
    )
    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
def mark_reminded(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "UPDATE appointments SET reminded=1 WHERE id=?",
        (record_id,)
    )

    conn.commit()
    conn.close()


def get_unreminded_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, name, service, master, date, time, comment 
        FROM appointments 
        WHERE reminded=0
        """
    )

    rows = cur.fetchall()
    conn.close()

    return rows

def clear_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments")
    conn.commit()
    conn.close()

def delete_old_records():
    records = get_all_records()
    now = datetime.now()

    for record in records:
        record_id, user_id, name, service, master, date, time, comment = record

        try:
            record_datetime = get_next_record_datetime(date, time)
        except ValueError:
            continue

        if record_datetime < now:
            delete_record(record_id)

def delete_old_schedule():
    schedule = get_schedule()
    now = datetime.now()

    for item in schedule:
        schedule_id, master, date, time = item

        try:
            schedule_datetime = get_next_record_datetime(date, time)
        except ValueError:
            continue

        if schedule_datetime < now:
            delete_schedule(schedule_id)

def get_services():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT id, name, price, duration FROM services ORDER BY id")
    rows = cur.fetchall()

    conn.close()
    return rows


def add_service(name, price, duration):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO services (name, price, duration) VALUES (?, ?, ?)",
        (name, price, duration)
    )

    conn.commit()
    conn.close()


def delete_service(service_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("DELETE FROM services WHERE id=?", (service_id,))

    conn.commit()
    conn.close()

def get_masters():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM masters ORDER BY id")
    rows = cur.fetchall()

    conn.close()
    return rows


def add_master(name):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO masters (name) VALUES (?)",
        (name,)
    )

    conn.commit()
    conn.close()


def delete_master(master_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("DELETE FROM masters WHERE id=?", (master_id,))

    conn.commit()
    conn.close()

def get_schedule():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, master, date, time FROM schedule ORDER BY master, date, time"
    )

    rows = cur.fetchall()

    conn.close()
    return rows


def add_schedule(master, day, time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO schedule (master, date, time) VALUES (?, ?, ?)",
        (master, day, time)
    )

    conn.commit()
    conn.close()


def delete_schedule(schedule_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM schedule WHERE id=?",
        (schedule_id,)
    )

    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()

    conn.close()

    return row[0] if row else ""


def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )

    conn.commit()
    conn.close()

def get_master_dates_from_db(master):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT DISTINCT date FROM schedule WHERE master=? ORDER BY date",
        (master,)
    )

    rows = cur.fetchall()

    conn.close()

    return [row[0] for row in rows]

def get_master_times_from_db(master, day):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT time FROM schedule WHERE master=? AND date=? ORDER BY time",
        (master, day)
    )

    rows = cur.fetchall()

    conn.close()

    return [row[0] for row in rows]

def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_admin_logged(context):
    return context.user_data.get("admin_logged") is True

def settings_kb():
    return kb([
        ["💈 Послуги"],
        ["👤 Майстри"],
        ["📅 Розклад"],
        ["⬅️ Назад"]
    ])

def get_free_times(master, day, exclude_id=None):
    all_times = get_master_times_from_db(master, day)
    records = get_all_records()

    busy = []

    for record in records:
        record_id, _, _, _, rec_master, rec_day, rec_time, comment = record

        if exclude_id is not None and record_id == exclude_id:
            continue

        if rec_master == master and rec_day == day:
            busy.append(rec_time)

    return [t for t in all_times if t not in busy]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    print(f"NEW USER: {update.message.from_user.full_name} | ID: {user_id}")
    
    if is_admin(user_id):
        if is_admin_logged(context):
            await update.message.reply_text(
                "⚙️ Адмін-панель:",
                reply_markup=admin_kb()
            )
        else:
            context.user_data["waiting_password"] = True

            await update.message.reply_text(
                "Введіть пароль адміністратора:"
            )

        return
    

    
    await update.message.reply_text(
        "Привіт! Обери дію:",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END

async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Обери потрібний розділ:",
        reply_markup=contacts_kb()
    )


async def contact_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📍 Адреса":
        await update.message.reply_text(
            f"📍 Адреса:\n{get_setting('address')}"
        )

    elif text == "📞 Зателефонувати":
        await update.message.reply_text(
            f"📞 Телефон:\n{get_setting('phone')}"
        )

    elif text == "🌐 Соцмережі":
        await update.message.reply_text(
            f"🌐 Соцмережі:\n{get_setting('socials')}"
        )

    elif text == "⬅️ Назад в меню":
        if is_admin(update.message.from_user.id) and is_admin_logged(context):
            await update.message.reply_text(
                "⚙️ Адмін-панель:",
                reply_markup=admin_kb()
            )
        else:
            await update.message.reply_text(
                "Головне меню:",
                reply_markup=main_menu_kb()
            )

async def begin_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Введіть своє ім'я:",
        reply_markup=back_kb([])
    )

    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Головне меню:",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END

    context.user_data["name"] = update.message.text

    services = get_services()

    if not services:
        await update.message.reply_text("Поки немає доступних послуг.")
        return ConversationHandler.END

    keyboard = [[service[1]] for service in services]

    await update.message.reply_text(
        "Обери послугу:",
        reply_markup=back_kb(keyboard)
    )

    return SERVICE

async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Введіть своє ім'я:",
            reply_markup=back_kb([])
        )
        return NAME

    service = update.message.text
    services = get_services()

    service_names = [s[1] for s in services]

    if service not in service_names:
        await update.message.reply_text("Обери послугу кнопкою.")
        return SERVICE

    context.user_data["service"] = service

    selected_service = None

    for s in services:
        if s[1] == service:
            selected_service = s
            break

    masters = get_masters()

    if not masters:
        await update.message.reply_text("Поки немає доступних майстрів.")
        return ConversationHandler.END

    keyboard = [[m[1]] for m in masters]

    await update.message.reply_text(
        f"Послуга: {selected_service[1]}\n"
        f"Ціна: {selected_service[2]}\n"
        f"Тривалість: {selected_service[3]}\n\n"
        f"Обери майстра:",
        reply_markup=back_kb(keyboard)
    )

    return MASTER

async def get_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        services = get_services()
        keyboard = [[s[1]] for s in services]

        await update.message.reply_text(
            "Обери послугу:",
            reply_markup=back_kb(keyboard)
        )

        return SERVICE

    master = update.message.text
    masters = get_masters()
    master_names = [m[1] for m in masters]

    if master not in master_names:
        await update.message.reply_text("Обери майстра кнопкою.")
        return MASTER

    context.user_data["master"] = master
    master_info = MASTER_INFO.get(master)

    if master_info:
        try:
            await update.message.reply_photo(
            photo=master_info["photo"],
            caption=master_info["description"]
        )
        except Exception:
            await update.message.reply_text(master_info["description"])

    dates = get_master_dates_from_db(master)

    if not dates:
        await update.message.reply_text(
            "У цього майстра поки немає розкладу."
        )
        return ConversationHandler.END

    keyboard = [[d] for d in dates]

    await update.message.reply_text(
        "Обери дату:",
        reply_markup=back_kb(keyboard)
    )

    return DAY

async def get_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        masters = get_masters()
        keyboard = [[m[1]] for m in masters]

        await update.message.reply_text(
            "Обери майстра:",
            reply_markup=back_kb(keyboard)
        )
        return MASTER

    date = update.message.text
    master = context.user_data["master"]

    dates = get_master_dates_from_db(master)

    if date not in dates:
        await update.message.reply_text("У цього майстра немає такої робочої дати.")
        return DAY

    context.user_data["date"] = date

    free_times = get_free_times(master, date)

    if not free_times:
        await update.message.reply_text("На цю дату свободного часу немає. Обери іншу дату.")
        return DAY

    keyboard = [[t] for t in free_times]

    await update.message.reply_text(
        "Обери час:",
        reply_markup=back_kb(keyboard)
    )

    return TIME


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        master = context.user_data["master"]
        days = get_master_dates_from_db(master)
        keyboard = [[d] for d in days]
        await update.message.reply_text(
            "Обери дату:",
            reply_markup=back_kb(keyboard)
        )

        return DAY

    time = update.message.text
    master = context.user_data["master"]
    date = context.user_data["date"]

    free_times = get_free_times(master, date)

    if time not in free_times:
        await update.message.reply_text("Це час вже зайнятий або недоступний. Обери інший.")
        return TIME

    context.user_data["time"] = time

    name = context.user_data["name"]
    service = context.user_data["service"]

    await update.message.reply_text(
    "💬 Додай коментар до запису або натисни 'Пропустити':",
    reply_markup=kb([
        ["⏭ Пропустити"],
        ["⬅️ Назад"]
    ])
    )

    return COMMENT

async def booking_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        master = context.user_data["master"]
        date = context.user_data["date"]

        free_times = get_free_times(master, date)
        keyboard = [[t] for t in free_times]

        await update.message.reply_text(
            "Обери вільний час:",
            reply_markup=back_kb(keyboard)
        )

        return TIME

    if text == "⏭ Пропустити":
        context.user_data["comment"] = "Без коментаря"
    else:
        context.user_data["comment"] = text

    await update.message.reply_text(
        f"Перевір запис:\n\n"
        f"Ім'я: {context.user_data['name']}\n"
        f"Послуга: {context.user_data['service']}\n"
        f"Майстер: {context.user_data['master']}\n"
        f"Дата: {context.user_data['date']}\n"
        f"Час: {context.user_data['time']}\n"
        f"Коментар: {context.user_data['comment']}\n\n"
        f"Підтверджуємо запис?",
        reply_markup=kb([
            ["✅ Підтвердити"],
            ["⬅️ Назад"],
            ["❌ Відмінити"]
        ])
    )

    return CONFIRM

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        master = context.user_data["master"]
        date = context.user_data["date"]

        free_times = get_free_times(master, date)
        keyboard = [[t] for t in free_times]

        await update.message.reply_text(
            "Обери вільний час:",
            reply_markup=back_kb(keyboard)
        )

        return TIME

    if text == "❌ Відмінити":
        await update.message.reply_text(
            "Запис відмінено.",
            reply_markup=main_menu_kb()
        )

        return ConversationHandler.END

    if text != "✅ Підтвердити":
        await update.message.reply_text("Натисни кнопку підтвердження.")
        return CONFIRM

    user_id = update.message.from_user.id
    data = context.user_data

    add_record(
        user_id,
        data["name"],
        data["service"],
        data["master"],
        data["date"],
        data["time"],
        data.get("comment", "Без коментаря")
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📌 Новий запис:\n\n"
                f"Ім'я: {data['name']}\n"
                f"Послуга: {data['service']}\n"
                f"Майстер: {data['master']}\n"
                f"Дата: {data['date']}\n"
                f"Час: {data['time']}"
            )
        )

    if is_admin(user_id) and is_admin_logged(context):
        menu = admin_kb()
    else:
        menu = main_menu_kb()

    await update.message.reply_text(
        "✅ Запис підтверджено!",
        reply_markup=menu
    )

    return ConversationHandler.END

def get_next_record_datetime(date_str, time_str):
    date_obj = datetime.strptime(date_str, "%d.%m.%Y")

    hour, minute = map(int, time_str.split(":"))

    record_datetime = date_obj.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    return record_datetime

async def reminder_checker(app):
    while True:
        records = get_unreminded_records()
        now = datetime.now()

        for record in records:
            record_id, user_id, name, service, master, date, time, comment = record

            try:
                record_datetime = get_next_record_datetime(date, time)
            except ValueError:
                continue

            time_diff = (record_datetime - now).total_seconds()

            # Напоминание только примерно за 1 час до записи
            if 3500 <= time_diff <= 3600:
                try:
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"⏰ Нагадування!\n\n"
                            f"Через годину у тебе запис:\n"
                            f"{service} | {master} | {date} | {time}"
                        )
                    )

                    mark_reminded(record_id)

                except Exception as e:
                    print(f"Помилка нагадування: {e}")

        await asyncio.sleep(60)

async def old_records_cleaner(app):
    while True:
        delete_old_records()
        delete_old_schedule()

        await asyncio.sleep(3600)

async def show_my_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    records = get_user_records(user_id)

    if not records:
        await update.message.reply_text(
            "У тебе поки немає записів.",
            reply_markup=main_menu_kb()
        )
        return

    message = "📋 Твої записи:\n\n"
    keyboard = []

    for record in records:
        record_id, user_id, name, service, master, date, time, comment = record

        message += f"{record_id}. {service} | {master} | {date} | {time}\n"
        keyboard.append([f"🔁 Перенести {record_id}"])
        keyboard.append([f"❌ Відмінити {record_id}"])

    keyboard.append(["⬅️ Назад"])

    await update.message.reply_text(
        message,
        reply_markup=kb(keyboard)
    )

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Головне меню:",
        reply_markup=main_menu_kb()
    )

async def start_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Напиши повідомлення в форматі:\n\n"
        "Ім'я | повідомлення\n\n"
        "Наприклад:\n"
        "Артем | Хочу перенести запис",
        reply_markup=back_kb([])
    )

    return CONTACT_ADMIN


async def send_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Головне меню:",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END

    text = update.message.text

    if "|" not in text:
        await update.message.reply_text(
            "Невірний формат.\n\n"
            "Пиши так:\n"
            "Ім'я | повідомлення"
        )
        return CONTACT_ADMIN

    client_name, client_message = text.split("|", 1)

    client_name = client_name.strip()
    client_message = client_message.strip()

    if not client_name or not client_message:
        await update.message.reply_text(
            "Ім'я та повідомлення не можуть бути порожніми."
        )
        return CONTACT_ADMIN

    user = update.message.from_user

    records = get_user_records(user.id)

    if records:
        status = "✅ Клієнт вже записаний"
        appointments_text = ""

        for record in records:
            record_id, user_id, name, service, master, date, time, comment = record
            appointments_text += (
                f"\n№{record_id}: "
                f"{service} | {master} | {date} | {time}"
            )
    else:
        status = "⚪ Клієнт поки що не записаний"
        appointments_text = "\nУ клієнта немає записів"

    username = f"@{user.username}" if user.username else "Немає"

    for admin_id in ADMIN_IDS:
         await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"💬 Нове повідомлення від клієнта\n\n"
                f"{status}\n"
                f"{appointments_text}\n\n"
                f"👤 Клієнт:\n"
                f"Ім'я: {client_name}\n"
                f"Telegram: {user.full_name}\n"
                f"Username: {username}\n"
                f"User ID: {user.id}\n\n"
                f"✉️ Повідомлення:\n"
                f"{client_message}"
            ),
            reply_markup=kb([
                [f"💬 Відповісти {user.id}"]
            ])
        )

    await update.message.reply_text(
        "✅ Повідомлення відправлено адміністратору.",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END

async def start_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        return ConversationHandler.END

    text = update.message.text

    try:
        client_id = int(text.split()[-1])
    except ValueError:
        await update.message.reply_text("Помилка відповіді.")
        return ConversationHandler.END

    context.user_data["reply_client_id"] = client_id

    await update.message.reply_text(
        "Напиши відповідь клієнту:",
        reply_markup=back_kb([])
    )

    return ADMIN_REPLY


async def send_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Адмін панель:",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    client_id = context.user_data.get("reply_client_id")

    if not client_id:
        await update.message.reply_text("Клієнта не знайдено.")
        return ConversationHandler.END

    text = update.message.text

    try:
        await context.bot.send_message(
            chat_id=client_id,
            text=(
                f"💬 Відповідь адміністратора:\n\n"
                f"{text}"
            )
        )

        await update.message.reply_text(
            "✅ Відповідь відправлено.",
            reply_markup=admin_kb()
        )

    except Exception as e:
        await update.message.reply_text(
            f"Помилка відправки:\n{e}",
            reply_markup=admin_kb()
        )

    return ConversationHandler.END

async def admin_cancel_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        context.user_data.pop("admin_cancel_record_id", None)

        await update.message.reply_text(
            "⚙️ Адмін-панель:",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    record_id = context.user_data.get("admin_cancel_record_id")

    if not record_id:
        await update.message.reply_text(
            "Запис не знайдено.",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    record = get_record(record_id)

    if not record:
        await update.message.reply_text(
            "Запис вже видалено.",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    record_id, user_id, name, service, master, date, time, comment = record

    if text == "Без коментаря":
        admin_comment = "Без коментаря"
    else:
        admin_comment = text.strip()

    delete_record(record_id)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ Ваш запис скасовано адміністратором.\n\n"
                f"💈 Послуга: {service}\n"
                f"👤 Майстер: {master}\n"
                f"📅 Дата: {date}\n"
                f"🕒 Час: {time}\n\n"
                f"💬 Коментар адміністратора:\n"
                f"{admin_comment}"
            ),
            reply_markup=kb([
                [f"💬 Зв'язатися з адміністратором"]
            ])
        )
    except Exception as e:
        print(f"Помилка повідомлення клієнта про скасування: {e}")

    context.user_data.pop("admin_cancel_record_id", None)

    await update.message.reply_text(
        "✅ Запис скасовано, клієнту відправлено повідомлення.",
        reply_markup=admin_kb()
    )

    return ConversationHandler.END

async def cancel_user_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    try:
        record_id = int(text.split()[-1])
    except ValueError:
        await update.message.reply_text("Помилка відміни запису.")
        return

    record = get_record(record_id)

    if not record or record[1] != user_id:
        await update.message.reply_text("Цей запис не знайдено.")
        return

    record_id, _, name, service, master, day, time, comment = record

    delete_record(record_id)

    await update.message.reply_text(
        f"❌ Запис відмінено:\n\n"
        f"{service} | {master} | {day} | {time}",
        reply_markup=main_menu_kb()
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"❌ Клієнт відмінив запис:\n\n"
                f"Ім'я: {name}\n"
                f"Послуга: {service}\n"
                f"Майстер: {master}\n"
                f"День: {day}\n"
                f"Час: {time}"
            )
        )


async def start_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    try:
        record_id = int(text.split()[-1])
    except ValueError:
        return ConversationHandler.END

    record = get_record(record_id)

    if not record or record[1] != user_id:
        await update.message.reply_text("Цей запис не знайдено.")
        return ConversationHandler.END

    context.user_data["reschedule_id"] = record_id
    context.user_data["reschedule_master"] = record[4]

    master = record[4]
    dates = get_master_dates_from_db(master)
    keyboard = [[d] for d in dates]

    await update.message.reply_text(
        f"Перенесення запису №{record_id}\n"
        f"Обери нову дату:",
        reply_markup=back_kb(keyboard)
    )

    return RESCHEDULE_DAY


async def reschedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await show_my_records(update, context)
        return ConversationHandler.END

    day = update.message.text
    master = context.user_data["reschedule_master"]

    dates = get_master_dates_from_db(master)

    if day not in dates:
        await update.message.reply_text("У цього майстра немає такої робочої дати. Обери іншу дату.")
        return RESCHEDULE_DAY

    context.user_data["reschedule_date"] = day

    record_id = context.user_data["reschedule_id"]
    free_times = get_free_times(master, day, exclude_id=record_id)

    if not free_times:
        await update.message.reply_text(
            "Немає вільного часу на цей день. Обери іншу дату."
        )
        return RESCHEDULE_DAY

    keyboard = [[t] for t in free_times]

    await update.message.reply_text(
        "Обери новий час:",
        reply_markup=back_kb(keyboard)
    )

    return RESCHEDULE_TIME


async def reschedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        master = context.user_data["reschedule_master"]
        dates = get_master_dates_from_db(master)
        keyboard = [[d] for d in dates]

        await update.message.reply_text(
            "Обери нову дату:",
            reply_markup=back_kb(keyboard)
        )

        return RESCHEDULE_DAY

    time = update.message.text

    record_id = context.user_data["reschedule_id"]
    date = context.user_data["reschedule_date"]
    master = context.user_data["reschedule_master"]

    free_times = get_free_times(master, date, exclude_id=record_id)

    if time not in free_times:
        await update.message.reply_text("Це час недоступний. Обери інший.")
        return RESCHEDULE_TIME

    update_record_time(record_id, date, time)

    await update.message.reply_text(
        f"✅ Запис перенесено!\n\n"
        f"Нова дата: {date}\n"
        f"Новий час: {time}",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END


async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if is_admin(user_id) and context.user_data.get("waiting_password"):
        if text == ADMIN_PASSWORD:
            context.user_data["admin_logged"] = True
            context.user_data["waiting_password"] = False

            await update.message.reply_text(
                "✅ Адмін-панель відкрита:",
                reply_markup=admin_kb()
            )
        else:
            await update.message.reply_text("❌ Невірний пароль.")

        return

    if not is_admin(user_id) or not is_admin_logged(context):
        return
    
    if context.user_data.get("waiting_setting"):
        setting_key = context.user_data["waiting_setting"]

        if text == "⬅️ Назад":
            context.user_data.pop("waiting_setting", None)

            await update.message.reply_text(
                "⚙️ Адмін-панель:",
                reply_markup=admin_kb()
            )
            return

        set_setting(setting_key, text)
        context.user_data.pop("waiting_setting", None)

        await update.message.reply_text(
            "✅ Дані оновлено.",
            reply_markup=admin_kb()
        )
        return
    
    if context.user_data.get("admin_cancel_record_id"):
        if text == "⬅️ Назад":
            context.user_data.pop("admin_cancel_record_id", None)

            await update.message.reply_text(
                "⚙️ Адмін-панель:",
                reply_markup=admin_kb()
            )
            return

        record_id = context.user_data.get("admin_cancel_record_id")
        record = get_record(record_id)

        if not record:
            context.user_data.pop("admin_cancel_record_id", None)

            await update.message.reply_text(
                "Запис вже видалено.",
                reply_markup=admin_kb()
            )
            return

        record_id, client_id, name, service, master, date, time, comment = record

        if text == "Без коментаря":
            admin_comment = "Без коментаря"
        else:
            admin_comment = text.strip()

        delete_record(record_id)

        try:
            await context.bot.send_message(
                chat_id=client_id,
                text=(
                    f"❌ Ваш запис скасовано адміністратором.\n\n"
                    f"💈 Послуга: {service}\n"
                    f"👤 Майстер: {master}\n"
                    f"📅 Дата: {date}\n"
                    f"🕒 Час: {time}\n\n"
                    f"💬 Коментар адміністратора:\n"
                    f"{admin_comment}"
                ),
                reply_markup=kb([
                    ["💬 Зв'язатися з адміністратором"]
                ])
            )
        except Exception as e:
            print(f"Помилка повідомлення клієнта: {e}")

        context.user_data.pop("admin_cancel_record_id", None)

        await update.message.reply_text(
            "✅ Запис скасовано, клієнту відправлено повідомлення.",
            reply_markup=admin_kb()
        )
        return

    if context.user_data.get("waiting_new_service"):
        if text == "⬅️ Назад":
            context.user_data["waiting_new_service"] = False
            await update.message.reply_text("⚙️ Налаштування:", reply_markup=admin_kb())
            return

        parts = text.split(" | ")

        if len(parts) != 3:
            await update.message.reply_text(
                "Невірний формат.\n\nПиши так:\nСтрижка | 500 грн | 45 хв"
            )
            return

        name, price, duration = parts
        add_service(name, price, duration)
        context.user_data["waiting_new_service"] = False

        await update.message.reply_text("✅ Послуга додана.", reply_markup=admin_kb())
        return

    if context.user_data.get("waiting_new_master"):
        if text == "⬅️ Назад":
            context.user_data["waiting_new_master"] = False
            await update.message.reply_text("⚙️ Налаштування:", reply_markup=admin_kb())
            return

        master_name = text.strip()

        if not master_name:
            await update.message.reply_text("Ім'я майстра не може бути порожнім.")
            return

        add_master(master_name)
        context.user_data["waiting_new_master"] = False

        await update.message.reply_text("✅ Майстра додано.", reply_markup=admin_kb())
        return

    if context.user_data.get("waiting_new_schedule"):
        if text == "⬅️ Назад":
            context.user_data["waiting_new_schedule"] = False
            await update.message.reply_text("⚙️ Налаштування:", reply_markup=admin_kb())
            return

        parts = text.split(" | ")

        if len(parts) != 3:
            await update.message.reply_text(
                "Невірний формат.\n\nПиши так:\nАртем | 12.05.2026 | 14:00"
            )
            return

        master, date, time = parts
        master = master.strip()
        date = date.strip()
        time = time.strip()

        master_names = [m[1] for m in get_masters()]

        if master not in master_names:
            await update.message.reply_text(
                "Немає такого майстра. Спочатку додай майстра в налаштуваннях."
            )
            return

        add_schedule(master, date, time)
        context.user_data["waiting_new_schedule"] = False

        await update.message.reply_text("✅ Розклад додано.", reply_markup=admin_kb())
        return

    records = get_all_records()

    if text == "📋 Список записів":
        if not records:
            await update.message.reply_text("Записів немає.", reply_markup=admin_kb())
            return

        message = "📋 Всі записи:\n\n"

        for r in records:
            record_id, _, name, service, master, date, time, comment = r
            message += f"{record_id}. {name} | {service} | {master} | {date} | {time}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "❌ Видалити запис":
        if not records:
            await update.message.reply_text("Записів немає.", reply_markup=admin_kb())
            return

        keyboard = [[f"❌ Запис {r[0]}"] for r in records]
        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Обери запис для скасування:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Запис "):
        try:
            record_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Помилка видалення.", reply_markup=admin_kb())
            return

        record = get_record(record_id)

        if not record:
            await update.message.reply_text("Запис не знайдено.", reply_markup=admin_kb())
            return

        context.user_data["admin_cancel_record_id"] = record_id

        await update.message.reply_text(
            "Напиши причину скасування для клієнта або натисни 'Без коментаря':",
            reply_markup=kb([
                ["Без коментаря"],
                ["⬅️ Назад"]
            ])
        )
        return ADMIN_CANCEL_COMMENT

    elif text == "📊 Аналітика":
        if not records:
            await update.message.reply_text("Аналітики поки немає.", reply_markup=admin_kb())
            return

        now = datetime.now()
        today_str = now.strftime("%d.%m.%Y")

        normalized_records = []

        for r in records:
            record_id, client_id, name, service, master, date, time, comment = r

            try:
                record_datetime = get_next_record_datetime(date, time)
            except ValueError:
                continue

            normalized_records.append({
                "id": record_id,
                "client_id": client_id,
                "name": name,
                "service": service,
                "master": master,
                "date": date,
                "time": time,
                "comment": comment,
                "datetime": record_datetime
            })

        if not normalized_records:
            await update.message.reply_text("Аналітики поки немає.", reply_markup=admin_kb())
            return

        normalized_records = sorted(normalized_records, key=lambda r: r["datetime"])
        today_records = [r for r in normalized_records if r["date"] == today_str]

        masters_counter = Counter(r["master"] for r in normalized_records)
        services_counter = Counter(r["service"] for r in normalized_records)
        dates_counter = Counter(r["date"] for r in normalized_records)

        sorted_masters = sorted(masters_counter.items(), key=lambda x: x[1], reverse=True)
        sorted_services = sorted(services_counter.items(), key=lambda x: x[1], reverse=True)
        sorted_dates = sorted(
            dates_counter.items(),
            key=lambda x: get_next_record_datetime(x[0], "00:00")
        )

        nearest_record = normalized_records[0]

        if nearest_record["date"] == today_str:
            nearest_text = f"сьогодні о {nearest_record['time']}"
        else:
            nearest_text = f"{nearest_record['date']} о {nearest_record['time']}"

        message = "📊 Аналітика\n\n"
        message += "━━━━━━━━━━━━━━\n"
        message += "📌 Загалом\n"
        message += f"• Активних записів: {len(normalized_records)}\n"
        message += f"• Унікальних клієнтів: {len(set(r['client_id'] for r in normalized_records))}\n"
        message += f"• Найближчий запис: {nearest_text}\n\n"

        message += "━━━━━━━━━━━━━━\n"
        message += f"📅 Сьогодні — {today_str}\n"
        message += f"• Записів: {len(today_records)}\n\n"

        if today_records:
            for r in today_records:
                message += (
                    f"🕒 {r['time']}\n"
                    f"👤 {r['master']}\n"
                    f"💈 {r['service']}\n"
                    f"🙋 Клієнт: {r['name']}\n"
                )

                if r["comment"]:
                    message += f"💬 Коментар: {r['comment']}\n"

                message += "\n"
        else:
            message += "На сьогодні записів немає\n\n"

        message += "━━━━━━━━━━━━━━\n"
        message += "👤 Майстри\n\n"

        for i, (master, count) in enumerate(sorted_masters):
            if i == 0:
                message += f"🏆 {master} — {count} записів\n"
            else:
                message += f"• {master} — {count} записи\n"

        message += "\n━━━━━━━━━━━━━━\n"
        message += "💈 Послуги\n\n"

        for i, (service, count) in enumerate(sorted_services):
            if i == 0:
                message += f"🔥 {service} — {count}\n"
            else:
                message += f"• {service} — {count}\n"

        message += "\n━━━━━━━━━━━━━━\n"
        message += "📅 По датах\n\n"

        for date, count in sorted_dates[:7]:
            message += f"• {date} — {count} записи\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "🕒 Зайняті слоти":
        if not records:
            await update.message.reply_text("Зайнятих слотів немає.", reply_markup=admin_kb())
            return

        message = "🕒 Зайняті слоти:\n\n"

        for r in records:
            record_id, _, name, service, master, date, time, comment = r
            message += f"{record_id}. {master} — {date} {time} ({service})\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "🧹 Очистити все":
        clear_records()
        await update.message.reply_text("🧹 Всі записи видалено.", reply_markup=admin_kb())

    elif text == "⚙️ Налаштування":
        await update.message.reply_text(
            "⚙️ Налаштування:",
            reply_markup=kb([
                ["💈 Послуги"],
                ["👤 Майстри"],
                ["📅 Розклад"],
                ["🌐 Контакти та соцмережі"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "💈 Послуги":
        await update.message.reply_text(
            "💈 Керування послугами:",
            reply_markup=kb([
                ["📋 Список послуг"],
                ["➕ Додати послугу"],
                ["❌ Видалити послугу"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📋 Список послуг":
        services = get_services()

        if not services:
            await update.message.reply_text("Послуг поки що немає.", reply_markup=admin_kb())
            return

        message = "💈 Послуги:\n\n"

        for service in services:
            service_id, name, price, duration = service
            message += f"{service_id}. {name} | {price} | {duration}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "➕ Додати послугу":
        context.user_data["waiting_new_service"] = True

        await update.message.reply_text(
            "Напиши нову послугу в форматі:\n\n"
            "Назва | Ціна | Тривалість\n\n"
            "Наприклад:\n"
            "Дитяча стрижка | 400 грн | 30 хв",
            reply_markup=back_kb([])
        )

    elif text == "❌ Видалити послугу":
        services = get_services()

        if not services:
            await update.message.reply_text("Послуг поки що немає.", reply_markup=admin_kb())
            return

        keyboard = []

        for service in services:
            service_id, name, _, _ = service
            keyboard.append([f"❌ Послуга {service_id}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Обери послугу для видалення:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Послуга "):
        try:
            service_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Помилка видалення.")
            return

        delete_service(service_id)

        await update.message.reply_text("✅ Послуга видалена.", reply_markup=admin_kb())

    elif text == "👤 Майстри":
        await update.message.reply_text(
            "👤 Керування майстрами:",
            reply_markup=kb([
                ["📋 Список майстрів"],
                ["➕ Додати майстра"],
                ["❌ Видалити майстра"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📋 Список майстрів":
        masters = get_masters()

        if not masters:
            await update.message.reply_text("Майстрів поки що немає.", reply_markup=admin_kb())
            return

        message = "👤 Майстри:\n\n"

        for master in masters:
            master_id, name = master
            message += f"{master_id}. {name}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "➕ Додати майстра":
        context.user_data["waiting_new_master"] = True

        await update.message.reply_text(
            "Напиши ім'я майстра.\n\n"
            "Наприклад:\n"
            "Ігор",
            reply_markup=back_kb([])
        )

    elif text == "❌ Видалити майстра":
        masters = get_masters()

        if not masters:
            await update.message.reply_text("Майстрів поки що немає.", reply_markup=admin_kb())
            return

        keyboard = []

        for master in masters:
            master_id, name = master
            keyboard.append([f"❌ Майстер {master_id}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Обери майстра для видалення:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Майстер "):
        try:
            master_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Помилка видалення.")
            return

        delete_master(master_id)

        await update.message.reply_text("✅ Майстер видалений.", reply_markup=admin_kb())

    elif text == "📅 Розклад":
        await update.message.reply_text(
            "📅 Керування розкладом:",
            reply_markup=kb([
                ["📋 Список розкладу"],
                ["➕ Додати розклад"],
                ["❌ Видалити розклад"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📋 Список розкладу":
        schedule = get_schedule()

        if not schedule:
            await update.message.reply_text("Розкладу поки що немає.", reply_markup=admin_kb())
            return

        message = "📅 Розклад:\n\n"

        for item in schedule:
            schedule_id, master, date, time = item
            message += f"{schedule_id}. {master} | {date} | {time}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "➕ Додати розклад":
        context.user_data["waiting_new_schedule"] = True

        await update.message.reply_text(
            "Напиши розклад в форматі:\n\n"
            "Майстер | Дата | Час\n\n"
            "Наприклад:\n"
            "Артем | 12.05.2026 | 14:00",
            reply_markup=back_kb([])
        )

    elif text == "❌ Видалити розклад":
        schedule = get_schedule()

        if not schedule:
            await update.message.reply_text("Розкладу поки що немає.", reply_markup=admin_kb())
            return

        keyboard = []

        for item in schedule:
            schedule_id, master, date, time = item
            keyboard.append([f"❌ Розклад {schedule_id}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Обери рядок розкладу для видалення:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Розклад "):
        try:
            schedule_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Помилка видалення.")
            return

        delete_schedule(schedule_id)

        await update.message.reply_text("✅ Розклад видалений.", reply_markup=admin_kb())

    elif text == "⬅️ Назад":
        await update.message.reply_text("⚙️ Адмін-панель:", reply_markup=admin_kb())

    elif text == "🌐 Контакти та соцмережі":
        await update.message.reply_text(
            "🌐 Керування контактами:",
            reply_markup=kb([
                ["📞 Змінити номер"],
                ["📍 Змінити адресу"],
                ["🌐 Змінити соцмережі"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📞 Змінити номер":
        context.user_data["waiting_setting"] = "phone"

        await update.message.reply_text(
            "Напиши новий номер телефону:",
            reply_markup=back_kb([])
        )

    elif text == "📍 Змінити адресу":
        context.user_data["waiting_setting"] = "address"

        await update.message.reply_text(
            "Напиши нову адресу:",
            reply_markup=back_kb([])
        )

    elif text == "🌐 Змінити соцмережі":
        context.user_data["waiting_setting"] = "socials"

        await update.message.reply_text(
            "Напиши соцмережі в форматі:\n\n"
            "Instagram: @name\n"
            "Facebook: link\n"
            "TikTok: @name\n"
            "Telegram: @name",
            reply_markup=back_kb([])
        )

    elif text == "🚪 Вийти з адмінки":
        context.user_data["admin_logged"] = False

        await update.message.reply_text(
            "Ти вийшов з адмінки.",
            reply_markup=main_menu_kb()
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Дія скасована.",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END


web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Bot is running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


def main():
    if not TOKEN:
        raise RuntimeError("TOKEN is missing. Add TOKEN in Render Environment Variables.")

    init_db()

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    app = ApplicationBuilder().token(TOKEN).build()

    booking = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📝 Записатися$"), begin_booking)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service)],
            MASTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_master)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_day)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_comment)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_booking)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    reschedule = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔁 Перенести \\d+$"), start_reschedule)
        ],
        states={
            RESCHEDULE_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reschedule_day)],
            RESCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reschedule_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    contact_admin = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💬 Зв'язатися з адміністратором$"), start_contact_admin)
        ],
        states={
            CONTACT_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_to_admin)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_reply_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^💬 Відповісти \\d+$"),
                start_admin_reply
            )
        ],
        states={
            ADMIN_REPLY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    send_admin_reply
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.Regex("^🚀 Почати$"), start)
    )
    app.add_handler(CommandHandler("cancel", cancel))
    
    
   

    app.add_handler(booking)
    app.add_handler(reschedule)
    app.add_handler(contact_admin)
    app.add_handler(admin_reply_handler)
    app.add_handler(MessageHandler(filters.Regex("^📋 Мої записи$"), show_my_records))
    app.add_handler(
        MessageHandler(
            filters.Regex("^⬅️ Назад$") & ~filters.User(user_id=ADMIN_IDS),
            back_to_main_menu
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^❌ Відмінити \\d+$"),
            cancel_user_record
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📞 Контакти$"),
            show_contacts
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^(📍 Адреса|📞 Зателефонувати|📸 Instagram)$"),
            contact_buttons
        )
    )

    app.add_handler(
    MessageHandler(
        filters.Regex("^(📍 Адреса|📞 Зателефонувати|🌐 Соцмережі|⬅️ Назад в меню)$"),
        contact_buttons
    )
)

    app.add_handler(
        ConversationHandler(
            entry_points=[
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_IDS),
                    admin_buttons
                )
        ],
        states={
            ADMIN_CANCEL_COMMENT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_cancel_comment
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
)

    
    print("Бот работает...")

    app.job_queue.run_once(
        lambda context: asyncio.create_task(reminder_checker(app)),
        when=1
    )
    app.job_queue.run_once(
        lambda context: asyncio.create_task(old_records_cleaner(app)),
        when=5
    )
    app.run_polling()


if __name__ == "__main__":
    main()

