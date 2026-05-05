import sqlite3
import asyncio
from datetime import datetime, timedelta
from collections import Counter

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import os

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    TOKEN = "8581581631:AAHrWbATdQImh6svUHfikwVeKVK9pCXZBWs"
ADMIN_IDS = [1288830602]
ADMIN_PASSWORD = "1234"

DB_FILE = "barbershop.db"

NAME, SERVICE, MASTER, DAY, TIME, CONFIRM, RESCHEDULE_DAY, RESCHEDULE_TIME = range(8)

SERVICES = {
    "Стрижка": "500 грн / 45 мин",
    "Борода": "300 грн / 30 мин",
    "Стрижка + борода": "700 грн / 60 мин",
}

MASTER_SCHEDULE = {
    "Артем": {
        "Понедельник": ["10:00", "12:00", "14:00", "16:00"],
        "Среда": ["10:00", "12:00", "14:00", "16:00"],
        "Пятница": ["10:00", "12:00", "14:00", "16:00"],
    },
    "Даня": {
        "Вторник": ["10:00", "12:00", "14:00", "16:00"],
        "Четверг": ["10:00", "12:00", "14:00", "16:00"],
        "Суббота": ["10:00", "12:00", "14:00", "16:00"],
    },
    "Максим": {
        "Понедельник": ["12:00", "14:00", "18:00"],
        "Среда": ["12:00", "14:00", "18:00"],
        "Суббота": ["12:00", "14:00", "18:00"],
    },
}


def kb(buttons):
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def back_kb(buttons):
    return ReplyKeyboardMarkup(buttons + [["⬅️ Назад"]], resize_keyboard=True)


def main_menu_kb():
    return kb([["📝 Записаться"], ["📋 Мои записи"]])


def admin_kb():
    return kb([
        ["📋 Список записей", "📊 Статистика"],
        ["🕒 Занятые слоты"],
        ["❌ Удалить запись", "🧹 Очистить все"],
        ["🚪 Выйти из админки"],
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
        day TEXT,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_all_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, name, service, master, day, time FROM appointments ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_records(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, name, service, master, day, time FROM appointments WHERE user_id=? ORDER BY id",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, name, service, master, day, time FROM appointments WHERE id=?",
        (record_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def add_record(user_id, name, service, master, day, time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO appointments (user_id, name, service, master, day, time) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, service, master, day, time)
    )
    conn.commit()
    conn.close()


def update_record_time(record_id, day, time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET day=?, time=? WHERE id=?",
        (day, time, record_id)
    )
    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


def clear_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments")
    conn.commit()
    conn.close()


def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_admin_logged(context):
    return context.user_data.get("admin_logged") is True


def get_free_times(master, day, exclude_id=None):
    all_times = MASTER_SCHEDULE.get(master, {}).get(day, [])
    records = get_all_records()

    busy = []
    for record in records:
        record_id, _, _, _, rec_master, rec_day, rec_time = record
        if exclude_id is not None and record_id == exclude_id:
            continue
        if rec_master == master and rec_day == day:
            busy.append(rec_time)

    return [t for t in all_times if t not in busy]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if is_admin(user_id):
        if is_admin_logged(context):
            await update.message.reply_text("⚙️ Админ панель:", reply_markup=admin_kb())
        else:
            context.user_data["waiting_password"] = True
            await update.message.reply_text("Введите пароль админа:", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    await update.message.reply_text("Привет! Выбери действие:", reply_markup=main_menu_kb())
    return ConversationHandler.END


async def begin_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Как тебя зовут?", reply_markup=back_kb([]))
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_kb())
        return ConversationHandler.END

    context.user_data["name"] = update.message.text

    keyboard = [[s] for s in SERVICES.keys()]
    await update.message.reply_text("Выбери услугу:", reply_markup=back_kb(keyboard))
    return SERVICE


async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text("Как тебя зовут?", reply_markup=back_kb([]))
        return NAME

    service = update.message.text
    if service not in SERVICES:
        await update.message.reply_text("Выбери услугу кнопкой.")
        return SERVICE

    context.user_data["service"] = service

    keyboard = [[m] for m in MASTER_SCHEDULE.keys()]
    await update.message.reply_text(
        f"Услуга: {service}\nЦена/длительность: {SERVICES[service]}\n\nВыбери мастера:",
        reply_markup=back_kb(keyboard)
    )
    return MASTER


async def get_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        keyboard = [[s] for s in SERVICES.keys()]
        await update.message.reply_text("Выбери услугу:", reply_markup=back_kb(keyboard))
        return SERVICE

    master = update.message.text
    if master not in MASTER_SCHEDULE:
        await update.message.reply_text("Выбери мастера кнопкой.")
        return MASTER

    context.user_data["master"] = master

    days = list(MASTER_SCHEDULE[master].keys())
    keyboard = [[d] for d in days]

    await update.message.reply_text("Выбери день:", reply_markup=back_kb(keyboard))
    return DAY


async def get_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        keyboard = [[m] for m in MASTER_SCHEDULE.keys()]
        await update.message.reply_text("Выбери мастера:", reply_markup=back_kb(keyboard))
        return MASTER

    day = update.message.text
    master = context.user_data["master"]

    if day not in MASTER_SCHEDULE[master]:
        await update.message.reply_text("У этого мастера нет такого рабочего дня.")
        return DAY

    context.user_data["day"] = day
    free_times = get_free_times(master, day)

    if not free_times:
        await update.message.reply_text("На этот день свободного времени нет. Выбери другой день.")
        return DAY

    keyboard = [[t] for t in free_times]
    await update.message.reply_text("Выбери свободное время:", reply_markup=back_kb(keyboard))
    return TIME


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        master = context.user_data["master"]
        days = list(MASTER_SCHEDULE[master].keys())
        keyboard = [[d] for d in days]
        await update.message.reply_text("Выбери день:", reply_markup=back_kb(keyboard))
        return DAY

    time = update.message.text
    master = context.user_data["master"]
    day = context.user_data["day"]

    free_times = get_free_times(master, day)

    if time not in free_times:
        await update.message.reply_text("Это время уже занято или недоступно. Выбери другое.")
        return TIME

    context.user_data["time"] = time

    name = context.user_data["name"]
    service = context.user_data["service"]

    await update.message.reply_text(
        f"Проверь запись:\n\n"
        f"Имя: {name}\n"
        f"Услуга: {service}\n"
        f"Мастер: {master}\n"
        f"День: {day}\n"
        f"Время: {time}\n\n"
        f"Подтверждаем?",
        reply_markup=kb([["✅ Подтвердить"], ["⬅️ Назад"], ["❌ Отменить"]])
    )
    return CONFIRM


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        master = context.user_data["master"]
        day = context.user_data["day"]
        free_times = get_free_times(master, day)

        keyboard = [[t] for t in free_times]

        await update.message.reply_text(
            "Выбери свободное время:",
            reply_markup=back_kb(keyboard)
        )
        return TIME

    if text == "❌ Отменить":
        await update.message.reply_text(
            "Запись отменена.",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END

    if text != "✅ Подтвердить":
        await update.message.reply_text("Нажми кнопку подтверждения.")
        return CONFIRM

    user_id = update.message.from_user.id
    data = context.user_data

    add_record(
        user_id,
        data["name"],
        data["service"],
        data["master"],
        data["day"],
        data["time"]
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📌 Новая запись:\n\n"
                f"Имя: {data['name']}\n"
                f"Услуга: {data['service']}\n"
                f"Мастер: {data['master']}\n"
                f"День: {data['day']}\n"
                f"Время: {data['time']}"
            )
        )

    await update.message.reply_text(
        "✅ Запись подтверждена!",
        reply_markup=main_menu_kb()
    )

    # Напоминание за 1 час до записи
    day = data["day"]
    time_str = data["time"]

    days_map = {
        "Понедельник": 0,
        "Вторник": 1,
        "Среда": 2,
        "Четверг": 3,
        "Пятница": 4,
        "Суббота": 5,
        "Воскресенье": 6,
    }

    now = datetime.now()

    target_weekday = days_map[day]
    current_weekday = now.weekday()

    days_ahead = target_weekday - current_weekday

    if days_ahead < 0:
        days_ahead += 7

    record_date = now + timedelta(days=days_ahead)

    hour, minute = map(int, time_str.split(":"))

    record_datetime = record_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    reminder_time = record_datetime - timedelta(hours=1)
    delay = (reminder_time - now).total_seconds()

    async def reminder():
        if delay > 0:
            await asyncio.sleep(delay)

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"⏰ Напоминание!\n\n"
                    f"Через час у тебя запись:\n"
                    f"{data['service']} | {data['master']} | "
                    f"{data['day']} | {data['time']}"
                )
            )

    asyncio.create_task(reminder())

    return ConversationHandler.END


async def show_my_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    records = get_user_records(user_id)

    if not records:
        await update.message.reply_text("У тебя пока нет записей.", reply_markup=main_menu_kb())
        return

    message = "📋 Твои записи:\n\n"
    keyboard = []

    for record in records:
        record_id, _, name, service, master, day, time = record
        message += f"{record_id}. {service} | {master} | {day} | {time}\n"
        keyboard.append([f"🔁 Перенести {record_id}"])

    keyboard.append(["⬅️ Назад"])

    await update.message.reply_text(message, reply_markup=kb(keyboard))


async def start_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    try:
        record_id = int(text.split()[-1])
    except ValueError:
        return ConversationHandler.END

    record = get_record(record_id)

    if not record or record[1] != user_id:
        await update.message.reply_text("Эта запись не найдена.")
        return ConversationHandler.END

    context.user_data["reschedule_id"] = record_id
    context.user_data["reschedule_master"] = record[4]

    master = record[4]
    days = list(MASTER_SCHEDULE[master].keys())
    keyboard = [[d] for d in days]

    await update.message.reply_text(
        f"Перенос записи №{record_id}\nВыбери новый день:",
        reply_markup=back_kb(keyboard)
    )
    return RESCHEDULE_DAY


async def reschedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await show_my_records(update, context)
        return ConversationHandler.END

    day = update.message.text
    master = context.user_data["reschedule_master"]

    if day not in MASTER_SCHEDULE[master]:
        await update.message.reply_text("У мастера нет такого рабочего дня.")
        return RESCHEDULE_DAY

    context.user_data["reschedule_day"] = day
    record_id = context.user_data["reschedule_id"]
    free_times = get_free_times(master, day, exclude_id=record_id)

    if not free_times:
        await update.message.reply_text("На этот день нет свободного времени. Выбери другой день.")
        return RESCHEDULE_DAY

    keyboard = [[t] for t in free_times]

    await update.message.reply_text("Выбери новое время:", reply_markup=back_kb(keyboard))
    return RESCHEDULE_TIME


async def reschedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        master = context.user_data["reschedule_master"]
        days = list(MASTER_SCHEDULE[master].keys())
        keyboard = [[d] for d in days]
        await update.message.reply_text("Выбери новый день:", reply_markup=back_kb(keyboard))
        return RESCHEDULE_DAY

    time = update.message.text
    record_id = context.user_data["reschedule_id"]
    day = context.user_data["reschedule_day"]
    master = context.user_data["reschedule_master"]

    free_times = get_free_times(master, day, exclude_id=record_id)

    if time not in free_times:
        await update.message.reply_text("Это время недоступно. Выбери другое.")
        return RESCHEDULE_TIME

    update_record_time(record_id, day, time)

    await update.message.reply_text(
        f"✅ Запись перенесена!\n\nНовый день: {day}\nНовое время: {time}",
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
            await update.message.reply_text("✅ Админ панель открыта:", reply_markup=admin_kb())
        else:
            await update.message.reply_text("❌ Неверный пароль.")
        return

    if not is_admin(user_id) or not is_admin_logged(context):
        return

    records = get_all_records()

    if text == "📋 Список записей":
        if not records:
            await update.message.reply_text("Записей нет.", reply_markup=admin_kb())
            return

        message = "📋 Все записи:\n\n"
        for r in records:
            record_id, _, name, service, master, day, time = r
            message += f"{record_id}. {name} | {service} | {master} | {day} | {time}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "📊 Статистика":
        if not records:
            await update.message.reply_text("Статистики пока нет.", reply_markup=admin_kb())
            return

        services = Counter(r[3] for r in records)
        masters = Counter(r[4] for r in records)
        days = Counter(r[5] for r in records)

        message = f"📊 Статистика:\n\nВсего записей: {len(records)}\n\n"

        message += "По услугам:\n"
        for k, v in services.items():
            message += f"- {k}: {v}\n"

        message += "\nПо мастерам:\n"
        for k, v in masters.items():
            message += f"- {k}: {v}\n"

        message += "\nПо дням:\n"
        for k, v in days.items():
            message += f"- {k}: {v}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "🕒 Занятые слоты":
        if not records:
            await update.message.reply_text("Занятых слотов нет.", reply_markup=admin_kb())
            return

        message = "🕒 Занятые слоты:\n\n"
        for r in records:
            record_id, _, name, service, master, day, time = r
            message += f"{record_id}. {master} — {day} {time} ({service})\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "❌ Удалить запись":
        if not records:
            await update.message.reply_text("Записей нет.", reply_markup=admin_kb())
            return

        keyboard = [[f"❌ Удалить {r[0]}"] for r in records]
        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text("Выбери запись для удаления:", reply_markup=kb(keyboard))

    elif text.startswith("❌ Удалить "):
        try:
            record_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Ошибка удаления.", reply_markup=admin_kb())
            return

        delete_record(record_id)
        await update.message.reply_text("✅ Запись удалена.", reply_markup=admin_kb())

    elif text == "🧹 Очистить все":
        clear_records()
        await update.message.reply_text("🧹 Все записи удалены.", reply_markup=admin_kb())

    elif text == "⬅️ Назад":
        await update.message.reply_text("⚙️ Админ панель:", reply_markup=admin_kb())

    elif text == "🚪 Выйти из админки":
        context.user_data["admin_logged"] = False
        await update.message.reply_text("Ты вышел из админки.", reply_markup=ReplyKeyboardRemove())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=main_menu_kb())
    return ConversationHandler.END


def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    booking = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Записаться$"), begin_booking)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service)],
            MASTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_master)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_day)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_booking)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    reschedule = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔁 Перенести \\d+$"), start_reschedule)],
        states={
            RESCHEDULE_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reschedule_day)],
            RESCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reschedule_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(booking)
    app.add_handler(reschedule)

    app.add_handler(MessageHandler(filters.Regex("^📋 Мои записи$"), show_my_records))
    app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_IDS),
        admin_buttons
    )
)

    print("Бот работает...")
    app.run_polling()


if __name__ == "__main__":
    main()
