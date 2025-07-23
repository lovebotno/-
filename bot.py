import logging
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from tasks import tasks  # Твоя структура завдань з рівнями

API_TOKEN = '7808304545:AAEagMXlNfvHd3zG-w21uJHKcEznjaaIJRM'  # 🔁 Замінити на свій токен

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

users = {}
active_games = {}

def main_keyboard(has_active_task: bool):
    """
    Формує головне меню.
    Якщо є активне завдання, додаємо кнопку 'Підтвердити виконання'
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton("Реєстрація"),
        KeyboardButton("Мій ID"),
        KeyboardButton("Запросити партнера"),
        KeyboardButton("Отримати завдання"),
        KeyboardButton("Пропустити завдання"),
        KeyboardButton("Рахунок"),
        KeyboardButton("Статус"),
    ]
    if has_active_task:
        buttons.insert(4, KeyboardButton("Підтвердити виконання"))
    keyboard.add(*buttons)
    return keyboard

def get_remaining_tasks():
    all_assigned = set()
    for user in users.values():
        for t in user['accepted_tasks']:
            all_assigned.add(t['text'])
        if user['current_task']:
            all_assigned.add(user['current_task']['text'])
    total_tasks = sum(len(v) for v in tasks.values())
    return total_tasks - len(all_assigned)

@dp.message_handler(commands=['start', 'register'])
async def register(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {
            'name': message.from_user.first_name,
            'score': 0,
            'current_task': None,
            'skips': 0,
            'partner': None,
            'accepted_tasks': [],
        }
        await message.answer(
            f"Вітаю, {message.from_user.first_name}! Тебе зареєстровано у грі ❤️\n"
            f"Твій Telegram ID: `{user_id}`\n"
            "Передай цей ID партнеру, щоб він запросив тебе до гри:\n"
            "`/invite <твій_ID>`",
            parse_mode="Markdown",
            reply_markup=main_keyboard(has_active_task=False)
        )
    else:
        has_task = users[user_id]['current_task'] is not None
        await message.answer("Ти вже зареєстрований у грі.", reply_markup=main_keyboard(has_active_task=has_task))

@dp.message_handler(lambda message: message.text == "Мій ID")
async def show_my_id(message: types.Message):
    user_id = message.from_user.id
    has_task = users.get(user_id, {}).get('current_task') is not None
    await message.answer(f"Твій Telegram ID: `{user_id}`", parse_mode="Markdown", reply_markup=main_keyboard(has_active_task=has_task))

@dp.message_handler(lambda message: message.text == "Запросити партнера")
async def invite_partner_handler(message: types.Message):
    await message.answer("Введи команду у форматі:\n/invite <ID партнера>", reply_markup=main_keyboard(has_active_task=users.get(message.from_user.id, {}).get('current_task') is not None))

@dp.message_handler(commands=['invite'])
async def invite_partner(message: types.Message):
    inviter_id = message.from_user.id
    args = message.get_args()
    if not args.isdigit():
        await message.answer("Введи ID партнера, наприклад: /invite 123456789", reply_markup=main_keyboard(has_active_task=users.get(inviter_id, {}).get('current_task') is not None))
        return

    partner_id = int(args)
    if partner_id not in users:
        await message.answer("Цей ID не зареєстровано.", reply_markup=main_keyboard(has_active_task=users.get(inviter_id, {}).get('current_task') is not None))
        return

    if users[inviter_id]['partner'] or users[partner_id]['partner']:
        await message.answer("Один із гравців вже має партнера.", reply_markup=main_keyboard(has_active_task=users.get(inviter_id, {}).get('current_task') is not None))
        return

    users[inviter_id]['partner'] = partner_id
    users[partner_id]['partner'] = inviter_id
    active_games[frozenset([inviter_id, partner_id])] = True
    await message.answer("Гру створено! Почніть гру кнопкою 'Отримати завдання'", reply_markup=main_keyboard(has_active_task=users.get(inviter_id, {}).get('current_task') is not None))

    try:
        await bot.send_message(partner_id, f"{users[inviter_id]['name']} запросив тебе до гри. Почніть гру кнопкою 'Отримати завдання'.", reply_markup=main_keyboard(has_active_task=users.get(partner_id, {}).get('current_task') is not None))
    except Exception:
        pass

@dp.message_handler(lambda message: message.text == "Отримати завдання")
async def send_task(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    has_task = user['current_task'] is not None if user else False

    if not user or not user['partner']:
        await message.answer("Ти не в парі. Зареєструйся /register або запроси партнера /invite <ID>", reply_markup=main_keyboard(has_active_task=has_task))
        return

    if has_task:
        await message.answer("У тебе вже є активне завдання. Спочатку виконай його або пропусти.", reply_markup=main_keyboard(has_active_task=True))
        return

    all_assigned = set()
    for u in users.values():
        if u['current_task']:
            all_assigned.add(u['current_task']['text'])
        for t in u['accepted_tasks']:
            all_assigned.add(t['text'])

    all_tasks_list = []
    for level, arr in tasks.items():
        for text in arr:
            all_tasks_list.append({'text': text, 'level': level})

    available_tasks = [t for t in all_tasks_list if t['text'] not in all_assigned]

    if not available_tasks:
        await message.answer("Усі завдання виконано 🎉", reply_markup=main_keyboard(has_active_task=False))
        return

    task = random.choice(available_tasks)
    duration_days = 1 if task['level'] == 'easy' else 3 if task['level'] == 'medium' else 7
    deadline = datetime.now() + timedelta(days=duration_days)

    user['current_task'] = {'text': task['text'], 'deadline': deadline, 'level': task['level']}

    partner_id = user['partner']

    await message.answer(
        f"📝 Завдання ({task['level']} рівень):\n{task['text']}\n"
        f"⏰ Термін виконання: {duration_days} днів\n\n"
        "Натисни 'Підтвердити виконання', коли виконаєш завдання.",
        reply_markup=main_keyboard(has_active_task=True)
    )

    try:
        await bot.send_message(partner_id, f"{user['name']} отримав нове завдання: {task['text']}", reply_markup=main_keyboard(has_active_task=users.get(partner_id, {}).get('current_task') is not None))
    except Exception:
        pass

@dp.message_handler(lambda message: message.text == "Підтвердити виконання")
async def accept_task(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user or not user['current_task']:
        await message.answer("Немає активного завдання для підтвердження.", reply_markup=main_keyboard(has_active_task=False))
        return

    task_text = user['current_task']['text']
    level = user['current_task']['level']
    points_map = {'easy': 1, 'medium': 2, 'hard': 3, 'bonus': 5}
    user['accepted_tasks'].append(user['current_task'])
    user['current_task'] = None
    user['skips'] = 0
    user['score'] += points_map.get(level, 1)

    await message.answer(f"✅ Завдання прийнято: {task_text}\n+{points_map.get(level,1)} балів", reply_markup=main_keyboard(has_active_task=False))

    partner_id = user['partner']
    if partner_id:
        await bot.send_message(partner_id, f"{user['name']} прийняв завдання: {task_text}", reply_markup=main_keyboard(has_active_task=users.get(partner_id, {}).get('current_task') is not None))

@dp.message_handler(lambda message: message.text == "Пропустити завдання")
async def skip_task(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    has_task = user['current_task'] is not None if user else False

    if not user or not has_task:
        await message.answer("Немає завдання для пропуску.", reply_markup=main_keyboard(has_active_task=False))
        return

    user['skips'] += 1
    text = user['current_task']['text']
    user['current_task'] = None

    if user['skips'] >= 3:
        user['score'] -= 1
        user['skips'] = 0
        await message.answer("❌ 3 пропуски підряд. -1 бал.", reply_markup=main_keyboard(has_active_task=False))
    else:
        await message.answer(f"Пропущено завдання: {text}", reply_markup=main_keyboard(has_active_task=False))

@dp.message_handler(lambda message: message.text == "Рахунок")
async def show_score(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    has_task = user['current_task'] is not None if user else False

    if not user:
        await message.answer("Ти ще не в грі.", reply_markup=main_keyboard(has_active_task=False))
        return

    partner = users.get(user.get('partner'))
    msg = f"Твій рахунок: {user['score']} балів"
    if partner:
        msg += f"\nРахунок партнера ({partner['name']}): {partner['score']} балів"

    await message.answer(msg, reply_markup=main_keyboard(has_active_task=has_task))

@dp.message_handler(lambda message: message.text == "Статус")
async def task_status(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    has_task = user['current_task'] is not None if user else False

    if not user:
        await message.answer("Ти не зареєстрований.", reply_markup=main_keyboard(has_active_task=False))
        return

    msg = f"📊 Залишилось завдань: {get_remaining_tasks()}"
    if has_task:
        deadline = user['current_task']['deadline']
        time_left = deadline - datetime.now()
        days_left = max(time_left.days, 0)
        msg += f"\n🕓 Твоє завдання: {user['current_task']['text']}\nЗалишилось: {days_left} днів"
    else:
        msg += "\nУ тебе немає активного завдання."

    await message.answer(msg, reply_markup=main_keyboard(has_active_task=has_task))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
