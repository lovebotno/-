import logging
import random
import datetime
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from tasks import tasks  # твій файл з завданнями, словник з рівнями

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'  # твій токен сюди

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_states = {}  # інфо по користувачах
awaiting_partner_id = set()  # хто вводить id партнера
game_sessions = {}  # ключ = tuple(user1,user2), значення — сесія гри


points_map = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "bonus": 5
}

# Терміни виконання завдань за рівнями
deadlines = {
    "easy": datetime.timedelta(hours=6),
    "medium": datetime.timedelta(hours=12),
    "hard": datetime.timedelta(days=7),
    "bonus": datetime.timedelta(days=7)
}

def used_tasks_for_session(user1, user2):
    used1 = user_states.get(user1, {}).get("used", set())
    used2 = user_states.get(user2, {}).get("used", set())
    return used1.union(used2)

def get_new_task_for_user(user_id):
    partner_id = user_states[user_id].get("partner_id")
    if not partner_id:
        return None, None, None
    used = used_tasks_for_session(user_id, partner_id)
    levels = list(tasks.keys())
    random.shuffle(levels)
    for level in levels:
        available = [t for t in tasks[level] if t not in used]
        if available:
            task = random.choice(available)
            user_states[user_id]["used"].add(task)
            # Записуємо дату й час видачі завдання
            user_states[user_id]["current_task"] = task
            user_states[user_id]["current_level"] = level
            user_states[user_id]["task_assigned_time"] = datetime.datetime.now()
            user_states[user_id]["skips"] = 0
            return task, level, deadlines[level]
    return None, None, None

def get_session_key(user1, user2):
    return tuple(sorted([user1, user2]))

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        user_states[user_id] = {
            "score": 0,
            "used": set(),
            "skips": 0,
            "current_task": None,
            "current_level": None,
            "task_assigned_time": None,
            "partner_id": None,
            "partner_requests": set()
        }
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Запросити партнера"))
    kb.add(KeyboardButton("Почати гру з партнером"))
    kb.add(KeyboardButton("Нове завдання"))
    kb.add(KeyboardButton("Пропустити"))
    kb.add(KeyboardButton("Виконано"))
    kb.add(KeyboardButton("Мій рахунок"))
    kb.add(KeyboardButton("Рахунок партнера"))
    kb.add(KeyboardButton("Список виконаних"))
    kb.add(KeyboardButton("Закінчити гру"))
    await message.answer(
        "Вітаю! Реєстрація завершена.\n\n"
        "1) Запроси партнера, щоб грати разом.\n"
        "2) Після того, як партнер прийме запрошення, натисни 'Почати гру з партнером'.\n\n"
        "Використовуй кнопки для гри.", reply_markup=kb)

@dp.message_handler(lambda message: message.text == "Запросити партнера")
async def request_partner(message: types.Message):
    user_id = message.from_user.id
    awaiting_partner_id.add(user_id)
    await message.answer("Введи user_id партнера (числа). Він має бути зареєстрований у боті.")

@dp.message_handler()
async def generic_handler(message: types.Message):
    user_id = message.from_user.id

    # Якщо користувач зараз вводить user_id партнера
    if user_id in awaiting_partner_id:
        partner_text = message.text.strip()
        if not partner_text.isdigit():
            await message.answer("Введи тільки числовий user_id партнера.")
            return
        partner_id = int(partner_text)
        if partner_id == user_id:
            await message.answer("Ти не можеш запросити самого себе. Введи інший user_id.")
            return
        if partner_id not in user_states:
            await message.answer("Партнер не зареєстрований. Нехай він напише /start.")
            return
        # Записуємо запит
        user_states[partner_id]["partner_requests"].add(user_id)
        awaiting_partner_id.remove(user_id)
        await message.answer(f"Запит відправлено користувачу {partner_id}. Очікуй, поки він прийме.")
        try:
            await bot.send_message(partner_id, f"Користувач {user_id} запросив тебе в гру. Відповіси 'прийняти {user_id}' або 'відхилити {user_id}'.")
        except Exception:
            await message.answer("Не вдалося надіслати повідомлення партнеру. Можливо, він заблокував бота.")
        return

    text = message.text.lower()

    # Прийняти запит
    if text.startswith("прийняти"):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Щоб прийняти, введи: 'прийняти <user_id>'")
            return
        requester_id = int(parts[1])
        if requester_id not in user_states or user_id not in user_states[requester_id]["partner_requests"]:
            await message.answer("Немає запиту від цього користувача.")
            return
        # Встановлюємо партнерство
        user_states[user_id]["partner_id"] = requester_id
        user_states[requester_id]["partner_id"] = user_id
        user_states[requester_id]["partner_requests"].remove(user_id)
        # Ініціалізуємо сесію гри
        session_key = get_session_key(user_id, requester_id)
        game_sessions[session_key] = {"players": session_key}
        # Ініціалізуємо пропуски і виконані завдання
        user_states[user_id]["skips"] = 0
        user_states[requester_id]["skips"] = 0
        user_states[user_id]["used"].clear()
        user_states[requester_id]["used"].clear()
        await message.answer(f"Ви стали партнерами з користувачем {requester_id}! Натисніть 'Почати гру з партнером'.")
        try:
            await bot.send_message(requester_id, f"Користувач {user_id} прийняв твій запит. Натисни 'Почати гру з партнером'.")
        except Exception:
            pass
        return

    # Відхилити запит
    if text.startswith("відхилити"):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Щоб відхилити, введи: 'відхилити <user_id>'")
            return
        requester_id = int(parts[1])
        if requester_id not in user_states or user_id not in user_states[requester_id]["partner_requests"]:
            await message.answer("Немає запиту від цього користувача.")
            return
        user_states[requester_id]["partner_requests"].remove(user_id)
        await message.answer(f"Відхилили запит від користувача {requester_id}.")
        try:
            await bot.send_message(requester_id, f"Користувач {user_id} відхилив твій запит.")
        except Exception:
            pass
        return

    # Обробка інших ігрових команд
    await handle_game_messages(message)

async def handle_game_messages(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        await message.answer("Спочатку введи /start")
        return

    partner_id = user_states[user_id].get("partner_id")
    if not partner_id:
        await message.answer("В тебе немає партнера. Запроси його або прийми запит.")
        return

    text = message.text.lower()

    if text == "почати гру з партнером":
        await message.answer("Гра починається! Тепер ви можете отримувати завдання.")
        return

    if text == "нове завдання":
        task, level, deadline = get_new_task_for_user(user_id)
        if task is None:
            await message.answer("Всі завдання виконані обома гравцями! Вітаємо 🎉")
            return
        deadline_str = f"Термін виконання: {deadline}"
        user_states[user_id]["task_assigned_time"] = datetime.datetime.now()
        await message.answer(f"Твоє завдання ({level} рівень, {points_map[level]} балів):\n\n{task}\n\n{deadline_str}")
        return

    if text == "пропустити":
        user_states[user_id]["skips"] += 1
        if user_states[user_id]["skips"] > 2:
            user_states[user_id]["score"] -= 1
            user_states[user_id]["skips"] = 0
            await message.answer("Третій пропуск підряд — мінус 1 бал.")
        else:
            await message.answer(f"Пропущено завдання без штрафу ({user_states[user_id]['skips']} пропуски).")
        # Очищуємо поточне завдання
        user_states[user_id]["current_task"] = None
        user_states[user_id]["current_level"] = None
        user_states[user_id]["task_assigned_time"] = None
        return

    if text == "виконано":
        if not user_states[user_id]["current_task"]:
            await message.answer("Немає активного завдання. Натисни 'Нове завдання'.")
            return
        # Перевіряємо термін виконання
        assigned_time = user_states[user_id].get("task_assigned_time")
        level = user_states[user_id].get("current_level")
        deadline = deadlines.get(level, datetime.timedelta(hours=6))
        now = datetime.datetime.now()
        if assigned_time and now - assigned_time > deadline:
            await message.answer(f"Час виконання завдання минув (термін: {deadline}). Наступного разу будь уважнішим.")
            # Очищаємо завдання
            user_states[user_id]["current_task"] = None
            user_states[user_id]["current_level"] = None
            user_states[user_id]["task_assigned_time"] = None
            return
        points = points_map[level]
        user_states[user_id]["score"] += points
        user_states[user_id]["skips"] = 0
        user_states[user_id]["current_task"] = None
        user_states[user_id]["current_level"] = None
        user_states[user_id]["task_assigned_time"] = None
        await message.answer(f"Завдання виконано! +{points} балів.\nТвій рахунок: {user_states[user_id]['score']} балів")
        return

    if text == "мій рахунок":
        score = user_states[user_id]["score"]
        await message.answer(f"Твій поточний рахунок: {score} балів")
        return

    if text == "рахунок партнера":
        partner_id = user_states[user_id].get("partner_id")
        if not partner_id:
            await message.answer("В тебе немає партнера.")
            return
        score = user_states.get(partner_id, {}).get("score", 0)
        await message.answer(f"Рахунок твого партнера: {score} балів")
        return

    if text == "список виконаних":
        done = user_states[user_id].get("used", set())
        if not done:
            await message.answer("Поки що не виконано жодного завдання.")
        else:
            await message.answer("Виконані завдання:\n" + "\n".join(done))
        return

    if text == "закінчити гру":
        partner_id = user_states[user_id].get("partner_id")
        if partner_id:
            user_states[partner_id]["partner_id"] = None
       
