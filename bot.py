import logging
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types

from tasks import TASKS  # tasks = [{'text': '...', 'level': 'easy'}, ...]

API_TOKEN = '7470253170:AAHX7NqY3L3H4pdCXVeDPsMXPvz8DM0_L70'  # 🔁 Замінити на свій токен

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

users = {}
active_games = {}
assigned_tasks = set()

def get_remaining_tasks():
    return len([t for t in TASKS if t['text'] not in assigned_tasks])

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
            parse_mode="Markdown"
        )
    else:
        await message.answer("Ти вже зареєстрований у грі.")

@dp.message_handler(commands=['invite'])
async def invite_partner(message: types.Message):
    inviter_id = message.from_user.id
    args = message.get_args()
    if not args.isdigit():
        await message.answer("Введи ID партнера, наприклад: /invite 123456789")
        return

    partner_id = int(args)
    if partner_id not in users:
        await message.answer("Цей ID не зареєстровано.")
        return

    if users[inviter_id]['partner'] or users[partner_id]['partner']:
        await message.answer("Один із гравців вже має партнера.")
        return

    users[inviter_id]['partner'] = partner_id
    users[partner_id]['partner'] = inviter_id
    active_games[frozenset([inviter_id, partner_id])] = True
    await message.answer("Гру створено! Почніть гру командою /task")

    try:
        await bot.send_message(partner_id, f"{users[inviter_id]['name']} запросив тебе до гри. Почніть гру командою /task.")
    except Exception:
        pass

@dp.message_handler(commands=['task'])
async def send_task(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user or not user['partner']:
        await message.answer("Ти не в парі. Зареєструйся /register або запроси /invite <ID>")
        return

    if user['current_task']:
        await message.answer("У тебе вже є активне завдання.")
        return

    available_tasks = [t for t in TASKS if t['text'] not in assigned_tasks]
    if not available_tasks:
        await message.answer("Усі завдання виконано 🎉")
        return

    task = random.choice(available_tasks)
    assigned_tasks.add(task['text'])

    duration = timedelta(days=1) if task['level'] != 'hard' else timedelta(days=7)
    deadline = datetime.now() + duration

    user['current_task'] = {'text': task['text'], 'deadline': deadline}
    
    partner_id = user['partner']
    partner = users[partner_id]
    partner_name = partner['name']

    await message.answer(
        f"📝 Завдання:\n{task['text']}\n"
        f"⏰ Термін виконання: {duration.days} днів\n\n"
        "✅ /accept — прийняти\n❌ /skip — відмовитись"
    )

    try:
        await bot.send_message(partner_id, f"{user['name']} отримав нове завдання.")
    except Exception:
        pass

@dp.message_handler(commands=['accept'])
async def accept_task(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user or not user['current_task']:
        await message.answer("Немає завдання.")
        return

    task_text = user['current_task']['text']
    user['accepted_tasks'].append(user['current_task'])
    user['current_task'] = None
    user['skips'] = 0

    await message.answer(f"✅ Завдання прийнято: {task_text}")

    partner_id = user['partner']
    if partner_id:
        await bot.send_message(partner_id, f"{user['name']} прийняв завдання: {task_text}")

@dp.message_handler(commands=['skip'])
async def skip_task(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user or not user['current_task']:
        await message.answer("Немає завдання для пропуску.")
        return

    user['skips'] += 1
    text = user['current_task']['text']
    user['current_task'] = None
    assigned_tasks.discard(text)

    if user['skips'] >= 3:
        user['score'] -= 1
        user['skips'] = 0
        await message.answer("❌ 3 пропуски підряд. -1 бал.")

    else:
        await message.answer(f"Пропущено завдання: {text}")

@dp.message_handler(commands=['score'])
async def show_score(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user:
        await message.answer("Ти ще не в грі.")
        return

    partner = users.get(user.get('partner'))
    msg = f"Твій рахунок: {user['score']} балів"
    if partner:
        msg += f"\nРахунок партнера ({partner['name']}): {partner['score']} балів"

    await message.answer(msg)

@dp.message_handler(commands=['status'])
async def task_status(message: types.Message):
    user_id = message.from_user.id
    user = users.get(user_id)

    if not user:
        await message.answer("Ти не зареєстрований.")
        return

    msg = f"📊 Залишилось завдань: {get_remaining_tasks()}"
    if user['current_task']:
        deadline = user['current_task']['deadline']
        time_left = deadline - datetime.now()
        msg += f"\n🕓 Твоє завдання: {user['current_task']['text']}\nЗалишилось: {time_left.days} днів"
    else:
        msg += "\nУ тебе немає активного завдання."

    await message.answer(msg)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
