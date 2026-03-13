import logging
import random
import time
import uuid
import json
import os
import aiohttp
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = "8725028171:AAEPE1789oMMMxyA8rSM3bPFfA9SSf4WAB8"

# Файлы для сохранения данных
NICKNAMES_FILE = 'nicknames.json'
STATS_FILE = 'stats.json'

# Загрузка сохраненных данных
def load_data():
    global user_nicknames, user_stats
    try:
        if os.path.exists(NICKNAMES_FILE):
            with open(NICKNAMES_FILE, 'r', encoding='utf-8') as f:
                user_nicknames = json.load(f)
                user_nicknames = {int(k): v for k, v in user_nicknames.items()}
        else:
            user_nicknames = {}
    except:
        user_nicknames = {}
    
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                user_stats = json.load(f)
                user_stats = {int(k): v for k, v in user_stats.items()}
        else:
            user_stats = {}
    except:
        user_stats = {}

# Сохранение данных
def save_data():
    try:
        with open(NICKNAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in user_nicknames.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения ников: {e}")
    
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in user_stats.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {e}")

# Загружаем данные при старте
load_data()

# Хранилища данных
games = {}
player_game = {}
lobbies = {}
waiting_for_opponent = []

# Временные хранилища
temp_lobby_name = {}
temp_lobby_password = {}
temp_lobby_join = {}
temp_set_nickname = {}

class TicTacToe:
    def __init__(self, game_id, player1_id, player2_id=None, mode='bot', difficulty='easy', total_games=1, lobby_id=None):
        self.game_id = game_id
        self.board = ['⬜'] * 9
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.current_turn = player1_id
        self.mode = mode
        self.difficulty = difficulty
        self.game_over = False
        self.winner = None
        self.last_move_time = time.time()
        self.player1_message_id = None
        self.player2_message_id = None
        self.player1_chat_id = None
        self.player2_chat_id = None
        self.player1_score = 0
        self.player2_score = 0
        self.total_games = total_games
        self.current_game = 1
        self.lobby_id = lobby_id
        self.voice_enabled = True
        
    def make_move(self, position, player_id):
        if self.game_over:
            return False, "Игра уже окончена"
        
        if player_id != self.current_turn:
            return False, "Сейчас не ваш ход"
        
        if self.board[position] != '⬜':
            return False, "Эта клетка уже занята"
        
        # НОРМАЛЬНЫЕ КРЕСТИКИ И НОЛИКИ
        if player_id == self.player1_id:
            symbol = '❌'
        else:
            symbol = '⭕'
        
        self.board[position] = symbol
        self.last_move_time = time.time()
        
        if self.check_win(symbol):
            self.winner = player_id
            self.game_over = True
            if player_id == self.player1_id:
                self.player1_score += 1
            else:
                self.player2_score += 1
            return True, "win"
        
        if self.check_draw():
            self.game_over = True
            return True, "draw"
        
        if self.mode == 'multiplayer':
            self.current_turn = self.player2_id if self.current_turn == self.player1_id else self.player1_id
        else:
            self.current_turn = 'bot' if self.current_turn == self.player1_id else self.player1_id
        
        return True, "continue"
    
    def check_win(self, symbol):
        win_combinations = [
            [0,1,2], [3,4,5], [6,7,8],
            [0,3,6], [1,4,7], [2,5,8],
            [0,4,8], [2,4,6]
        ]
        for combo in win_combinations:
            if all(self.board[i] == symbol for i in combo):
                return True
        return False
    
    def check_draw(self):
        return '⬜' not in self.board
    
    def get_board_display(self):
        board_str = ""
        for i in range(9):
            board_str += self.board[i]
            if (i + 1) % 3 == 0:
                board_str += "\n"
            else:
                board_str += " "
        return board_str
    
    def get_score_display(self):
        if self.mode == 'multiplayer' or (self.mode == 'bot' and self.total_games > 1):
            return f"Счет: {self.player1_score} : {self.player2_score}"
        return ""

# Класс для TTS с РАЗНЫМИ ответами
class VoiceBot:
    def __init__(self):
        self.voice_map = {
            'easy': 'ru-RU-OstapenkoNeural',      # Мягкий женский
            'medium': 'ru-RU-DariyaNeural',        # Нейтральный женский
            'hard': 'ru-RU-MikhailNeural',         # Мужской
            'impossible': 'ru-RU-CatherineNeural'  # Загадочный женский
        }
        
        # РАЗНЫЕ ОТВЕТЫ ДЛЯ КАЖДОГО УРОВНЯ (20+ вариантов)
        self.responses = {
            'easy': [
                "Я только учусь, не судите строго!",
                "Ого, какой интересный ход!",
                "Я пока не очень умный, но стараюсь!",
                "Ты явно опытнее меня!",
                "Мне ещё многому нужно научиться!",
                "Интересно, интересно...",
                "Я просто делаю случайные ходы!",
                "Ты хорошо играешь!",
                "Ой, а куда я походил?",
                "Кажется, я проигрываю...",
                "Ничего, я только учусь!",
                "Твоя стратегия мне непонятна!",
                "Я пока не понимаю эту игру...",
                "Но я стараюсь!",
                "Может быть, в следующий раз повезёт?",
                "Ты слишком сильный соперник!",
                "Я просто новичок!",
                "Ого, как ты это сделал?",
                "Мне нравится с тобой играть!",
                "Давай ещё!"
            ],
            'medium': [
                "Неплохой ход, но я начинаю понимать!",
                "Интересная стратегия!",
                "Посмотрим, что будет дальше!",
                "Ты хорошо играешь!",
                "Я уже начинаю разбираться!",
                "Этот ход я ожидал!",
                "Хм, интересно...",
                "Твоя тактика становится понятнее!",
                "Я учусь на своих ошибках!",
                "С каждым ходом я умнею!",
                "Неплохо, неплохо...",
                "Ты достойный соперник!",
                "Я начинаю понимать твою стратегию!",
                "Это было предсказуемо!",
                "Хороший ход!",
                "Я тоже так могу!",
                "Интересная партия!",
                "Ты заставляешь меня думать!",
                "Уровень игры растёт!",
                "Давай посмотрим, кто кого!"
            ],
            'hard': [
                "Отличный ход, но я просчитал его!",
                "Я ожидал этого хода!",
                "Хорошая стратегия!",
                "Так держать!",
                "Это было предсказуемо.",
                "Я анализирую каждый твой ход!",
                "Ты играешь сильно!",
                "Но я тоже не лыком шит!",
                "Интересная тактика...",
                "Посмотрим, что дальше!",
                "Я на шаг впереди!",
                "Ты заставляешь меня напрягаться!",
                "Хорошая игра!",
                "Я просчитываю все варианты!",
                "Ты достойный противник!",
                "Этот ход я предусмотрел!",
                "Давай продолжим!",
                "Я в хорошей форме сегодня!",
                "Твои ходы становятся предсказуемыми!",
                "Интересно, кто победит?"
            ],
            'impossible': [
                "Я просчитал этот ход на 10 шагов вперёд!",
                "Ты играешь на удивление хорошо для человека!",
                "Интересно, что будет дальше...",
                "Я анализирую твою стратегию в реальном времени!",
                "Нейросеть довольна твоей игрой!",
                "Твой ход не стал для меня сюрпризом.",
                "Я вижу все возможные варианты!",
                "Ты хорошо играешь, но я лучше!",
                "Мои алгоритмы предсказали это!",
                "Человеческий разум так предсказуем...",
                "Но ты меня удивляешь!",
                "Интересный паттерн поведения!",
                "Я учусь на твоих ошибках!",
                "Твоя стратегия мне знакома!",
                "Я видел тысячи таких игр!",
                "Ты уникален в своём подходе!",
                "Нейросеть впечатлена!",
                "Давай посмотрим, на что ты способен!",
                "Я ждал этого хода!",
                "Ты достоин моего внимания!"
            ]
        }
    
    async def text_to_speech(self, text, difficulty='medium'):
        voice_name = self.voice_map.get(difficulty, 'ru-RU-DariyaNeural')
        url = f"https://api.streamelements.com/kappa/v2/speech?voice={voice_name}&text={text}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        return audio_data
        except Exception as e:
            logger.error(f"Ошибка TTS: {e}")
            return None
        
        return None
    
    def get_random_response(self, difficulty):
        """Возвращает случайный ответ для уровня сложности"""
        responses = self.responses.get(difficulty, self.responses['medium'])
        return random.choice(responses)

voice_bot = VoiceBot()

class BotPlayer:
    def __init__(self, difficulty='easy'):
        self.difficulty = difficulty
        
    def get_move(self, game):
        available = [i for i, cell in enumerate(game.board) if cell == '⬜']
        
        if not available:
            return None
        
        if self.difficulty == 'easy':
            return random.choice(available)
        
        elif self.difficulty == 'medium':
            if random.random() < 0.5:
                return self.get_smart_move(game, available)
            return random.choice(available)
        
        elif self.difficulty == 'hard':
            return self.get_smart_move(game, available)
        
        else:  # impossible
            return self.get_smart_move(game, available)
    
    def get_smart_move(self, game, available):
        # Победный ход
        for pos in available:
            game.board[pos] = '⭕'
            if game.check_win('⭕'):
                game.board[pos] = '⬜'
                return pos
            game.board[pos] = '⬜'
        
        # Блокировка
        for pos in available:
            game.board[pos] = '❌'
            if game.check_win('❌'):
                game.board[pos] = '⬜'
                return pos
            game.board[pos] = '⬜'
        
        # Центр
        if 4 in available:
            return 4
        
        # Углы
        corners = [0, 2, 6, 8]
        available_corners = [c for c in corners if c in available]
        if available_corners:
            return random.choice(available_corners)
        
        return random.choice(available)

def get_nickname(user_id):
    return user_nicknames.get(str(user_id), f"Игрок_{str(user_id)[:4]}")

async def update_both_players(context, game, text, keyboard=None):
    if game.player1_message_id and game.player1_chat_id:
        try:
            if keyboard:
                await context.bot.edit_message_text(
                    chat_id=game.player1_chat_id,
                    message_id=game.player1_message_id,
                    text=text,
                    reply_markup=keyboard
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=game.player1_chat_id,
                    message_id=game.player1_message_id,
                    text=text
                )
        except Exception as e:
            logger.error(f"Ошибка обновления у игрока 1: {e}")
    
    if game.player2_message_id and game.player2_chat_id:
        try:
            if keyboard:
                await context.bot.edit_message_text(
                    chat_id=game.player2_chat_id,
                    message_id=game.player2_message_id,
                    text=text,
                    reply_markup=keyboard
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=game.player2_chat_id,
                    message_id=game.player2_message_id,
                    text=text
                )
        except Exception as e:
            logger.error(f"Ошибка обновления у игрока 2: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    if user_id not in user_stats:
        user_stats[user_id] = {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0}
        save_data()
    
    welcome_text = (
        "🎮 **КРЕСТИКИ-НОЛИКИ**\n\n"
        f"Ваш ник: {get_nickname(user_id)}\n\n"
        "🎤 **ГОЛОСОВОЙ ЧАТ:**\n"
        "• Просто отправляй голосовые во время игры\n"
        "• Бот отвечает голосом (20+ вариантов)\n"
        "• Собеседник получает сразу\n\n"
        "👇 **Выберите режим:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Установить ник", callback_data='set_nickname')],
        [InlineKeyboardButton("🤖 Игра с ботом", callback_data='menu_bot')],
        [InlineKeyboardButton("👥 Игра с другом", callback_data='menu_friend')],
        [InlineKeyboardButton("📊 Статистика", callback_data='menu_stats')],
        [InlineKeyboardButton("❓ Помощь", callback_data='menu_help')]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    
    if data == 'set_nickname':
        temp_set_nickname[user_id] = True
        await query.edit_message_text("✏️ Введите ваш ник (до 20 символов):")
    
    elif data == 'menu_bot':
        keyboard = [
            [InlineKeyboardButton("🟢 Легкий", callback_data='bot_easy')],
            [InlineKeyboardButton("🟡 Средний", callback_data='bot_medium')],
            [InlineKeyboardButton("🔴 Сложный", callback_data='bot_hard')],
            [InlineKeyboardButton("🤖 Нейросеть", callback_data='bot_impossible')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]
        ]
        await query.edit_message_text(
            "🤖 Выберите уровень сложности:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_'):
        difficulty = data.split('_')[1]
        
        keyboard = [
            [InlineKeyboardButton("1 игра", callback_data=f'series_1_{difficulty}')],
            [InlineKeyboardButton("3 игры", callback_data=f'series_3_{difficulty}')],
            [InlineKeyboardButton("5 игр", callback_data=f'series_5_{difficulty}')],
            [InlineKeyboardButton("10 игр", callback_data=f'series_10_{difficulty}')],
            [InlineKeyboardButton("∞ Бесконечно", callback_data=f'series_inf_{difficulty}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            "🎮 Сколько игр сыграть?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('series_'):
        parts = data.split('_')
        if parts[1] == 'inf':
            total_games = 999999
            difficulty = parts[2]
        else:
            total_games = int(parts[1])
            difficulty = parts[2]
        
        game_id = str(uuid.uuid4())[:8]
        game = TicTacToe(game_id, user_id, mode='bot', difficulty=difficulty, total_games=total_games)
        
        games[game_id] = game
        player_game[user_id] = game_id
        
        difficulty_names = {
            'easy': '🟢 Легкий',
            'medium': '🟡 Средний',
            'hard': '🔴 Сложный',
            'impossible': '🤖 Нейросеть'
        }
        
        player_nick = get_nickname(user_id)
        games_count = "∞" if total_games == 999999 else str(total_games)
        
        if total_games > 1:
            header = f"{player_nick} (❌) vs Бот (⭕)\n{game.get_score_display()}\n"
            match_info = f"⚔️ Матч 1/{games_count}\n\n"
        else:
            header = f"{player_nick} (❌) vs Бот (⭕)\n"
            match_info = ""
        
        text = (match_info + header + game.get_board_display() + 
                f"\n{difficulty_names[difficulty]}\n"
                f"🎤 Голосовой чат: просто отправляй голосовые!\n"
                f"Ваш ход!")
        
        msg = await query.edit_message_text(
            text,
            reply_markup=create_game_keyboard(game_id, user_id)
        )
        
        game.player1_message_id = msg.message_id
        game.player1_chat_id = msg.chat_id
    
    elif data == 'menu_friend':
        keyboard = [
            [InlineKeyboardButton("🎮 Создать комнату", callback_data='friend_create')],
            [InlineKeyboardButton("🔍 Найти комнату", callback_data='friend_find')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]
        ]
        await query.edit_message_text(
            "👥 Игра с другом\n\nСоздайте комнату и отправьте ID другу:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == 'friend_create':
        keyboard = [
            [InlineKeyboardButton("1 игра", callback_data='create_1')],
            [InlineKeyboardButton("3 игры", callback_data='create_3')],
            [InlineKeyboardButton("5 игр", callback_data='create_5')],
            [InlineKeyboardButton("10 игр", callback_data='create_10')],
            [InlineKeyboardButton("∞ Бесконечно", callback_data='create_inf')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')]
        ]
        await query.edit_message_text(
            "🎮 Сколько игр сыграть?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('create_'):
        if data == 'create_inf':
            total_games = 999999
        else:
            total_games = int(data.split('_')[1])
        
        temp_lobby_name[user_id] = total_games
        await query.edit_message_text(
            f"📝 Выбрано игр: {'∞' if total_games == 999999 else total_games}\n\n"
            f"Введите название комнаты\n(или 'нет' для случайного названия):"
        )
    
    elif data == 'friend_find':
        if not lobbies:
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')]]
            await query.edit_message_text(
                "❌ Нет активных комнат.\nСоздайте новую!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        text = "📋 Доступные комнаты:\n\n"
        keyboard = []
        
        for lobby_id, lobby in lobbies.items():
            if lobby['player2'] is None:
                lock = "🔒" if lobby['password'] else "🔓"
                games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
                creator_nick = get_nickname(lobby['creator'])
                text += f"{lock} {lobby['name']}\n"
                text += f"   Создатель: {creator_nick}\n"
                text += f"   Игр: {lobby['current']}/{games_count}\n"
                text += f"   Счет: {lobby['score1']}:{lobby['score2']}\n"
                text += f"   ID: {lobby_id}\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{lock} {lobby['name']}", 
                    callback_data=f'join_{lobby_id}'
                )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith('join_'):
        lobby_id = data.replace('join_', '')
        
        if lobby_id not in lobbies:
            await query.edit_message_text(
                "❌ Комната не найдена",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')
                ]])
            )
            return
        
        lobby = lobbies[lobby_id]
        
        if lobby['player2'] is not None:
            await query.edit_message_text(
                "❌ В этой комнате уже есть второй игрок",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')
                ]])
            )
            return
        
        if lobby['password']:
            temp_lobby_join[user_id] = lobby_id
            await query.edit_message_text(
                f"🔒 Введите пароль для комнаты '{lobby['name']}':"
            )
        else:
            await join_lobby(user_id, lobby_id, query, context)
    
    elif data.startswith('continue_'):
        lobby_id = data.replace('continue_', '')
        
        if lobby_id not in lobbies:
            await query.edit_message_text(
                "❌ Комната не найдена",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ В меню", callback_data='menu_main')
                ]])
            )
            return
        
        lobby = lobbies[lobby_id]
        
        lobby['score1'] = 0
        lobby['score2'] = 0
        lobby['current'] = 1
        
        game_id = str(uuid.uuid4())[:8]
        game = TicTacToe(
            game_id,
            lobby['creator'],
            lobby['player2'],
            'multiplayer',
            total_games=lobby['total'],
            lobby_id=lobby_id
        )
        
        games[game_id] = game
        player_game[lobby['creator']] = game_id
        player_game[lobby['player2']] = game_id
        lobby['game_id'] = game_id
        
        creator_nick = get_nickname(lobby['creator'])
        player2_nick = get_nickname(lobby['player2'])
        
        games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
        score_display = game.get_score_display()
        header = f"{creator_nick} (❌) vs {player2_nick} (⭕)\n{score_display}\n"
        match_info = f"⚔️ Матч 1/{games_count}\n\n"
        turn_text = f"Ход игрока {creator_nick} (❌)"
        
        text = (match_info + header + game.get_board_display() + 
                f"\n🎤 Голосовой чат: просто отправляй голосовые!\n{turn_text}")
        
        msg1 = await context.bot.send_message(
            lobby['creator'],
            text,
            reply_markup=create_game_keyboard(game_id, lobby['creator'])
        )
        game.player1_message_id = msg1.message_id
        game.player1_chat_id = msg1.chat_id
        
        msg2 = await context.bot.send_message(
            lobby['player2'],
            text,
            reply_markup=create_game_keyboard(game_id, lobby['creator'])
        )
        game.player2_message_id = msg2.message_id
        game.player2_chat_id = msg2.chat_id
    
    elif data == 'menu_stats':
        stats = user_stats.get(user_id, {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
        win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        nickname = get_nickname(user_id)
        
        text = (
            f"📊 Статистика игрока {nickname}:\n\n"
            f"Всего игр: {stats['total']}\n"
            f"🏆 Побед: {stats['wins']}\n"
            f"😢 Поражений: {stats['losses']}\n"
            f"🤝 Ничьих: {stats['draws']}\n"
            f"📈 Процент побед: {win_rate:.1f}%"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'menu_help':
        text = (
            "❓ **ПОМОЩЬ**\n\n"
            "🎮 **Как играть:**\n"
            "• Нажимайте на ⬜ клетки\n"
            "• Соберите 3 в ряд для победы\n\n"
            "🎤 **ГОЛОСОВОЙ ЧАТ:**\n"
            "• Просто отправляйте голосовые во время игры\n"
            "• Бот отвечает голосом (20+ разных фраз)\n"
            "• Собеседник получает мгновенно\n"
            "• Работает в обоих режимах\n\n"
            "🤖 **Уровни бота:**\n"
            "• 🟢 Легкий - случайные ходы\n"
            "• 🟡 Средний - иногда думает\n"
            "• 🔴 Сложный - просчет ходов\n"
            "• 🤖 Нейросеть - умный ИИ\n\n"
            "📝 **Команды:**\n"
            "/start - главное меню\n"
            "/join [ID] - подключиться к комнате"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'menu_main':
        if user_id in player_game:
            game_id = player_game[user_id]
            if game_id in games:
                del games[game_id]
            del player_game[user_id]
        
        welcome_text = (
            "🎮 **ГЛАВНОЕ МЕНЮ**\n\n"
            f"Ваш ник: {get_nickname(user_id)}\n\n"
            "🎤 **ГОЛОСОВОЙ ЧАТ АКТИВЕН**\n"
            "• Просто отправляй голосовые в игре\n\n"
            "👇 **Выберите режим:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("✏️ Установить ник", callback_data='set_nickname')],
            [InlineKeyboardButton("🤖 Игра с ботом", callback_data='menu_bot')],
            [InlineKeyboardButton("👥 Игра с другом", callback_data='menu_friend')],
            [InlineKeyboardButton("📊 Статистика", callback_data='menu_stats')],
            [InlineKeyboardButton("❓ Помощь", callback_data='menu_help')]
        ]
        await query.edit_message_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('move_'):
        position = int(data.split('_')[1])
        
        if user_id not in player_game:
            await query.answer("Игра не найдена!", show_alert=True)
            return
        
        game_id = player_game[user_id]
        game = games.get(game_id)
        
        if not game:
            await query.answer("Игра не найдена!", show_alert=True)
            return
        
        result, status = game.make_move(position, user_id)
        
        if not result:
            await query.answer(status, show_alert=True)
            return
        
        player1_nick = get_nickname(game.player1_id)
        player2_nick = get_nickname(game.player2_id) if game.player2_id else "Бот"
        
        score_display = game.get_score_display()
        games_count = "∞" if game.total_games == 999999 else str(game.total_games)
        
        if game.mode == 'multiplayer':
            header = f"{player1_nick} (❌) vs {player2_nick} (⭕)\n{score_display}\n"
            if game.total_games > 1:
                header = f"⚔️ Матч {game.current_game}/{games_count}\n" + header
        else:
            diff_icons = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = diff_icons.get(game.difficulty, '🤖')
            header = f"{player1_nick} (❌) vs {diff_icon} {player2_nick}\n{score_display}\n"
            if game.total_games > 1:
                header = f"⚔️ Матч {game.current_game}/{games_count}\n" + header
        
        voice_text = "🎤 Голосовой чат: просто отправляй голосовые!"
        
        if status == "win":
            winner_id = game.winner
            loser_id = game.player2_id if winner_id == game.player1_id else game.player1_id
            
            if str(winner_id) in user_stats:
                user_stats[str(winner_id)]['wins'] += 1
                user_stats[str(winner_id)]['total'] += 1
            if str(loser_id) in user_stats:
                user_stats[str(loser_id)]['losses'] += 1
                user_stats[str(loser_id)]['total'] += 1
            save_data()
            
            winner_nick = get_nickname(winner_id)
            
            if game.mode == 'multiplayer':
                for lobby in lobbies.values():
                    if lobby['game_id'] == game_id:
                        lobby['score1'] = game.player1_score
                        lobby['score2'] = game.player2_score
                        break
            
            text = f"🎉 Победил {winner_nick}!\n\n" + header + game.get_board_display() + f"\n{voice_text}"
            game.game_over = True
            
            await update_both_players(context, game, text)
            await check_next_game(context, game_id)
            
        elif status == "draw":
            if str(game.player1_id) in user_stats:
                user_stats[str(game.player1_id)]['draws'] += 1
                user_stats[str(game.player1_id)]['total'] += 1
            if game.player2_id and str(game.player2_id) in user_stats:
                user_stats[str(game.player2_id)]['draws'] += 1
                user_stats[str(game.player2_id)]['total'] += 1
            save_data()
            
            text = f"🤝 Ничья!\n\n" + header + game.get_board_display() + f"\n{voice_text}"
            game.game_over = True
            
            await update_both_players(context, game, text)
            await check_next_game(context, game_id)
        
        elif status == "continue":
            if game.mode == 'bot':
                text = header + game.get_board_display() + f"\n{voice_text}\n🤖 Бот думает..."
                await update_both_players(context, game, text)
                
                time.sleep(1)
                
                bot = BotPlayer(game.difficulty)
                bot_move = bot.get_move(game)
                
                if bot_move is not None:
                    result, status = game.make_move(bot_move, 'bot')
                    
                    if status == "win":
                        if str(game.player1_id) in user_stats:
                            user_stats[str(game.player1_id)]['losses'] += 1
                            user_stats[str(game.player1_id)]['total'] += 1
                        save_data()
                        
                        text = f"😢 Бот победил!\n\n" + header + game.get_board_display() + f"\n{voice_text}"
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    elif status == "draw":
                        if str(game.player1_id) in user_stats:
                            user_stats[str(game.player1_id)]['draws'] += 1
                            user_stats[str(game.player1_id)]['total'] += 1
                        save_data()
                        
                        text = f"🤝 Ничья!\n\n" + header + game.get_board_display() + f"\n{voice_text}"
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    else:
                        text = header + game.get_board_display() + f"\n{voice_text}\nВаш ход!"
                        await update_both_players(context, game, text, create_game_keyboard(game_id, game.player1_id))
            
            else:
                if game.current_turn == game.player1_id:
                    turn_text = f"Ход игрока {player1_nick} (❌)"
                else:
                    turn_text = f"Ход игрока {player2_nick} (⭕)"
                
                text = header + game.get_board_display() + f"\n{voice_text}\n{turn_text}"
                await update_both_players(context, game, text, create_game_keyboard(game_id, game.current_turn))

async def check_next_game(context, game_id):
    game = games.get(game_id)
    if not game:
        return
    
    if game.mode == 'bot' and game.total_games > 1:
        if game.current_game < game.total_games:
            game.current_game += 1
            
            game.board = ['⬜'] * 9
            game.game_over = False
            game.winner = None
            game.current_turn = game.player1_id
            
            player_nick = get_nickname(game.player1_id)
            
            diff_icons = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = diff_icons.get(game.difficulty, '🤖')
            
            score_display = game.get_score_display()
            games_count = "∞" if game.total_games == 999999 else str(game.total_games)
            header = f"{player_nick} (❌) vs {diff_icon} Бот\n{score_display}\n"
            match_info = f"⚔️ Матч {game.current_game}/{games_count}\n\n"
            
            text = (match_info + header + game.get_board_display() + 
                    f"\n🎤 Голосовой чат: просто отправляй голосовые!\nВаш ход!")
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game.player1_chat_id,
                    message_id=game.player1_message_id,
                    text=text,
                    reply_markup=create_game_keyboard(game_id, game.player1_id)
                )
            except Exception as e:
                logger.error(f"Ошибка обновления следующей игры: {e}")
        
        else:
            player_nick = get_nickname(game.player1_id)
            diff_icons = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = diff_icons.get(game.difficulty, '🤖')
            
            final_text = (
                f"🏁 Серия игр завершена!\n\n"
                f"Финальный счет:\n"
                f"{player_nick}: {game.player1_score}\n"
                f"Бот ({diff_icon}): {game.player2_score}"
            )
            
            keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data='menu_main')]]
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game.player1_chat_id,
                    message_id=game.player1_message_id,
                    text=final_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Ошибка финала серии: {e}")
            
            if game_id in games:
                del games[game_id]
            if str(game.player1_id) in player_game:
                del player_game[str(game.player1_id)]
    
    elif game.mode == 'multiplayer':
        for lobby_id, lobby in lobbies.items():
            if lobby['game_id'] == game_id:
                games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
                
                if lobby['current'] < lobby['total']:
                    lobby['current'] += 1
                    
                    game.board = ['⬜'] * 9
                    game.game_over = False
                    game.winner = None
                    game.current_game = lobby['current']
                    
                    if lobby['current'] % 2 == 0:
                        game.current_turn = lobby['player2']
                    else:
                        game.current_turn = lobby['creator']
                    
                    creator_nick = get_nickname(lobby['creator'])
                    player2_nick = get_nickname(lobby['player2'])
                    
                    score_display = game.get_score_display()
                    header = f"{creator_nick} (❌) vs {player2_nick} (⭕)\n{score_display}\n"
                    match_info = f"⚔️ Матч {lobby['current']}/{games_count}\n\n"
                    
                    if game.current_turn == lobby['creator']:
                        turn_text = f"Ход игрока {creator_nick} (❌)"
                    else:
                        turn_text = f"Ход игрока {player2_nick} (⭕)"
                    
                    text = (match_info + header + game.get_board_display() + 
                            f"\n🎤 Голосовой чат: просто отправляй голосовые!\n{turn_text}")
                    
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game.player1_chat_id,
                            message_id=game.player1_message_id,
                            text=text,
                            reply_markup=create_game_keyboard(game_id, game.current_turn)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обновления у игрока 1: {e}")
                    
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game.player2_chat_id,
                            message_id=game.player2_message_id,
                            text=text,
                            reply_markup=create_game_keyboard(game_id, game.current_turn)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обновления у игрока 2: {e}")
                
                else:
                    creator_nick = get_nickname(lobby['creator'])
                    player2_nick = get_nickname(lobby['player2'])
                    
                    if lobby['score1'] > lobby['score2']:
                        winner_text = f"🏆 Победитель серии: {creator_nick}"
                    elif lobby['score2'] > lobby['score1']:
                        winner_text = f"🏆 Победитель серии: {player2_nick}"
                    else:
                        winner_text = f"🤝 Ничья в серии!"
                    
                    final_text = (
                        f"🏁 Серия игр завершена!\n\n"
                        f"Финальный счет:\n"
                        f"{creator_nick}: {lobby['score1']}\n"
                        f"{player2_nick}: {lobby['score2']}\n\n"
                        f"{winner_text}\n\n"
                        f"Хотите сыграть ещё?"
                    )
                    
                    keyboard = [
                        [InlineKeyboardButton("✅ Сыграть ещё (счет с 0)", callback_data=f'continue_{lobby_id}')],
                        [InlineKeyboardButton("◀️ В меню", callback_data='menu_main')]
                    ]
                    
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game.player1_chat_id,
                            message_id=game.player1_message_id,
                            text=final_text,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка финала у игрока 1: {e}")
                    
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game.player2_chat_id,
                            message_id=game.player2_message_id,
                            text=final_text,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка финала у игрока 2: {e}")
                
                break

async def join_lobby(user_id, lobby_id, query=None, context=None, update=None):
    lobby = lobbies[lobby_id]
    
    game_id = str(uuid.uuid4())[:8]
    game = TicTacToe(
        game_id,
        lobby['creator'],
        user_id,
        'multiplayer',
        total_games=lobby['total'],
        lobby_id=lobby_id
    )
    
    games[game_id] = game
    player_game[lobby['creator']] = game_id
    player_game[user_id] = game_id
    
    lobby['player2'] = user_id
    lobby['game_id'] = game_id
    lobby['score1'] = 0
    lobby['score2'] = 0
    
    creator_nick = get_nickname(lobby['creator'])
    joiner_nick = get_nickname(user_id)
    
    games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
    score_display = game.get_score_display()
    header = f"{creator_nick} (❌) vs {joiner_nick} (⭕)\n{score_display}\n"
    match_info = f"⚔️ Матч 1/{games_count}\n\n"
    turn_text = f"Ход игрока {creator_nick} (❌)"
    
    text = (match_info + header + game.get_board_display() + 
            f"\n🎤 Голосовой чат: просто отправляй голосовые!\n{turn_text}")
    
    msg1 = await context.bot.send_message(
        lobby['creator'],
        text,
        reply_markup=create_game_keyboard(game_id, lobby['creator'])
    )
    game.player1_message_id = msg1.message_id
    game.player1_chat_id = msg1.chat_id
    
    msg2 = await context.bot.send_message(
        user_id,
        text,
        reply_markup=create_game_keyboard(game_id, lobby['creator'])
    )
    game.player2_message_id = msg2.message_id
    game.player2_chat_id = msg2.chat_id
    
    notification = f"✅ Подключено к комнате '{lobby['name']}'\nИгра началась!"
    
    if query:
        await query.edit_message_text(notification)
    else:
        await context.bot.send_message(user_id, notification)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    # ОБРАБОТКА ГОЛОСОВЫХ СООБЩЕНИЙ (ПРОСТО ОТПРАВЛЯЕШЬ)
    if update.message.voice:
        if user_id in player_game:
            game_id = player_game[user_id]
            game = games.get(game_id)
            
            if game:
                voice = update.message.voice
                
                # Если игра с ботом - бот отвечает голосом
                if game.mode == 'bot':
                    # Получаем случайный ответ для уровня сложности
                    response_text = voice_bot.get_random_response(game.difficulty)
                    
                    # Отправляем уведомление
                    await update.message.reply_text("🎤 Бот слушает и отвечает...")
                    
                    # Конвертируем в голос
                    audio_data = await voice_bot.text_to_speech(response_text, game.difficulty)
                    
                    if audio_data:
                        await context.bot.send_voice(
                            chat_id=user_id,
                            voice=audio_data,
                            caption=f"🤖 Бот ({game.difficulty}) отвечает:"
                        )
                    else:
                        await update.message.reply_text(f"🤖 {response_text}")
                
                # Если мультиплеер - пересылаем сопернику
                else:
                    opponent_id = str(game.player2_id) if user_id == str(game.player1_id) else str(game.player1_id)
                    
                    if opponent_id:
                        await context.bot.send_voice(
                            chat_id=opponent_id,
                            voice=voice.file_id,
                            caption=f"🎤 Голосовое сообщение от {get_nickname(user_id)}"
                        )
                        await update.message.reply_text("✅ Голосовое отправлено сопернику!")
                
                return
            else:
                await update.message.reply_text("❌ Сначала начните игру!")
                return
        else:
            await update.message.reply_text("❌ Сначала начните игру через /start")
            return
    
    # ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ
    text = update.message.text
    
    if user_id in temp_set_nickname:
        nickname = text[:20]
        user_nicknames[user_id] = nickname
        save_data()
        del temp_set_nickname[user_id]
        
        await update.message.reply_text(
            f"✅ Ник установлен: {nickname}\n\n"
            f"Возвращайтесь в меню: /start"
        )
    
    elif user_id in temp_lobby_name:
        total_games = temp_lobby_name[user_id]
        
        if text.lower() == 'нет':
            room_name = f"Комната_{random.randint(1000,9999)}"
        else:
            room_name = text[:30]
        
        temp_lobby_password[user_id] = {
            'name': room_name,
            'total': total_games
        }
        del temp_lobby_name[user_id]
        
        await update.message.reply_text(
            f"📝 Название: {room_name}\n"
            f"🎮 Игр: {'∞' if total_games == 999999 else total_games}\n\n"
            f"Введите пароль (или 'нет' для открытой комнаты):"
        )
    
    elif user_id in temp_lobby_password:
        data = temp_lobby_password[user_id]
        
        if text.lower() == 'нет':
            password = None
            pass_text = "без пароля"
        else:
            password = text
            pass_text = "с паролем"
        
        lobby_id = str(uuid.uuid4())[:8]
        
        lobbies[lobby_id] = {
            'name': data['name'],
            'creator': user_id,
            'creator_name': user_nicknames.get(user_id, f"Игрок_{user_id[:4]}"),
            'password': password,
            'total': data['total'],
            'current': 1,
            'player2': None,
            'game_id': None,
            'score1': 0,
            'score2': 0,
            'created': time.time()
        }
        
        del temp_lobby_password[user_id]
        
        games_count = "∞" if data['total'] == 999999 else str(data['total'])
        
        await update.message.reply_text(
            f"✅ Комната создана!\n\n"
            f"🏷 Название: {data['name']}\n"
            f"🆔 ID: {lobby_id}\n"
            f"🎮 Серия: {games_count} игр\n"
            f"🔒 Пароль: {pass_text}\n\n"
            f"Отправьте ID другу: /join {lobby_id}\n"
            f"Ожидайте подключения..."
        )
    
    elif user_id in temp_lobby_join:
        lobby_id = temp_lobby_join[user_id]
        
        if lobby_id not in lobbies:
            await update.message.reply_text("❌ Комната не найдена")
            del temp_lobby_join[user_id]
            return
        
        lobby = lobbies[lobby_id]
        
        if text == lobby['password']:
            del temp_lobby_join[user_id]
            await join_lobby(user_id, lobby_id, None, context, update)
        else:
            await update.message.reply_text("❌ Неправильный пароль. Попробуйте снова:")
    
    elif text.startswith('/join'):
        parts = text.split()
        if len(parts) >= 2:
            lobby_id = parts[1]
            
            if lobby_id not in lobbies:
                await update.message.reply_text("❌ Комната не найдена")
                return
            
            lobby = lobbies[lobby_id]
            
            if lobby['player2'] is not None:
                await update.message.reply_text("❌ В комнате уже есть второй игрок")
                return
            
            if lobby['password']:
                temp_lobby_join[user_id] = lobby_id
                await update.message.reply_text(
                    f"🔒 Введите пароль для комнаты '{lobby['name']}':"
                )
            else:
                await join_lobby(user_id, lobby_id, None, context, update)

def create_game_keyboard(game_id, current_player_id):
    """Клавиатура - ТОЛЬКО КЛЕТКИ И МЕНЮ, БЕЗ ЧАТА"""
    game = games.get(game_id)
    if not game:
        return None
    
    keyboard = []
    row = []
    
    for i in range(9):
        if game.current_turn == current_player_id and game.board[i] == '⬜' and not game.game_over:
            callback = f'move_{i}'
        else:
            callback = 'no_move'
        
        row.append(InlineKeyboardButton(game.board[i], callback_data=callback))
        
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    
    # ТОЛЬКО КНОПКА МЕНЮ - НИКАКИХ КНОПОК ЧАТА
    keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data='menu_main')])
    return InlineKeyboardMarkup(keyboard)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    print("=" * 50)
    print("🎮 КРЕСТИКИ-НОЛИКИ - ФИНАЛЬНАЯ ВЕРСИЯ")
    print("=" * 50)
    print("✅ НОРМАЛЬНЫЕ КРЕСТИКИ И НОЛИКИ")
    print("✅ ГОЛОСОВОЙ ЧАТ: ПРОСТО ОТПРАВЛЯЙ ГОЛОСОВЫЕ")
    print("✅ БОТ ОТВЕЧАЕТ ГОЛОСОМ (20+ ВАРИАНТОВ)")
    print("✅ ТЕКСТОВЫЙ ЧАТ УДАЛЁН")
    print("=" * 50)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_message))
    app.add_error_handler(error_handler)
    
    print("🚀 Бот запущен! Отправьте /start в Telegram")
    app.run_polling()

if __name__ == '__main__':
    main()