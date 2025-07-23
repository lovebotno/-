import logging
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from tasks import tasks  # файл з завданнями

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Бали за рівень
points_map = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "bonus": 5
}

# Сесії гри: key - chat_id або інша логіка, value - dict з двома гравцями (user_ids)
game_sessions = {}

# Стани користувачів
user_states = {}
# Структура user_states[user_id] = {
#   'score': int,
#   'used': set(),
#   'skips': int,
#   'current_task': str or None,
#   'current_level': str or None,
#   'deadline': datetime or None,
#   'partner_id': int or None
# }

def get_new_task(user_id):
    used = user_states[user_id]["used"]
    level = random.choice(list(tasks.keys()))
    available = [t for t in tasks[level] if t not in used]
    if not available:
        for lvl in tasks.keys():
            available = [t for t in tasks[lvl] if t not in used]
            if available:
                level = lvl
                break
    if not available:
        return None, None
    task = random.choice(available)
    user_states[user_id]["used"].add(task)
    return task, level

def get_deadline_by_level(level):
    if level == "hard":
        return datetime.now() + timedelta(days=7)
    else:
        return datetime.now() + timedelta(days=1)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {
        "score": 0,
        "used": set(),
        "skips": 0,
        "current_task": None,
        "current_level": None,
        "deadline": None,
        "partner_id": None,
    }
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Почати гру з партнером"))
    kb.add(KeyboardButton("Переглянути моє завдання"))
    kb.add(KeyboardButton("Переглянути завдання партнера"))
    kb.add(KeyboardButton("Прийняти завдання"))
    kb.add(KeyboardButton("Завдання виконано"))
    kb.add(KeyboardButton("Пропустити"))
    kb.add(KeyboardButton("Мій рахунок"))
    kb.add(KeyboardButton("Рахунок партнера"))
    kb.add(KeyboardButton("Закінчити гру"))
    await message.answer(
        "Вітаю! Щоб грати з партнером, натисни 'Почати гру з партнером'. "
        "Інші кнопки для управління грою.",
        reply_markup=kb
    )

@dp.message_handler(lambda message: message.text == "Почати гру з партнером")
async def start_game_with_partner(message: types.Message):
    user_id = message.from_user.id
    await message.answer("Введи Telegram user ID або username партнера (без @):")

    # Чекаємо наступне повідомлення для отримання партнера
    @dp.message_handler()
    async def set_partner(msg: types.Message):
        partner_id = None
        # Спробуємо витягти айді, якщо це число
        if msg.text.isdigit():
            partner_id = int(msg.text)
        else:
            # Спробуємо знайти користувача по username, це складніше і вимагає додаткової логіки
            await msg.answer("Поки введіть user_id цифрами.")
            return

        if partner_id == user_id:
            await msg.answer("Ти не можеш грати з самим собою, введи інший user ID.")
            return

        # Ініціалізуємо стан для партнера, якщо немає
        if partner_id not in user_states:
            user_states[partner_id] = {
                "score": 0,
                "used": set(),
                "skips": 0,
                "current_task": None,
                "current_level": None,
                "deadline": None,
                "partner_id": user_id
            }
        else:
            user_states[partner_id]["partner_id"] = user_id

        user_states[user_id]["partner_id"] = partner_id

        # Створюємо сесію, key - tuple двох user_id (для простоти унікальний ідентифікатор сесії)
        session_key = tuple(sorted([user_id, partner_id]))
        game_sessions[session_key] = {"players": session_key}

        await msg.answer(f"Гра почалася з користувачем {partner_id}. Тепер натисни 'Нове завдання' для отримання завдання.")

        # Видаляємо цей handler після першого використання, щоб не перехоплював всі наступні повідомлення
        dp.message_handlers.unregister(set_partner)

@dp.message_handler(lambda message: message.text == "Нове завдання")
async def new_task_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["partner_id"] is None:
        await message.answer("Спочатку почніть гру з партнером командою 'Почати гру з партнером'.")
        return

    task, level = get_new_task(user_id)
    if task is None:
        await message.answer("Всі завдання виконані! Вітаємо 🎉")
        return
    deadline = get_deadline_by_level(level)
    user_states[user_id]["current_task"] = task
    user_states[user_id]["current_level"] = level
    user_states[user_id]["deadline"] = deadline
    user_states[user_id]["skips"] = 0

    await message.answer(
        f"Твоє завдання ({level} рівень, {points_map[level]} балів):\n\n{task}\n\n"
        f"Термін виконання: до {deadline.strftime('%d-%m-%Y %H:%M')}\n"
        "Щоб прийняти завдання, натисни кнопку 'Прийняти завдання'."
    )

@dp.message_handler(lambda message: message.text == "Прийняти завдання")
async def accept_task_handler(message: types.Message):
    user_id = message.from_user.id
    if not user_states[user_id].get("current_task"):
        await message.answer("У тебе немає активного завдання для прийняття. Натисни 'Нове завдання'.")
        return
    await message.answer(f"Завдання прийнято:\n{user_states[user_id]['current_task']}")

@dp.message_handler(lambda message: message.text == "Завдання виконано")
async def task_done_handler(message: types.Message):
    user_id = message.from_user.id
    if not user_states[user_id].get("current_task"):
        await message.answer("У тебе немає активного завдання.")
        return

    level = user_states[user_id]["current_level"]
    points = points_map[level]
    user_states[user_id]["score"] += points
    user_states[user_id]["current_task"] = None
    user_states[user_id]["current_level"] = None
    user_states[user_id]["deadline"] = None
    user_states[user_id]["skips"] = 0

    await message.answer(f"Завдання виконано! Ти отримав {points} балів.\nТвій рахунок: {user_states[user_id]['score']}")

@dp.message_handler(lambda message: message.text == "Пропустити")
async def skip_task_handler(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id]["skips"] += 1
    if user_states[user_id]["skips"] > 2:
        user_states[user_id]["score"] -= 1
        user_states[user_id]["skips"] = 0
        await message.answer("Третій пропуск підряд — мінус 1 бал.")
    else:
        await message.answer(f"Пропущено завдання без штрафу ({user_states[user_id]['skips']} пропуски).")
    # Знімаємо активне завдання, бо воно пропущене
    user_states[user_id]["current_task"] = None
    user_states[user_id]["current_level"] = None
    user_states[user_id]["deadline"] = None

@dp.message_handler(lambda message: message.text == "Переглянути моє завдання")
async def view_my_task(message: types.Message):
    user_id = message.from_user.id
    task = user_states[user_id].get("current_task")
    deadline = user_states[user_id].get("deadline")
    if task:
        await message.answer(f"Твоє активне завдання:\n{task}\nТермін виконання до {deadline.strftime('%d-%m-%Y %H:%M')}")
    else:
        await message.answer("У тебе немає активного завдання.")

@dp.message_handler(lambda message: message.text == "Переглянути завдання партнера")
async def view_partner_task(message: types.Message):
    user_id = message.from_user.id
    partner_id = user_states[user_id].get("partner_id")
    if not partner_id or partner_id not in user_states:
        await message.answer("Партнер не підключений або не знайдений.")
        return
    task = user_states[partner_id].get("current_task")
    if task:
        await message.answer("Партнер має активне завдання.")
    else:
        await message.answer("Партнер не має активного завдання.")

@dp.message_handler(lambda message: message.text == "Мій рахунок")
async def my_score(message: types.Message):
    user_id = message.from_user.id
    score = user_states[user_id]["score"]
    await message.answer(f"Твій рахунок: {score} балів")

@dp.message_handler(lambda message: message.text == "Рахунок партнера")
async def partner_score(message: types.Message):
    user_id = message.from_user.id
    partner_id = user_states[user_id].get("partner_id")
    if not partner_id or partner_id not in user_states:
        await message.answer("Партнер не підключений або не знайдений.")
        return
    score = user_states[partner_id]["score"]
    await message.answer(f"Рахунок партнера: {score} балів")

@dp.message_handler(lambda message: message.text == "Закінчити гру")
async def end_game(message: types.Message):
    user_id = message.from_user.id
    partner_id = user_states[user_id].get("partner_id")

    if partner_id and partner_id in user_states:
        user_states[partner_id]["partner_id"] = None

    if user_id in user_states:
        del user_states[user_id]

    await message.answer("Гру завершено. Щоб почати знову — введи /start.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
