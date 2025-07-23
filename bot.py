import logging
import random
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from tasks import tasks  # Має бути файл tasks.py з завданнями

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Збереження стану користувачів: score, used tasks, skips, current_task, current_level
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
    # Вибір рівня складності рандомно
    level = random.choice(list(tasks.keys()))
    available = [t for t in tasks[level] if t not in used]
    if not available:
        # Якщо немає доступних завдань цього рівня - шукаємо в інших рівнях
        for lvl in tasks.keys():
            available = [t for t in tasks[lvl] if t not in used]
            if available:
                level = lvl
                break
    if not available:
        return None, None  # Всі завдання виконані
    task = random.choice(available)
    return task, level

def task_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Прийняти завдання", callback_data="accept_task"),
        InlineKeyboardButton("Відмовитись", callback_data="decline_task")
    )
    return keyboard

def active_task_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Завдання виконано", callback_data="complete_task"),
        InlineKeyboardButton("Пропустити", callback_data="skip_task")
    )
    return keyboard

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {
        "score": 0,
        "used": set(),
        "skips": 0,
        "current_task": None,
        "current_level": None,
        "task_accepted": False
    }
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Нове завдання"))
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
        if user_states[user_id]["task_accepted"]:
            await message.answer("Спочатку виконай або пропусти поточне завдання!")
            return

        task, level = get_new_task(user_id)
        if task is None:
            await message.answer("Всі завдання виконані! Вітаємо 🎉")
            return
        user_states[user_id]["current_task"] = task
        user_states[user_id]["current_level"] = level
        user_states[user_id]["task_accepted"] = False

        await message.answer(
            f"Твоє завдання ({level} рівень, {points_map[level]} балів):\n\n{task}",
            reply_markup=task_keyboard()
        )

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

@dp.callback_query_handler(lambda c: c.data in ["accept_task", "decline_task", "complete_task", "skip_task"])
async def process_task_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    if user_id not in user_states:
        await callback_query.answer("Спочатку введи /start")
        return

    state = user_states[user_id]

    if callback_query.data == "accept_task":
        if state["current_task"] is None:
            await callback_query.answer("Нема активного завдання.")
            return
        if state["task_accepted"]:
            await callback_query.answer("Завдання вже прийнято.")
            return
        state["task_accepted"] = True
        await callback_query.message.edit_reply_markup(active_task_keyboard())
        await callback_query.answer("Завдання прийнято! Удачі :)")

    elif callback_query.data == "decline_task":
        if state["current_task"] is None:
            await callback_query.answer("Нема активного завдання.")
            return
        state["current_task"] = None
        state["current_level"] = None
        state["task_accepted"] = False
        await callback_query.message.edit_text("Завдання відхилено. Натисни 'Нове завдання' щоб отримати інше.")
        await callback_query.answer()

    elif callback_query.data == "complete_task":
        if not state["task_accepted"]:
            await callback_query.answer("Спочатку прийми завдання.")
            return
        points = points_map[state["current_level"]]
        state["score"] += points
        state["skips"] = 0
        state["used"].add(state["current_task"])
        state["current_task"] = None
        state["current_level"] = None
        state["task_accepted"] = False
        await callback_query.message.edit_text(f"Завдання виконано! +{points} балів.\nТвій рахунок: {state['score']} балів.")
        await callback_query.answer()

    elif callback_query.data == "skip_task":
        if not state["task_accepted"]:
            await callback_query.answer("Спочатку прийми завдання.")
            return
        state["skips"] += 1
        state["used"].add(state["current_task"])
        state["current_task"] = None
        state["current_level"] = None
        state["task_accepted"] = False
        if state["skips"] > 2:
            state["score"] -= 1
            state["skips"] = 0
            await callback_query.message.edit_text("Третій пропуск підряд — мінус 1 бал.")
        else:
            await callback_query.message.edit_text(f"Завдання пропущено без штрафу ({state['skips']} пропуски підряд).")
        await callback_query.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
