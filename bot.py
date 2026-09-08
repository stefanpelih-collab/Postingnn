# -*- coding: utf-8 -*-
"""
Телеграм-бот "431-a baby"
"""

import json
import logging
import os
import re
from pathlib import Path

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER")
DATA_FILE = Path(__file__).with_name("bot_data.json")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("431a_baby_bot")

def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("Не удалось прочитать файл данных, начинаю с пустого")
    return {}

def save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("Не удалось сохранить файл данных")

DATA = load_data()

def chat_store(chat_id: int) -> dict:
    key = str(chat_id)
    if key not in DATA:
        DATA[key] = {"married": [], "positions": {}, "pending": {}}
    DATA[key].setdefault("married", [])
    DATA[key].setdefault("positions", {})
    DATA[key].setdefault("pending", {})
    return DATA[key]

def display_name(user: User) -> str:
    return user.full_name or user.first_name or (user.username or "Без имени")

def is_married(store: dict, user_id: int) -> bool:
    for pair in store["married"]:
        if pair[0] == user_id or pair[2] == user_id:
            return True
    return False

COMMAND_SPECS = [
    ("dice", ["подбросить", "кубик"]),
    ("dice", ["кубик"]),
    ("dice", ["dice"]),
    ("dice", ["kubik"]),
    ("married_list", ["в", "браке"]),
    ("married_list", ["вбраке"]),
    ("married_list", ["vbrake"]),
    ("positions", ["должности"]),
    ("positions", ["dolzhnosti"]),
    ("marry", ["свадьба"]),
    ("marry", ["svadba"]),
    ("help", ["помощь"]),
    ("help", ["help"]),
    ("help", ["start"]),
]

def parse_command(text: str):
    if not text or not text.startswith("/"):
        return None, None
    body = text[1:]
    body = body.lstrip(" ")
    words_raw = body.split()
    if not words_raw:
        return None, None
    words_raw[0] = words_raw[0].split("@")[0]
    words_lower = [w.lower() for w in words_raw]
    best = None
    for name, seq in COMMAND_SPECS:
        n = len(seq)
        if len(words_lower) >= n and words_lower[:n] == seq:
            if best is None or n > best[0]:
                best = (n, name)
    if best is None:
        return None, None
    n, name = best
    remaining = " ".join(words_raw[n:]).strip()
    return name, remaining

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return
    command, remaining = parse_command(message.text)
    if command is None:
        return
    if command == "help":
        await cmd_help(update, context)
    elif command == "marry":
        await cmd_marry(update, context, remaining)
    elif command == "married_list":
        await cmd_married_list(update, context)
    elif command == "positions":
        await cmd_positions(update, context, remaining)
    elif command == "dice":
        await cmd_dice(update, context)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Привет! Я 431-a baby 🤖\n\n"
        "Доступные команды:\n"
        "• /свадьба — сделать предложение (ответом на сообщение человека "
        "или через @nickname)\n"
        "• /в браке — список тех, кто женился\n"
        "• /должности — список должностей "
        "(создатель группы может задать: /должности @nickname Должность)\n"
        "• /подбросить кубик (или /кубик) — бросить кубик 🎲"
    )
    await update.effective_message.reply_text(text)

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE, remaining: str):
    message = update.effective_message
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user, None
    for entity in message.entities or []:
        if entity.type == "text_mention" and entity.user:
            return entity.user, None
    match = re.search(r"@([A-Za-z0-9_]{5,32})", remaining or "")
    if match:
        username = match.group(1)
        try:
            chat = await context.bot.get_chat(f"@{username}")
            if chat.type == "private":
                fake_user = User(
                    id=chat.id,
                    first_name=chat.first_name or username,
                    last_name=chat.last_name,
                    username=chat.username,
                    is_bot=False,
                )
                return fake_user, None
        except Exception:
            return None, (
                f"Не могу найти @{username} напрямую через Telegram API "
                "(так бывает, если этот человек ни разу не писал в чат). "
                "Пожалуйста, сделайте команду ОТВЕТОМ на его сообщение."
            )
        return None, f"Не удалось определить пользователя @{username}."
    return None, (
        "Укажите, кого хотите позвать: ответьте командой на сообщение "
        "этого человека, либо укажите @username."
    )

async def cmd_marry(update: Update, context: ContextTypes.DEFAULT_TYPE, remaining: str) -> None:
    message = update.effective_message
    chat_id = update.effective_chat.id
    proposer = update.effective_user
    store = chat_store(chat_id)
    target, error = await get_target_user(update, context, remaining)
    if error:
        await message.reply_text(error)
        return
    if target.id == proposer.id:
        await message.reply_text("Нельзя сделать предложение самому себе 😅")
        return
    if target.is_bot:
        await message.reply_text("Боту предложение не сделать 🤖")
        return
    if is_married(store, proposer.id):
        await message.reply_text("Вы уже состоите в браке! Сначала разберитесь с текущим 😉")
        return
    if is_married(store, target.id):
        await message.reply_text(f"{display_name(target)} уже состоит в браке.")
        return
    if str(target.id) in store["pending"]:
        await message.reply_text("Этому человеку уже сделали предложение, дождитесь ответа.")
        return
    proposer_name = display_name(proposer)
    target_name = display_name(target)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Принять 💍", callback_data=f"marry_yes:{target.id}"),
                InlineKeyboardButton("Отказаться 💔", callback_data=f"marry_no:{target.id}"),
            ]
        ]
    )
    target_mention = f"@{target.username}" if target.username else target_name
    proposer_mention = f"@{proposer.username}" if proposer.username else proposer_name
    sent = await message.reply_text(
        f"💍 {proposer_mention} делает предложение руки и сердца {target_mention}!\n"
        f"{target_mention}, каков будет ваш ответ?",
        reply_markup=keyboard,
    )
    store["pending"][str(target.id)] = {
        "proposer_id": proposer.id,
        "proposer_name": proposer_name,
        "target_name": target_name,
        "message_id": sent.message_id,
    }
    save_data(DATA)

async def on_marry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = update.effective_chat.id
    store = chat_store(chat_id)
    action, target_id_str = query.data.split(":", 1)
    target_id = int(target_id_str)
    clicker = query.from_user
    pending = store["pending"].get(target_id_str)
    if not pending:
        await query.answer("Это предложение уже неактуально.", show_alert=True)
        return
    if clicker.id != target_id:
        await query.answer("Это предложение не для вас 🙂", show_alert=True)
        return
    if action == "marry_yes":
        proposer_id = pending["proposer_id"]
        proposer_name = pending["proposer_name"]
        target_name = pending["target_name"]
        store["married"].append([proposer_id, proposer_name, target_id, target_name])
        del store["pending"][target_id_str]
        save_data(DATA)
        await query.answer("Поздравляем! 🎉")
        await query.edit_message_text("Поздравляем молодых с помолвкой! 🎉👰🤵💍")
    elif action == "marry_no":
        del store["pending"][target_id_str]
        save_data(DATA)
        await query.answer()
        await query.edit_message_text("Ваш суженый расторг предложение :(")

async def cmd_married_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store = chat_store(chat_id)
    if not store["married"]:
        await update.effective_message.reply_text("Пока никто не женился 💔")
        return
    lines = []
    for pair in store["married"]:
        _, name1, _, name2 = pair
        lines.append(f"💑 {name1} и {name2}")
    await update.effective_message.reply_text("Пары в браке:\n" + "\n".join(lines))

async def is_group_creator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        return True
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except Exception:
        logger.exception("Не удалось получить список админов")
        return False
    for admin in admins:
        if admin.status == "creator" and admin.user.id == user.id:
            return True
    return False

async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE, remaining: str) -> None:
    message = update.effective_message
    chat_id = update.effective_chat.id
    store = chat_store(chat_id)
    if remaining:
        if not await is_group_creator(update, context):
            await message.reply_text(
                "Назначать должности может только создатель группы."
            )
            return
        match = re.match(r"^@([A-Za-z0-9_]{3,32})\s+(.+)$", remaining.strip())
        if not match:
            await message.reply_text(
                "Формат: /должности @nickname Название должности"
            )
            return
        username, position = match.group(1), match.group(2).strip()
        store["positions"][username.lower()] = {
            "username": username,
            "position": position,
        }
        save_data(DATA)
        await message.reply_text(f"Готово: @{username} — {position}")
        return
    if not store["positions"]:
        await message.reply_text("Должности пока никому не назначены.")
        return
    lines = [
        f"@{item['username']} — {item['position']}"
        for item in store["positions"].values()
    ]
    await message.reply_text("Должности:\n" + "\n".join(lines))

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")

async def on_bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.new_chat_members:
        return
    me = await context.bot.get_me()
    for member in message.new_chat_members:
        if member.id == me.id:
            await message.reply_text(
                "Привет, я 431-a baby! Напишите /помощь, чтобы увидеть список команд 🎉"
            )

def main() -> None:
    if not TOKEN or TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER":
        raise SystemExit(
            "Укажите токен бота в переменной TOKEN или переменной окружения BOT_TOKEN."
        )
    application = Application.builder().token(TOKEN).build()
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_bot_added)
    )
    application.add_handler(MessageHandler(filters.TEXT, router))
    application.add_handler(
        CallbackQueryHandler(on_marry_callback, pattern=r"^marry_(yes|no):")
    )
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
