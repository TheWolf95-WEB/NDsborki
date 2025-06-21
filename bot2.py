# Запуск уведомления после run_polling
async def on_startup(app):
    if os.path.exists("restart_message.txt"):
        with open("restart_message.txt", "r") as f:
            user_id = int(f.read().strip())
        try:
            menu = [['📋 Сборки Warzone']]
            markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)
            await app.bot.send_message(
                chat_id=user_id,
                text="✅ Бот успешно перезапущен. Возвращаюсь в главное меню...",
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception:
            logging.exception("❌ Не удалось отправить сообщение после рестарта")
        os.remove("restart_message.txt")

import asyncio
import sys
import subprocess
import logging
import os
from dotenv import load_dotenv
load_dotenv()
from logging.handlers import RotatingFileHandler
from collections import Counter
from datetime import datetime

# Установка абсолютного пути к директории проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# === Логирование ===
os.makedirs("logs", exist_ok=True)

# Обработчик для INFO и выше с ротацией
info_handler = RotatingFileHandler("logs/info.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
info_handler.setLevel(logging.INFO)
info_handler.addFilter(lambda record: record.levelno < logging.WARNING)

# Обработчик для WARNING и выше с ротацией
error_handler = RotatingFileHandler("logs/error.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
error_handler.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[info_handler, error_handler]  # Без StreamHandler
)


# === Импорты и конфигурация ===
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, CallbackQueryHandler
import json

# === Константы ===
TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = list(map(int, os.getenv("ALLOWED_USERS", "").split(",")))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_PATH = 'database/builds.json'


# Этапы диалога для ConversationHandler
(WEAPON_NAME, ROLE_INPUT, CATEGORY_SELECT, VIEW_CATEGORY_SELECT, MODE_SELECT, TYPE_CHOICE, MODULE_COUNT, MODULE_SELECT, IMAGE_UPLOAD, CONFIRMATION,
 VIEW_WEAPON, VIEW_SET_COUNT, VIEW_DISPLAY, POST_CONFIRM) = range(14)


# === Утилита для добавления кнопки главного меню ===
def build_keyboard_with_main(buttons: list[list[str]]) -> ReplyKeyboardMarkup:
    if not any("🏠 Главное меню" in row for row in buttons):
        buttons.append(["🏠 Главное меню"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) not in os.getenv("ALLOWED_USERS", "").split(","):
            await update.message.reply_text("❌ У тебя нет прав для этой команды.")
            return
        return await func(update, context)
    return wrapper


# === Команда /start, главное меню ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🔥 Новый код загружен с GitHub")
    user_id = update.effective_user.id
    menu = get_main_menu(user_id)

    if user_id in ALLOWED_USERS:
        text = "Добро пожаловать в NDsborki BOT"
        text += "\n\n🛠 Админ: используйте команду /add для добавления сборок."
    else:
        text = (
            "👋 <b>Добро пожаловать в NDsborki BOT!</b>\n\n"
            "Здесь ты можешь:\n"
            " • Смотреть сборки оружия из Warzone\n"
            " • Выбирать тип и кол-во модулей для фильтра\n"
            " • Листать подходящие варианты с фото и автором\n\n"
            "📍 Жми <b>«Сборки Warzone»</b>, чтобы начать!\n\n"
            "⚠️ Добавление сборок доступно только администраторам.\n\n"
            "💬 Если есть идеи или нашёл баг — пиши @nd_admin95\n\n"
            "🛠 Бот будет постоянно обновляться и улучшаться!!"
        )

    await update.message.reply_text(text, reply_markup=menu, parse_mode="HTML")



# === универсальная функция для клавиатуры === 
def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([['📋 Сборки Warzone']], resize_keyboard=True)



@admin_only
async def check_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os

    file_map = {
        "assault": "modules-assault.json",
        "battle": "modules-battle.json",
        "smg": "modules-pp.json",
        "shotgun": "modules-drobovik.json",
        "marksman": "modules-pehotnay.json",
        "lmg": "modules-pulemet.json",
        "sniper": "modules-snayperki.json",
        "pistol": "modules-pistolet.json",
        "special": "modules-osoboe.json"
    }

    msg_lines = ["🔍 Проверка файлов в /database:"]
    for key, fname in file_map.items():
        path = f"database/{fname}"
        if os.path.exists(path):
            msg_lines.append(f"✅ {key}: <code>{fname}</code> — найден")
        else:
            msg_lines.append(f"❌ {key}: <code>{fname}</code> — отсутствует")

    await update.message.reply_text("\n".join(msg_lines), parse_mode="HTML")




# === Просмотр сборок по шагам ===
async def show_all_builds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(DB_PATH, 'r') as f:
        data = json.load(f)
    types = sorted(set(b['type'] for b in data if b['mode'].lower() == 'warzone'))
    if not types:
        await update.message.reply_text("Сборок Warzone пока нет.")
        return ConversationHandler.END
    buttons = [[t] for t in types]
    await update.message.reply_text("Выберите тип оружия:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return VIEW_WEAPON

# Показывает список оружия выбранного типа
async def view_select_weapon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['selected_type'] = update.message.text
    with open(DB_PATH, 'r') as f:
        data = json.load(f)
    weapons = sorted(set(b['weapon_name'] for b in data if b['type'] == context.user_data['selected_type'] and b.get('category') == context.user_data.get('selected_category')))
    if not weapons:
        await update.message.reply_text("Сборок по этому типу пока нет.")
        return ConversationHandler.END
    buttons = [[w] for w in weapons]

    # 🟢 Сохраняем выбранное оружие для дальнейших шагов
    context.user_data['available_weapons'] = weapons

    await update.message.reply_text("Выберите оружие:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return VIEW_SET_COUNT

# Просит выбрать количество модулей (5 или 8), с указанием количества доступных сборок
# Просит выбрать количество модулей (5 или 8), с указанием количества доступных сборок
async def view_set_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['selected_weapon'] = update.message.text  # ✅ фикс: сохраняем выбранное оружие
    context.user_data['selected_category'] = context.user_data.get('selected_category')

    # Загружаем сборки из БД
    with open(DB_PATH, 'r') as f:
        builds = json.load(f)

    # Считаем, сколько сборок с 5 и 8 модулями
    count_5 = sum(1 for b in builds if b['weapon_name'] == context.user_data['selected_weapon']
                                      and b['type'] == context.user_data['selected_type']
                                      and len(b['modules']) == 5)
    count_8 = sum(1 for b in builds if b['weapon_name'] == context.user_data['selected_weapon']
                                      and b['type'] == context.user_data['selected_type']
                                      and len(b['modules']) == 8)

    # Обновляем клавиатуру с количеством
    keyboard = [[f"5 ({count_5})"], [f"8 ({count_8})"]]
    await update.message.reply_text("Выберите количество модулей:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    return VIEW_DISPLAY


# === Фильтрует сборки по типу, оружию и количеству модулей ===
# Показывает первую подходящую сборку
async def view_display_builds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    count_str = raw_text.split()[0]  # Берёт "5" из "5 (0)" и т.д.
    try:
        count = int(count_str)
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, выберите количество модулей с клавиатуры.")
        return VIEW_DISPLAY

    context.user_data['selected_count'] = count

    with open(DB_PATH, 'r') as f:
        builds = json.load(f)

    filtered = [
       b for b in builds
       if b['type'] == context.user_data['selected_type'] and
       b['weapon_name'] == context.user_data['selected_weapon'] and
       len(b['modules']) == count and
       b.get('category') == context.user_data.get('selected_category')
     ]



    if not filtered:
        context.user_data.pop('selected_count', None)
        # обновлённый пересчёт доступных сборок
        count_5 = sum(1 for b in builds if b['weapon_name'] == context.user_data['selected_weapon'] and b['type'] == context.user_data['selected_type'] and len(b['modules']) == 5)
        count_8 = sum(1 for b in builds if b['weapon_name'] == context.user_data['selected_weapon'] and b['type'] == context.user_data['selected_type'] and len(b['modules']) == 8)
        keyboard = [[f"5 ({count_5})"], [f"8 ({count_8})"]]
        await update.message.reply_text(
            "❌ Подходящих сборок не найдено.\n\nВыберите другое количество модулей:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return VIEW_DISPLAY

    context.user_data['viewed_builds'] = filtered
    context.user_data['current_index'] = 0
    return await send_build(update, context)



# Показывает текущую сборку (с фото и навигацией)
async def send_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data['current_index']
    build = context.user_data['viewed_builds'][idx]

    # Внешний вид вывода сборки (пользовательская часть)
    # Загружаем словарь переводов EN → RU
    translation = load_translation_dict(build['type'])

    # Показываем сборку, переводя значения модулей
    modules_text = "\n".join(
        f"├ {k}: {translation.get(v, v)}"
        for k, v in build['modules'].items()
    )

    caption = (
        f"Оружие: {build['weapon_name']}\n"
        f"Дистанция: {build.get('role', '-')}\n"
        f"Тип: {build['type']}\n\n"
        f"Модули: {len(build['modules'])}\n"
        f"{modules_text}\n\n"
        f"Автор: {build['author']}"
    )



    nav = []
    nav_row = []
    if idx > 0:
        nav_row.append("⬅ Предыдущая")
    if idx < len(context.user_data['viewed_builds']) - 1:
        nav_row.append("➡ Следующая")
    if nav_row:
        nav.append(nav_row)
    nav.append(["📋 Сборки Warzone"])
    markup = ReplyKeyboardMarkup(nav, resize_keyboard=True)

    if os.path.exists(build['image']):
        with open(build['image'], 'rb') as img:
            await update.message.reply_photo(photo=InputFile(img), caption=caption, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(caption, reply_markup=markup, parse_mode="HTML")
    return VIEW_DISPLAY

# Переход к следующей сборке
async def next_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['current_index'] < len(context.user_data['viewed_builds']) - 1:
        context.user_data['current_index'] += 1
        return await send_build(update, context)

# Переход к предыдущей сборке
async def previous_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['current_index'] > 0:
        context.user_data['current_index'] -= 1
        return await send_build(update, context)

# === Админская часть ===
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет прав добавления.")
        await start(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🛠 <b>Режим добавления сборок включён</b>\n\n"
        "📌 Следуйте пошаговым инструкциям, чтобы добавить новую сборку.\n"
        "Вы можете в любой момент ввести <code>/cancel</code>, чтобы выйти.",
        parse_mode="HTML"
    )

    await update.message.reply_text("Введите название оружия:", reply_markup=ReplyKeyboardRemove())
    return WEAPON_NAME


# Запрашивает название оружия и Дистанция 
async def get_weapon_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weapon'] = update.message.text
    await update.message.reply_text("Теперь введите Дистанцию оружия")
    return ROLE_INPUT

async def get_weapon_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['role'] = update.message.text
    buttons = [["Топовая мета"], ["Мета"], ["Новинки"]]
    await update.message.reply_text("Выберите категорию сборки:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return CATEGORY_SELECT

# новый обработчик выбора категориии и режимаConversationHandle
async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['category'] = update.message.text
    await update.message.reply_text("Выберите режим:", reply_markup=ReplyKeyboardMarkup([["Warzone"]], resize_keyboard=True))
    return MODE_SELECT


# Запрашивает тип оружия
async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = update.message.text
    weapon_types = load_weapon_types()

    # Извлекаем label’ы (названия для кнопок)
    labels = [item["label"] for item in weapon_types]

    # группируем по 2 кнопки в строку
    buttons = [labels[i:i+2] for i in range(0, len(labels), 2)]

    await update.message.reply_text("Выберите тип оружия:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return TYPE_CHOICE


# === Функция для загрузки типов === 
def load_weapon_types():
    with open("database/types.json", "r", encoding="utf-8") as f:
        return json.load(f)


# === Выбор количества модулей (по key) ===
async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_label = update.message.text.strip()
    weapon_types = load_weapon_types()

    # Мапа: label → key
    label_to_key = {item["label"]: item["key"] for item in weapon_types}
    selected_key = label_to_key.get(selected_label)

    # Логируем, что ввёл пользователь
    logging.info(f"[get_type] Введён label: {selected_label!r}")

    # Логируем все доступные варианты
    logging.info("[get_type] Все доступные label → key:")
    for label, key in label_to_key.items():
        logging.info(f" - {label!r} → {key}")

    if not selected_key:
        await update.message.reply_text("❌ Тип оружия не распознан. Пожалуйста, выберите из предложенных кнопок.")
        return TYPE_CHOICE

    context.user_data['type'] = selected_key

    file_map = {
        "assault": "modules-assault.json",
        "battle": "modules-battle.json",
        "smg": "modules-pp.json",
        "shotgun": "modules-drobovik.json",
        "marksman": "modules-pehotnay.json",
        "lmg": "modules-pulemet.json",
        "sniper": "modules-snayperki.json",
        "pistol": "modules-pistolet.json",
        "special": "modules-osoboe.json"
    }

    filename = file_map.get(selected_key)
    if not filename:
        await update.message.reply_text("❌ Для выбранного типа оружия модули пока не настроены.")
        return ConversationHandler.END

    try:
        with open(f"database/{filename}", "r", encoding="utf-8") as f:
            module_data = json.load(f)
    except Exception as e:
        logging.exception(f"❌ Ошибка при загрузке файла {filename}")
        await update.message.reply_text(f"❌ Не удалось загрузить модули для {selected_label}.\nОшибка: {e}")
        return ConversationHandler.END

    context.user_data['module_variants'] = module_data
    context.user_data['module_options'] = list(module_data.keys())

    await update.message.reply_text(
        "Сколько модулей:",
        reply_markup=ReplyKeyboardMarkup([["5"], ["8"]], resize_keyboard=True)
    )
    return MODULE_COUNT




# Запрашивает выбор количество модулей (5 или 8)
async def get_module_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['module_count'] = int(update.message.text)
    context.user_data['selected_modules'] = []
    context.user_data['detailed_modules'] = {}
    buttons = [context.user_data['module_options'][i:i+2] for i in range(0, len(context.user_data['module_options']), 2)]
    await update.message.reply_text("Выберите модуль:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return MODULE_SELECT

# === Обработчик inline-кнопок ===
async def module_variant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if 'current_module' not in context.user_data:
        await query.message.reply_text("⚠️ Ошибка: модуль не выбран.")
        return MODULE_SELECT
    variant = query.data
    current_module = context.user_data['current_module']
    context.user_data['detailed_modules'][current_module] = variant

    if current_module not in context.user_data['selected_modules']:
        context.user_data['selected_modules'].append(current_module)

    await query.message.reply_text(f"✅ {current_module}: {variant}")

    # Проверка: выбрано ли нужное количество модулей
    if len(context.user_data['selected_modules']) >= context.user_data['module_count']:
        await query.edit_message_reply_markup(reply_markup=None)
        context.user_data.pop('current_module', None)  # Сбросим текущий модуль
        context.user_data['waiting_image'] = True
        logging.info("✅ Все модули выбраны, переходим к загрузке изображения.")
        await query.message.reply_text(
            "📷 Все модули выбраны.\nТеперь прикрепите изображение сборки (фото или файл):",
            reply_markup=ReplyKeyboardRemove()
        )
        return IMAGE_UPLOAD

    # Если не все модули выбраны — предлагаем выбрать следующий
    remaining = [m for m in context.user_data['module_options'] if m not in context.user_data['selected_modules']]
    buttons = [remaining[i:i+2] for i in range(0, len(remaining), 2)]
    context.user_data['current_module'] = None
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Выберите следующий модуль:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return MODULE_SELECT


# === Выбор модуля через обычные кнопки, варианты — inline ===
async def select_modules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    module = update.message.text
    if module not in context.user_data['module_options'] or module in context.user_data['selected_modules']:
        await update.message.reply_text("Некорректный или уже выбранный модуль.")
        return MODULE_SELECT

    context.user_data['current_module'] = module
    variants = context.user_data['module_variants'].get(module, [])

    # Сохраняем перевод EN → RU
    context.user_data['variant_translation'] = {
        v['en']: v['ru'] for v in variants
    }

    keyboard = [[InlineKeyboardButton(v['en'], callback_data=v['en'])] for v in variants]

    await update.message.reply_text(
        f"Выберите вариант для {module}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MODULE_SELECT

# ⬇️ Вставить здесь
async def reject_early_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❗ Сначала выберите все модули. Потом отправьте изображение.")
    return MODULE_SELECT

# === Загрузка изображения ===

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("📥 Обработка изображения началась...")

    file = None

    if update.message.photo:
        logging.info("📷 Получено сжатое фото")
        file = await update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        logging.info("🖼️ Получен несжатый документ-изображение")
        file = await update.message.document.get_file()
    else:
        logging.warning("❌ Изображение не распознано")
        await update.message.reply_text("❌ Пожалуйста, прикрепите изображение как фото или как файл.")
        return IMAGE_UPLOAD

    os.makedirs("images", exist_ok=True)
    path = f"images/{context.user_data['weapon'].replace(' ', '_')}.jpg"
    await file.download_to_drive(path)
    context.user_data['image'] = path

    logging.info(f"✅ Изображение сохранено: {path}")
    logging.info("⏳ Ожидание подтверждения...")

    await update.message.reply_text(
        "✅ Изображение получено.\n\nНажмите «Завершить», чтобы сохранить сборку, или «Отмена», чтобы прервать.",
        reply_markup=ReplyKeyboardMarkup([["Завершить", "Отмена"]], resize_keyboard=True)
    )
    return CONFIRMATION



# Сохранение полной сборки в JSON
async def confirm_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_build = {
        "weapon_name": context.user_data['weapon'],
        "role": context.user_data.get('role', ''),
        "category": context.user_data.get("category", "Мета"),
        "mode": context.user_data['mode'],
        "type": context.user_data['type'],
        "modules": context.user_data['detailed_modules'],
        "image": context.user_data['image'],
        "author": update.effective_user.full_name
    }

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'r') as f:
            data = json.load(f)
    else:
        data = []
    data.append(new_build)
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=2)

    # Новая клавиатура с вариантами
    keyboard = [
        ["➕ Добавить ещё одну сборку"],
        ["◀ Отмена"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "✅ Сборка успешно добавлена!\n\nЧто хотите сделать дальше?",
        reply_markup=reply_markup
    )

    return POST_CONFIRM

# === Команда /help ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
    "💬 Если у вас возникли вопросы, проблемы в работе бота или есть идеи по улучшению — не стесняйтесь, пишите прямо мне: @nd_admin95\n\n"
    "Я всегда на связи и стараюсь сделать бота ещё лучше для вас!"
)

# === /log ===
async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет прав для просмотра логов.")
        return

    try:
        result = subprocess.run(
            ["journalctl", "-u", "ndsborki.service", "-n", "30", "--no-pager"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logs = result.stdout.strip() or result.stderr.strip()
        if not logs:
            logs = "⚠️ Логи пусты или недоступны."

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📄 <b>Последние 30 строк лога:</b>\n<pre>{logs}</pre>",
            parse_mode="HTML"
        )

        await update.message.reply_text("📤 Логи отправлены в админский канал.")
    except Exception as e:
        await update.message.reply_text("❌ Не удалось получить логи.")
        logging.exception("Ошибка при получении логов")




# === Команда /Статус для админов ===   

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этой команде.")
        return

    if not os.path.exists(DB_PATH):
        await update.message.reply_text("❌ База данных отсутствует.")
        return

    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при чтении БД: {e}")
        return

    # Статус systemd
    try:
        result = subprocess.run(["systemctl", "is-active", "ndsborki.service"], capture_output=True, text=True)
        service_status = result.stdout.strip()
    except Exception as e:
        service_status = f"⚠️ Ошибка при проверке systemd: {e}"

    total = len(data)
    formatted_time = datetime.fromtimestamp(os.path.getmtime(DB_PATH)).strftime("%d.%m.%Y %H:%M")

    authors = Counter(b.get("author", "—") for b in data)
    categories = Counter(b.get("category", "—") for b in data)

    msg = [
        f"🖥 <b>Состояние сервиса:</b> <code>{service_status}</code>",
        f"📦 <b>Всего сборок:</b> <code>{total}</code>",
        f"📅 <b>Обновлено:</b> <code>{formatted_time}</code>",
        "",
        "👥 <b>Авторы:</b>"
    ]
    msg += [f"• <b>{name}</b> — <code>{count}</code>" for name, count in authors.most_common()]

    if categories:
        msg.append("\n📁 <b>Категории сборок:</b>")
        msg += [f"• <b>{cat}</b> — <code>{count}</code>" for cat, count in categories.items()]

    await update.message.reply_text("\n".join(msg), parse_mode="HTML")

# === Команда /home — возврат в главное меню ===
async def home_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Главное меню...")
    await start(update, context)



# === Команда /show_all — список всех сборок текстом ===
async def show_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(DB_PATH):
        await update.message.reply_text("Список сборок пуст.")
        return

    with open(DB_PATH, 'r') as f:
        data = json.load(f)

    # ✅ Показываем только Warzone
    data = [b for b in data if b.get("mode", "").lower() == "warzone"]

    if not data:
        await update.message.reply_text("Список сборок пуст.")
        return

    lines = ["📄 <b>Сборки Warzone:</b>"]
    for idx, b in enumerate(data, start=1):
        translation = load_translation_dict(b.get("type", ""))  # ✅ загрузка перевода
        modules_text = "\n".join(
            f"🔸 {k}: {translation.get(v, v)}" for k, v in b.get("modules", {}).items()
        )

        lines.append(
            f"<b>{idx}. {b.get('weapon_name', '—').upper()}</b>\n"
            f"├ Дистанция: {b.get('role', '-')}\n"
            f"├ Тип: {b.get('type', '-')}\n"
            f"├ Модулей: {len(b.get('modules', {}))}\n"
            f"└ Автор: {b.get('author', '-')}"
        )

    result = "\n\n".join(lines)
    markup = ReplyKeyboardMarkup([['🏠 Главное меню']], resize_keyboard=True)
    await update.message.reply_text(result, reply_markup=markup, parse_mode="HTML")


# Отмена действия и сброс клавиатуры
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === /restart ===
@admin_only
async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    context.user_data.clear()
    await update.message.reply_text(
        "🔄 Бот перезапускается...\n⏳ Пожалуйста, подождите пару секунд..."
    )

    # Для уведомления в лог-канал
    with open("restarted_by.txt", "w") as f:
        f.write(f"{user.full_name} (ID: {user.id})")

    # Для личного уведомления после перезапуска
    with open("restart_message.txt", "w") as f:
        f.write(str(user.id))

    os._exit(0)







    # 💣 Завершаем процесс — systemd сам перезапустит
    os._exit(0)



# Выбор категории в пользов части
async def view_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(DB_PATH):
        await update.message.reply_text("⚠️ База данных не найдена.")
        return ConversationHandler.END

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Названия категорий и эмодзи
    raw_categories = {
        "Топовая мета": "🔥 Топовая мета",
        "Мета": "📈 Мета",
        "Новинки": "🆕 Новинки"
    }

    # Подсчёт количества сборок на каждую категорию
    counts = {
        cat: sum(1 for b in data if b.get("mode", "").lower() == "warzone" and b.get("category") == cat)
        for cat in raw_categories
    }

    # Обработка выбора категории
    user_input = update.message.text.strip()
    for key, label in raw_categories.items():
        if user_input.startswith(label):
            context.user_data['selected_category'] = key
            types = sorted(set(
                b['type'] for b in data
                if b.get("mode", "").lower() == "warzone" and b.get("category") == key
            ))
            buttons = [[t] for t in types]
            await update.message.reply_text("Выберите тип оружия:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return VIEW_WEAPON

    # Первый запуск — вывод категорий с эмодзи и количеством
    buttons = [[f"{label} ({counts[key]})"] for key, label in raw_categories.items()]
    await update.message.reply_text("Выберите категорию:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return VIEW_CATEGORY_SELECT





# === Регистрация хендлеров ===
app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()


app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("restart", restart_bot))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("show_all", show_all_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("log", get_logs))
app.add_handler(CommandHandler("check_files", check_files))



add_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("➕ Добавить сборку"), add_start),
        CommandHandler("add", add_start),
    ],
    states={
        WEAPON_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weapon_name)],
        ROLE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weapon_role)],
        CATEGORY_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],  # ⬅ ВЕРХ
        MODE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mode)],
        TYPE_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_type)],
        MODULE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_module_count)],
        MODULE_SELECT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, select_modules),
            MessageHandler(filters.PHOTO | filters.Document.IMAGE, reject_early_image),
            CallbackQueryHandler(module_variant_callback),
        ],
        IMAGE_UPLOAD: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image)],
        CONFIRMATION: [
            MessageHandler(filters.TEXT & filters.Regex("^Завершить$"), confirm_build),
            MessageHandler(filters.Regex("Отмена"), cancel),
            MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: u.message.reply_text(
                "📍 Пожалуйста, нажмите кнопку «Завершить», чтобы сохранить сборку, или «Отмена», чтобы выйти.")
            )
        ],
        POST_CONFIRM: [
            MessageHandler(filters.Regex("➕ Добавить ещё одну сборку"), add_start),
            MessageHandler(filters.Regex("◀ Отмена"), start)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        MessageHandler(filters.Regex("^/cancel$"), cancel),
        CommandHandler("home", home_command),
    ]
)

app.add_handler(add_conv)



# =======================================================================================


view_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("📋 Сборки Warzone"), view_category_select)],
    states={
        VIEW_CATEGORY_SELECT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, view_select_weapon),
            MessageHandler(filters.TEXT & ~filters.COMMAND, show_all_builds),
        ],
        VIEW_WEAPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_select_weapon)],
        VIEW_SET_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_set_count)],
        VIEW_DISPLAY: [
            MessageHandler(filters.Regex("5|8"), view_display_builds),
            MessageHandler(filters.Regex("➡ Следующая"), next_build),
            MessageHandler(filters.Regex("⬅ Предыдущая"), previous_build),
            MessageHandler(filters.Regex("📋 Сборки Warzone"), show_all_builds),
            MessageHandler(filters.Regex("◀ Назад"), view_set_count),
        ]
    },
    fallbacks=[
        CommandHandler("home", home_command),
        MessageHandler(filters.Regex("Отмена"), cancel),
    ]
    
)

app.add_handler(view_conv)

# ⬇️ Отдельно вне всех handlers — просто как обычную команду
app.add_handler(CommandHandler("home", home_command))


# =========================================================================================

# === Упрощённый режим удаления сборок по ID ===
DELETE_ENTER_ID, DELETE_CONFIRM_SIMPLE = range(130, 132)


# Запуск удаления — вывод списка с ID
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этой команде.")
        return ConversationHandler.END

    if not os.path.exists(DB_PATH):
        await update.message.reply_text("❌ База сборок пуста.")
        return ConversationHandler.END

    with open(DB_PATH, 'r') as f:
        data = json.load(f)

    if not data:
        await update.message.reply_text("❌ Нет сборок для удаления.")
        return ConversationHandler.END

    context.user_data['delete_map'] = {}
    text_lines = ["🧾 Сборки для удаления:"]

    for idx, b in enumerate(data, start=1):
        context.user_data['delete_map'][str(idx)] = b
        translation = load_translation_dict(b.get("type", ""))
        modules = "\n".join(f"🔸 {k}: {translation.get(v, v)}" for k, v in b.get("modules", {}).items())
        text_lines.append(
        f"{b['weapon_name']} (ID {idx})\nТип: {b['type']}\n\nМодулей: {len(b['modules'])}\n{modules}\n\nАвтор: {b['author']}"
    )

    message = "\n\n".join(text_lines)
    keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton("🚪 Выйти из удаления", callback_data="stop_delete"))

    await update.message.reply_text(
        message + "\n\nВведите ID сборки для удаления (например: 1)",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return DELETE_ENTER_ID

# Callback-кнопка для выхода
async def stop_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("🚫 Вы вышли из режима удаления.")
    return ConversationHandler.END

# Ввод ID для удаления
async def delete_enter_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    build_id = update.message.text.strip()
    if build_id not in context.user_data.get('delete_map', {}):
        await update.message.reply_text("❌ Неверный ID. Попробуйте снова.")
        return DELETE_ENTER_ID

    context.user_data['delete_id'] = build_id
    b = context.user_data['delete_map'][build_id]

    await update.message.reply_text(
        f"❗ Вы уверены, что хотите удалить сборку {b['weapon_name']} (ID: {build_id})?",
        reply_markup=ReplyKeyboardMarkup([["Да"], ["Отмена"]], resize_keyboard=True)
    )
    return DELETE_CONFIRM_SIMPLE

# Подтверждение удаления
async def delete_confirm_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено.")
        return await delete_start(update, context)

    build_id = context.user_data.get('delete_id')
    if not build_id or build_id not in context.user_data.get('delete_map', {}):
        await update.message.reply_text("❌ Ошибка ID. Возврат к списку.")
        return await delete_start(update, context)

    to_delete = context.user_data['delete_map'][build_id]
    with open(DB_PATH, 'r') as f:
        data = json.load(f)

    new_data = [b for b in data if b != to_delete]
    with open(DB_PATH, 'w') as f:
        json.dump(new_data, f, indent=2)

    await update.message.reply_text("✅ Сборка удалена.")
    return await delete_start(update, context)

# Handler
simple_delete_conv = ConversationHandler(
    entry_points=[CommandHandler("delete", delete_start)],
    states={
        DELETE_ENTER_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, delete_enter_id),
        ],
        DELETE_CONFIRM_SIMPLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_confirm_simple)],
    },
    fallbacks=[
        CommandHandler("home", home_command),
        MessageHandler(filters.Regex("Отмена"), cancel), 
    ]
)
app.add_handler(simple_delete_conv)



# отдельно за пределами ConversationHandler
app.add_handler(CallbackQueryHandler(stop_delete_callback, pattern="^stop_delete$"))

# Обработка кнопки главное меню
app.add_handler(MessageHandler(filters.Regex("🏠 Главное меню"), start))

# ==================== КОНЕЦ удаления сборки ===================================== 


# === Загрузка переводов для отображения сборок ===
def load_translation_dict(weapon_key):
    file_map = {
        "assault": "modules-assault.json",
        "smg": "modules-pp.json",
        "shotgun": "modules-drobovik.json",
        "marksman": "modules-pehotnay.json",
        "lmg": "modules-pulemet.json",
        "sniper": "modules-snayperki.json",
        # Добавь остальные при необходимости
    }

    filename = file_map.get(weapon_key)
    if not filename:
        return {}

    with open(f"database/{filename}", "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    return {v['en']: v['ru'] for variants in raw_data.values() for v in variants}




app.run_polling()
