import logging
import random
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from tasks import tasks, bonus_tasks  # задачі окремо імпортуємо

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

# Словник активних ігор: chat_id -> гра
games = {}

# Для простоти стартуємо гру з 2 гравців за командою /startgame (треба їх позначити)
# Кожен гравець отримує свій user_id у рамках цієї гри

def get_new_task_for_player(game, user_id):
    used = game["players"][user_id]["used"]
    # Рандомно вибираємо рівень
    level = random.choice(list(tasks.keys()))
    available = [t for t in tasks[level] if t not in used]
    if not available:
        # Шукаємо в інших рівнях
        for lvl in tasks.keys():
            available = [t for t in tasks[lvl] if t not in used]
            if available:
                level = lvl
                break
    if not available:
        return None, None
    task = random.choice(available)
    used.add(task)
    return task, level

def get_new_bonus_task(game):
    done = game["bonus_done"]
    available = [t for t in bonus_tasks if t not in done]
    if not available:
        return None
    task = random.choice(available)
    done.add(task)
    return task

def create_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Нове завдання"))
    kb.add(KeyboardButton("Виконано"))
    kb.add(KeyboardButton("Пропустити"))
    kb.add(KeyboardButton("Мій рахунок"))
    kb.add(KeyboardButton("Список виконаних"))
    kb.add(KeyboardButton("Статус гри"))
    kb.add(KeyboardButton("Закінчити гру"))
    return kb

@dp.message_handler(commands=['startgame'])
async def cmd_startgame(message: types.Message):
    chat_id = message.chat.id

    # Перевіряємо, що в чаті двоє гравців (для приватних чатів це user_id == chat_id)
    # Для простоти вважаємо, що гру грають два користувача, які написали /join

    await message.answer("Гра запускається!\nЩоб приєднатись, надішліть /join", reply_markup=None)

    # Ініціалізуємо пусту гру, чекаємо на 2 гравців
    games[chat_id] = {
        "players": {},  # user_id -> info
        "order": [],
        "bonus_done": set(),
        "active_bonus_task": None,
        "started": False
    }

@dp.message_handler(commands=['join'])
async def cmd_join(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.full_name

    if chat_id not in games:
        await message.answer("Гра не запущена. Спочатку надішли /startgame")
        return

    game = games[chat_id]

    if len(game["players"]) >= 2:
        await message.answer("Вже є 2 гравці у грі.")
        return

    if user_id in game["players"]:
        await message.answer("Ти вже у грі.")
        return

    game["players"][user_id] = {
        "score": 0,
        "used": set(),
        "skips": 0,
        "current_task": None,
        "current_level": None,
        "username": username
    }

    game["order"].append(user_id)

    await message.answer(f"{username} приєднався до гри!")

    if len(game["players"]) == 2:
        game["started"] = True
        kb = create_keyboard()
        for uid in game["players"]:
            task, level = get_new_task_for_player(game, uid)
            game["players"][uid]["current_task"] = task
            game["players"][uid]["current_level"] = level
            game["players"][uid]["skips"] = 0
            await bot.send_message(uid, f"Гра почалась! Твоє перше завдання ({level} рівень):\n\n{task}", reply_markup=kb)
        # Надсилаємо повідомлення у чат, що гра почалась
        await bot.send_message(chat_id, "Гра розпочалась! Кожен отримав завдання у приватні повідомлення.")

@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.lower()

    if chat_id not in games:
        await message.answer("Гра не запущена. Надішли /startgame щоб розпочати.")
        return

    game = games[chat_id]

    if user_id not in game["players"]:
        await message.answer("Ти не в грі. Надішли /join щоб приєднатись.")
        return

    player = game["players"][user_id]

    kb = create_keyboard()

    if text == "нове завдання":
        if player["current_task"] is not None:
            await message.answer("У тебе ще є активне завдання! Спочатку виконай або пропусти його.")
            return
        task, level = get_new_task_for_player(game, user_id)
        if task is None:
            await message.answer("Всі завдання виконані!")
            return
        player["current_task"] = task
        player["current_level"] = level
        player["skips"] = 0
        await message.answer(f"Нове завдання ({level} рівень, {points_map[level]} балів):\n\n{task}", reply_markup=kb)

    elif text == "виконано":
        if player["current_task"] is None:
            await message.answer("У тебе немає активного завдання. Запроси нове завдання кнопкою 'Нове завдання'.")
            return
        player["score"] += points_map[player["current_level"]]
        player["skips"] = 0
        # Додаємо завдання у виконані
        player["used"].add(player["current_task"])
        player["current_task"] = None
        player["current_level"] = None
        await message.answer(f"Завдання виконано! Твій рахунок: {player['score']} балів.", reply_markup=kb)

    elif text == "пропустити":
        if player["current_task"] is None:
            await message.answer("У тебе немає активного завдання, щоб пропустити.", reply_markup=kb)
            return
        player["skips"] += 1
        player["used"].add(player["current_task"])
        player["current_task"] = None
        player["current_level"] = None
        if player["skips"] > 2:
            player["score"] -= 1
            player["skips"] = 0
            await message.answer("Третій пропуск підряд — мінус 1 бал.", reply_markup=kb)
        else:
            await message.answer(f"Завдання пропущено без штрафу ({player['skips']} пропуски підряд).", reply_markup=kb)

    elif text == "мій рахунок":
        await message.answer(f"Твій поточний рахунок: {player['score']} балів.", reply_markup=kb)

    elif text == "список виконаних":
        if not player["used"]:
            await message.answer("Поки що не виконано жодного завдання.", reply_markup=kb)
        else:
            await message.answer("Виконані завдання:\n" + "\n".join(player["used"]), reply_markup=kb)

    elif text == "статус гри":
        msg = "Статус гри:\n"
        for uid in game["order"]:
            p = game["players"][uid]
            msg += f"{p['username']}: {p['score']} балів, виконано {len(p['used'])} завдань\n"
        await message.answer(msg, reply_markup=kb)

    elif text == "закінчити гру":
        msg = "Гра завершена. Підсумки:\n"
        for uid in game["order"]:
            p = game["players"][uid]
            msg += f"{p['username']}: {p['score']} балів, виконано {len(p['used'])} завдань\n"
        await message.answer(msg)
        del games[chat_id]

    else:
        await message.answer("Використовуй кнопки меню або /startgame для початку.", reply_markup=kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
