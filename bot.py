import logging
import random
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'  # встав свій токен сюди

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Словник для зберігання станів користувачів
user_states = {}
# Словник для ігор (ключ — кортеж з двох user_id)
game_sessions = {}
# Користувачі, які зараз вводять ID партнера (очікування)
awaiting_partner_id = set()

# Бали за рівні складності
points_map = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "bonus": 5
}

# Припустимо, що у вас є файл tasks.py з таким словником:
# tasks = {
#   "easy": [...],
#   "medium": [...],
#   "hard": [...],
#   "bonus": [...],
# }

from tasks import tasks  # імпортуй свій файл з завданнями

# Для перевірки, чи завдання використані в обох
def used_tasks_for_session(user1, user2):
    used1 = user_states.get(user1, {}).get("used", set())
    used2 = user_states.get(user2, {}).get("used", set())
    return used1.union(used2)

def get_new_task_for_user(user_id):
    partner_id = user_states[user_id].get("partner_id")
    if not partner_id:
        return None, None
    used = used_tasks_for_session(user_id, partner_id)
    levels = list(tasks.keys())
    random.shuffle(levels)
    for level in levels:
        available = [t for t in tasks[level] if t not in used]
        if available:
            task = random.choice(available)
            user_states[user_id]["used"].add(task)
            return task, level
    return None, None

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
            "partner_id": None
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
    await message.answer("Вітаю! Реєстрація завершена.\n\n" +
                         "1) Запроси партнера, щоб грати разом.\n" +
                         "2) Після того, як партнер прийме запрошення, натисни 'Почати гру з партнером'.\n\n" +
                         "Використовуй кнопки для гри.", reply_markup=kb)

@dp.message_handler(lambda message: message.text == "Запросити партнера")
async def request_partner(message: types.Message):
    user_id = message.from_user.id
    awaiting_partner_id.add(user_id)
    await message.answer("Введи user_id партнера (цифрами). Він має бути зареєстрований у боті.")

@dp.message_handler()
async def receive_partner(message: types.Message):
    user_id = message.from_user.id
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

        # Записуємо заявку
        if "partner_requests" not in user_states[partner_id]:
            user_states[partner_id]["partner_requests"] = set()
        user_states[partner_id]["partner_requests"].add(user_id)

        awaiting_partner_id.remove(user_id)
        await message.answer(f"Запит відправлено користувачу {partner_id}. Очікуй, поки він прийме.")
        try:
            await bot.send_message(partner_id, f"Користувач {user_id} запросив тебе в гру. Відповіси 'прийняти {user_id}' або 'відхилити {user_id}'.")
        except Exception:
            await message.answer("Не вдалося відправити повідомлення партнеру. Можливо він заблокував бота.")
        return

    # Обробка відповіді партнера
    text = message.text.lower()
    if text.startswith("прийняти"):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Щоб прийняти, введи: 'прийняти <user_id>'")
            return
        requester_id = int(parts[1])
        if requester_id not in user_states or user_id not in user_states[requester_id].get("partner_requests", set()):
            await message.answer("Немає запиту від цього користувача.")
            return

        # Встановлюємо партнерство
        user_states[user_id]["partner_id"] = requester_id
        user_states[requester_id]["partner_id"] = user_id

        # Очищаємо запити
        user_states[requester_id]["partner_requests"].remove(user_id)

        # Ініціалізуємо використані завдання для обох, якщо нема
        user_states[user_id].setdefault("used", set())
        user_states[requester_id].setdefault("used", set())

        # Ініціалізуємо пропуски
        user_states[user_id]["skips"] = 0
        user_states[requester_id]["skips"] = 0

        session_key = tuple(sorted([user_id, requester_id]))
        game_sessions[session_key] = {"players": session_key}

        await message.answer(f"Ви успішно стали партнерами з користувачем {requester_id}! Натисніть 'Почати гру з партнером'.")
        try:
            await bot.send_message(requester_id, f"Користувач {user_id} прийняв твій запит. Натисни 'Почати гру з партнером'.")
        except Exception:
            pass
        return

    if text.startswith("відхилити"):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Щоб відхилити, введи: 'відхилити <user_id>'")
            return
        requester_id = int(parts[1])
        if requester_id not in user_states or user_id not in user_states[requester_id].get("partner_requests", set()):
            await message.answer("Немає запиту від цього користувача.")
            return

        user_states[requester_id]["partner_requests"].remove(user_id)
        await message.answer(f"Відхилили запит від користувача {requester_id}.")
        try:
            await bot.send_message(requester_id, f"Користувач {user_id} відхилив твій запит.")
        except Exception:
            pass
        return

    # Далі обробка інших повідомлень
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
        # Просто підтверджуємо що гру почали
        await message.answer("Гра починається! Тепер ви можете отримувати завдання.")
        return

    if text == "нове завдання":
        task, level = get_new_task_for_user(user_id)
        if task is None:
            await message.answer("Всі завдання виконані обома гравцями! Вітаємо 🎉")
            return
        points = points_map[level]
        user_states[user_id]["current_task"] = task
        user_states[user_id]["current_level"] = level
        user_states[user_id]["skips"] = 0
        await message.answer(f"Твоє завдання ({level} рівень, {points} балів):\n\n{task}")
    elif text == "пропустити":
        user_states[user_id]["skips"] += 1
        if user_states[user_id]["skips"] > 2:
            user_states[user_id]["score"] -= 1
            user_states[user_id]["skips"] = 0
            await message.answer("Третій пропуск підряд — мінус 1 бал.")
        else:
            await message.answer(f"Пропущено завдання без штрафу ({user_states[user_id]['skips']} пропуски).")
    elif text == "виконано":
        if "current_task" not in user_states[user_id] or user_states[user_id]["current_task"] is None:
            await message.answer("Немає активного завдання. Натисни 'Нове завдання'.")
            return
        level = user_states[user_id]["current_level"]
        points = points_map[level]
        user_states[user_id]["score"] += points
        user_states[user_id]["skips"] = 0
        # Заносимо завдання в список виконаних (вже зроблено в get_new_task_for_user)
        await message.answer(f"Завдання виконано! +{points} балів.\
