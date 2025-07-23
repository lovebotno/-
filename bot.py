import logging
import random
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from tasks import tasks  # Імпорт завдань з tasks.py

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Збереження стану користувачів: score, used tasks, skips
user_states = {}

# Бали за рівень
points_map = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "bonus": 5
}

def get_new_task(user_id):
    used = user_states[user_id]["used"]
    level = random.choice(list(tasks.keys()))
    available = [t for t in tasks[level] if t not in used]
    if not available:
        # Шукаємо завдання в інших рівнях, якщо на вибраному рівні немає
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

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {
        "score": 0,
        "used": set(),
        "skips": 0,
        "consecutive_skips": 0
    }
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Нове завдання"))
    kb.add(KeyboardButton("Прийняти завдання"))
    kb.add(KeyboardButton("Виконано"))
    kb.add(KeyboardButton("Пропустити"))
    kb.add(KeyboardButton("Мій рахунок"))
    kb.add(KeyboardButton("Список виконаних"))
    kb.add(KeyboardButton("Закінчити гру"))
    await message.answer("Вітаю в Sex Bingo! Натисни кнопку 'Нове завдання', щоб почати.", reply_markup=kb)

@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        await message.answer("Спочатку введи /start")
        return

    text = message.text.lower()

    if text == "нове завдання":
        # Нове завдання пропонуємо, але не ставимо в активні, поки не прийняли
        task, level = get_new_task(user_id)
        if task is None:
            await message.answer("Всі завдання виконані! Вітаємо 🎉")
            return
        user_states[user_id]["proposed_task"] = (task, level)
        points = points_map[level]
        await message.answer(f"Пропонуємо тобі завдання ({level} рівень, {points} балів):\n\n{task}\n\nНатисни 'Прийняти завдання' щоб його взяти або 'Пропустити' щоб відмовитись.")

    elif text == "прийняти завдання":
        if "proposed_task" not in user_states[user_id]:
            await message.answer("Немає запропонованого завдання. Натисни 'Нове завдання' для отримання.")
            return
        task, level = user_states[user_id]["proposed_task"]
        user_states[user_id]["current_task"] = task
        user_states[user_id]["current_level"] = level
        user_states[user_id]["skips"] = 0
        user_states[user_id]["proposed_task"] = None
        await message.answer(f"Завдання прийнято:\n\n{task}\n\nПісля виконання натисни 'Виконано'.")

    elif text == "пропустити":
        # Пропуск не прийнятого завдання
        if "proposed_task" in user_states[user_id] and user_states[user_id]["proposed_task"]:
            user_states[user_id]["proposed_task"] = None
        user_states[user_id]["consecutive_skips"] += 1
        if user_states[user_id]["consecutive_skips"] > 2:
            user_states[user_id]["score"] -= 1
            user_states[user_id]["consecutive_skips"] = 0
            await message.answer("Третій пропуск підряд — мінус 1 бал.")
        else:
            await message.answer(f"Завдання пропущено без штрафу ({user_states[user_id]['consecutive_skips']} пропуски підряд).")

    elif text == "виконано":
        if "current_task" not in user_states[user_id]:
            await message.answer("Немає активного завдання. Натисни 'Нове завдання'.")
            return
        level = user_states[user_id]["current_level"]
        points = points_map[level]
        user_states[user_id]["score"] += points
        user_states[user_id]["skips"] = 0
        user_states[user_id]["consecutive_skips"] = 0
        # Позначити завдання як виконане — воно вже додано в used під час get_new_task
        user_states[user_id].pop("current_task")
        user_states[user_id].pop("current_level")
        await message.answer(f"Завдання виконано! +{points} балів.\nТвій рахунок: {user_states[user_id]['score']} балів")

    elif text == "мій рахунок":
        score = user_states[user_id]["score"]
        await message.answer(f"Твій поточний рахунок: {score} балів")

    elif text == "список виконаних":
        done = user_states[user_id]["used"]
        if not done:
            await message.answer("Поки що не виконано жодного завдання.")
        else:
            await message.answer("Виконані завдання:\n" + "\n".join(done))

    elif text == "закінчити гру":
        score = user_states[user_id]["score"]
        await message.answer(f"Гру завершено. Твій підсумковий рахунок: {score} балів.\nЩоб почати знову — введи /start")
        del user_states[user_id]

    else:
        await message.answer("Натисни кнопку на клавіатурі або введи /start для початку.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

