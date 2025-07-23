import logging
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from tasks import tasks  # ваш файл з завданнями

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_states = {}

points_map = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "bonus": 5
}

def get_deadline_by_level(level: str) -> datetime:
    now = datetime.now()
    if level == "hard":
        return now + timedelta(days=7)  # 7 днів на виконання
    else:
        return now + timedelta(hours=24)  # 24 години для інших

def get_new_task(user_id):
    used = user_states[user_id]["used"]
    # Вибираємо рівень складності випадково
    level = random.choice(list(tasks.keys()))
    available = [t for t in tasks[level] if t not in used and t not in user_states[user_id]["completed_by_any"]]
    if not available:
        for lvl in tasks.keys():
            available = [t for t in tasks[lvl] if t not in used and t not in user_states[user_id]["completed_by_any"]]
            if available:
                level = lvl
                break
    if not available:
        return None, None
    task = random.choice(available)
    return task, level

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {
        "score": 0,
        "used": set(),
        "skips": 0,
        "proposed_task": None,
        "proposed_level": None,
        "proposed_deadline": None,
        "completed_by_any": set()
    }
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Нове завдання"))
    kb.add(KeyboardButton("Пропустити"))
    kb.add(KeyboardButton("Мій рахунок"))
    kb.add(KeyboardButton("Список виконаних"))
    kb.add(KeyboardButton("Закінчити гру"))
    kb.add(KeyboardButton("Прийняти завдання"))
    kb.add(KeyboardButton("Завдання виконано"))
    await message.answer("Вітаю в Sex Bingo! Натисни 'Нове завдання', щоб отримати завдання.", reply_markup=kb)

@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        await message.answer("Спочатку введи /start")
        return

    text = message.text.lower()

    state = user_states[user_id]

    if text == "нове завдання":
        task, level = get_new_task(user_id)
        if task is None:
            await message.answer("Всі завдання виконані! Вітаємо 🎉")
            return
        deadline = get_deadline_by_level(level)
        state["proposed_task"] = task
        state["proposed_level"] = level
        state["proposed_deadline"] = deadline
        deadline_str = deadline.strftime("%d-%m-%Y %H:%M")
        await message.answer(
            f"Нове завдання ({level} рівень, {points_map[level]} балів):\n\n{task}\n\n"
            f"Термін виконання: до {deadline_str}\n\n"
            "Якщо готовий виконати, натисни 'Прийняти завдання'. Якщо ні — 'Пропустити'."
        )

    elif text == "прийняти завдання":
        if state["proposed_task"] is None:
            await message.answer("Спочатку отримай завдання через кнопку 'Нове завдання'.")
            return
        # Прийняли завдання — додаємо у used, ставимо поточне активне завдання
        task = state["proposed_task"]
        level = state["proposed_level"]
        state["used"].add(task)
        state["current_task"] = task
        state["current_level"] = level
        state["current_deadline"] = state["proposed_deadline"]
        state["proposed_task"] = None
        state["proposed_level"] = None
        state["proposed_deadline"] = None
        state["skips"] = 0
        await message.answer(f"Завдання прийнято! Виконай його до {state['current_deadline'].strftime('%d-%m-%Y %H:%M')}. Коли виконаєш — натисни 'Завдання виконано'.")

    elif text == "завдання виконано":
        if "current_task" not in state or state["current_task"] is None:
            await message.answer("У тебе немає активного завдання. Спочатку прийми завдання.")
            return
        # Перевірка чи не прострочено
        now = datetime.now()
        deadline = state.get("current_deadline")
        if deadline and now > deadline:
            await message.answer("На жаль, ти не встиг виконати завдання вчасно. Балів не нараховано.")
            # Очищаємо активне завдання, не даємо бали
            state["current_task"] = None
            state["current_level"] = None
            state["current_deadline"] = None
            return
        # Нараховуємо бали
        level = state["current_level"]
        points = points_map.get(level, 1)
        state["score"] += points
        # Додаємо до списку завдань, що виконані будь-ким (щоб не повторювали)
        state["completed_by_any"].add(state["current_task"])
        # Очищаємо активне завдання
        state["current_task"] = None
        state["current_level"] = None
        state["current_deadline"] = None
        await message.answer(f"Завдання виконано! +{points} балів.\nПоточний рахунок: {state['score']} балів.")

    elif text == "пропустити":
        state["skips"] += 1
        if state["skips"] > 2:
            state["score"] -= 1
            state["skips"] = 0
            # Якщо було активне завдання, видаляємо його
            if "current_task" in state:
                state["current_task"] = None
                state["current_level"] = None
                state["current_deadline"] = None
            await message.answer("Третій пропуск підряд — мінус 1 бал.")
        else:
            await message.answer(f"Пропущено завдання без штрафу ({state['skips']} пропуски).")
        # При пропуску пропонуємо отримати нове завдання
        state["proposed_task"] = None
        state["proposed_level"] = None
        state["proposed_deadline"] = None

    elif text == "мій рахунок":
        await message.answer(f"Твій поточний рахунок: {state['score']} балів")

    elif text == "список виконаних":
        done = state["completed_by_any"]
        if not done:
            await message.answer("Поки що не виконано жодного завдання.")
        else:
            await message.answer("Виконані завдання:\n" + "\n".join(done))

    elif text == "закінчити гру":
        await message.answer(f"Гру завершено. Твій підсумковий рахунок: {state['score']} балів.\nЩоб почати знову — введи /start")
        del user_states[user_id]

    else:
        await message.answer("Натисни кнопку на клавіатурі або введи /start для початку.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
