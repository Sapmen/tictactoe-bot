import logging
import random
import time
import uuid
import json
import os
import io
import aiohttp
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Voice
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
CHAT_HISTORY_FILE = 'chat_history.json'

# Загрузка сохраненных данных
def load_data():
    global user_nicknames, user_stats, chat_history
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
    
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = {}
    except:
        chat_history = {}

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
    
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения чата: {e}")

# Загружаем данные при старте
load_data()

# Хранилища данных
games = {}
player_game = {}
lobbies = {}
waiting_for_opponent = []
chat_history = {}

# Временные хранилища
temp_lobby_name = {}
temp_lobby_password = {}
temp_lobby_join = {}
temp_set_nickname = {}
temp_bot_series = {}
temp_bot_chat = {}
temp_lobby_chat = {}
temp_lobby_continue = {}

class TicTacToe:
    def __init__(self, game_id, player1_id, player2_id=None, mode='bot', difficulty='easy', total_games=1, chat_enabled=False, lobby_id=None):
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
        self.chat_enabled = chat_enabled
        self.chat_history = []
        self.lobby_id = lobby_id
        self.voice_enabled = True  # Голосовой чат всегда включен для всех
        
    def make_move(self, position, player_id):
        if self.game_over:
            return False, "Игра уже окончена"
        
        if player_id != self.current_turn:
            return False, "Сейчас не ваш ход"
        
        if self.board[position] != '⬜':
            return False, "Эта клетка уже занята"
        
        # Определяем символ
        if player_id == self.player1_id:
            symbol = '❌'
        else:
            symbol = '⭕'
        
        self.board[position] = symbol
        self.last_move_time = time.time()
        
        # Проверяем победу
        if self.check_win(symbol):
            self.winner = player_id
            self.game_over = True
            # Обновляем счет
            if player_id == self.player1_id:
                self.player1_score += 1
            else:
                self.player2_score += 1
            return True, "win"
        
        # Проверяем ничью
        if self.check_draw():
            self.game_over = True
            return True, "draw"
        
        # Меняем ход
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
            return f"📊 Счет: {self.player1_score} : {self.player2_score}"
        return ""
    
    def add_chat_message(self, user_id, message):
        """Добавляет сообщение в историю чата"""
        timestamp = datetime.now().strftime("%H:%M")
        nickname = get_nickname(user_id)
        self.chat_history.append({
            'user_id': user_id,
            'nickname': nickname,
            'message': message,
            'time': timestamp
        })
        # Сохраняем только последние 20 сообщений
        if len(self.chat_history) > 20:
            self.chat_history = self.chat_history[-20:]
    
    def get_chat_display(self):
        """Возвращает отформатированную историю чата"""
        if not self.chat_history:
            return "💬 Чат пуст. Напишите что-нибудь!"
        
        chat_text = "💬 История чата:\n\n"
        for msg in self.chat_history[-10:]:  # Показываем последние 10 сообщений
            chat_text += f"[{msg['time']}] {msg['nickname']}: {msg['message']}\n"
        return chat_text

# Класс для TTS (Text-to-Speech)
class VoiceBot:
    def __init__(self):
        self.voice_map = {
            'easy': 'ru-RU-OstapenkoNeural',      # Мягкий женский голос
            'medium': 'ru-RU-DariyaNeural',        # Нейтральный женский
            'hard': 'ru-RU-MikhailNeural',         # Мужской голос
            'impossible': 'ru-RU-CatherineNeural'  # Загадочный женский
        }
    
    async def text_to_speech(self, text, difficulty='medium'):
        """Конвертирует текст в голосовое сообщение"""
        voice_name = self.voice_map.get(difficulty, 'ru-RU-DariyaNeural')
        
        # Используем бесплатный API для TTS
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

# Инициализируем голосового бота
voice_bot = VoiceBot()

class NeuralNetworkBot:
    def __init__(self, difficulty='impossible'):
        self.difficulty = difficulty
        # Ответы для разных уровней сложности
        self.responses = {
            'easy': [
                "Я только учусь!",
                "Интересный ход!",
                "Ого, так неожиданно!",
                "Я пока не очень умный...",
                "Ты явно опытнее меня!"
            ],
            'medium': [
                "Неплохой ход!",
                "Я начинаю понимать игру...",
                "Интересная стратегия!",
                "Посмотрим, что будет дальше!",
                "Ты хорошо играешь!"
            ],
            'hard': [
                "Отличный ход!",
                "Я ожидал этого...",
                "Хорошая стратегия!",
                "Так держать!",
                "Это было предсказуемо."
            ],
            'impossible': [
                "Я просчитал этот ход!",
                "Ты играешь на удивление хорошо!",
                "Интересно, что будет дальше...",
                "Я анализирую твою стратегию!",
                "Нейросеть довольна твоей игрой!"
            ]
        }
        
    def get_move(self, game):
        available = [i for i, cell in enumerate(game.board) if cell == '⬜']
        
        if not available:
            return None
        
        # 1. Победный ход
        for pos in available:
            game.board[pos] = '⭕'
            if game.check_win('⭕'):
                game.board[pos] = '⬜'
                return pos
            game.board[pos] = '⬜'
        
        # 2. Блокировка
        for pos in available:
            game.board[pos] = '❌'
            if game.check_win('❌'):
                game.board[pos] = '⬜'
                return pos
            game.board[pos] = '⬜'
        
        # 3. Центр
        if 4 in available:
            return 4
        
        # 4. Углы
        corners = [0, 2, 6, 8]
        available_corners = [c for c in corners if c in available]
        if available_corners:
            return random.choice(available_corners)
        
        return random.choice(available)
    
    def get_chat_response(self, game, message):
        """Генерирует ответ нейросети на сообщение игрока"""
        # Анализируем сообщение
        message_lower = message.lower()
        
        # Ответы на приветствия
        if any(word in message_lower for word in ['привет', 'здравствуй', 'хай', 'hello']):
            return f"Привет! Как твоя игра? (Уровень: {self.difficulty})"
        
        # Ответы на вопросы о игре
        if any(word in message_lower for word in ['как дела', 'как ты']):
            responses = {
                'easy': "У меня всё отлично! Я только учусь играть!",
                'medium': "Хорошо! Начинаю понимать стратегию!",
                'hard': "Прекрасно! Я анализирую каждый ход!",
                'impossible': "Отлично! Нейросеть в полной боевой готовности!"
            }
            return responses.get(self.difficulty, "Всё хорошо!")
        
        # Ответы на комплименты
        if any(word in message_lower for word in ['молодец', 'умница', 'хорошо', 'круто']):
            responses = {
                'easy': "Спасибо! Ты тоже молодец!",
                'medium': "Благодарю! Твоя игра впечатляет!",
                'hard': "Спасибо! Я стараюсь!",
                'impossible': "Нейросеть ценит твои слова!"
            }
            return responses.get(self.difficulty, "Спасибо!")
        
        # Ответы на вопросы о ходе
        if any(word in message_lower for word in ['куда ходить', 'посоветуй', 'подскажи']):
            return "Смотри на центр и углы, это ключевые позиции!"
        
        # Если ничего не подошло, случайный ответ для текущей сложности
        return random.choice(self.responses.get(self.difficulty, self.responses['medium']))

class BotPlayer:
    def __init__(self, difficulty='easy', chat_enabled=False):
        self.difficulty = difficulty
        self.chat_enabled = chat_enabled
        self.neural = NeuralNetworkBot(difficulty) if chat_enabled else None
        
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
            if self.neural:
                return self.neural.get_move(game)
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
    """Возвращает ник пользователя"""
    return user_nicknames.get(str(user_id), f"Игрок_{str(user_id)[:4]}")

async def update_both_players(context, game, text, keyboard=None):
    """Обновляет сообщения у обоих игроков"""
    # Обновляем у первого игрока
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
    
    # Обновляем у второго игрока (если есть)
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
    
    welcome_text = "🎮 Добро пожаловать в Крестики-Нолики!\n\n"
    
    if user_id in user_nicknames:
        welcome_text += f"Ваш ник: {user_nicknames[user_id]}\n"
    else:
        welcome_text += "Установите ник, чтобы друзья вас узнали!\n"
    
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
    
    # Установка ника
    if data == 'set_nickname':
        temp_set_nickname[user_id] = True
        await query.edit_message_text(
            "✏️ Введите ваш ник (до 20 символов):"
        )
    
    # Меню игры с ботом
    elif data == 'menu_bot':
        keyboard = [
            [InlineKeyboardButton("🟢 Легкий", callback_data='bot_difficulty_easy')],
            [InlineKeyboardButton("🟡 Средний", callback_data='bot_difficulty_medium')],
            [InlineKeyboardButton("🔴 Сложный", callback_data='bot_difficulty_hard')],
            [InlineKeyboardButton("🤖 Нейросеть", callback_data='bot_difficulty_impossible')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]
        ]
        await query.edit_message_text(
            "🤖 Выберите уровень сложности:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_difficulty_'):
        difficulty = data.replace('bot_difficulty_', '')
        temp_bot_series[user_id] = {'difficulty': difficulty}
        
        # Добавляем выбор чата
        keyboard = [
            [InlineKeyboardButton("💬 С чатом (нейросеть)", callback_data=f'bot_chat_yes_{difficulty}')],
            [InlineKeyboardButton("🎮 Без чата", callback_data=f'bot_chat_no_{difficulty}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            f"🤖 Уровень: {difficulty}\nВыберите режим общения с ботом:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_chat_'):
        parts = data.split('_')
        chat_enabled = (parts[2] == 'yes')
        difficulty = parts[3]
        
        # Сохраняем выбор чата
        temp_bot_chat[user_id] = {'enabled': chat_enabled}
        
        keyboard = [
            [InlineKeyboardButton("1 игра", callback_data=f'bot_series_1_{difficulty}')],
            [InlineKeyboardButton("3 игры", callback_data=f'bot_series_3_{difficulty}')],
            [InlineKeyboardButton("5 игр", callback_data=f'bot_series_5_{difficulty}')],
            [InlineKeyboardButton("10 игр", callback_data=f'bot_series_10_{difficulty}')],
            [InlineKeyboardButton("∞ Бесконечно", callback_data=f'bot_series_inf_{difficulty}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            "🎮 Сколько игр сыграть с ботом?\n"
            "Выберите количество:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_series_'):
        parts = data.split('_')
        if parts[2] == 'inf':
            total_games = 999999
            difficulty = parts[3]
        else:
            total_games = int(parts[2])
            difficulty = parts[3]
        
        chat_config = temp_bot_chat.get(user_id, {'enabled': False})
        chat_enabled = chat_config['enabled']
        
        # Создаем игру
        game_id = str(uuid.uuid4())[:8]
        game = TicTacToe(game_id, user_id, mode='bot', difficulty=difficulty, total_games=total_games, chat_enabled=chat_enabled)
        
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
            header = f"👤 {player_nick} (❌) vs 🤖 Бот ({difficulty_names[difficulty]})\n{game.get_score_display()}\n"
            match_info = f"⚔️ Матч 1/{games_count}\n\n"
        else:
            header = f"👤 {player_nick} (❌) vs 🤖 Бот ({difficulty_names[difficulty]})\n"
            match_info = ""
        
        chat_status = "💬 Чат включен" if chat_enabled else "🎮 Чат выключен"
        voice_status = "🎤 Голосовой чат активен (отправляйте голосовые!)"
        text = match_info + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\nВаш ход!"
        
        msg = await query.edit_message_text(
            text,
            reply_markup=create_game_keyboard(game_id, user_id, game)
        )
        
        game.player1_message_id = msg.message_id
        game.player1_chat_id = msg.chat_id
    
    # Меню игры с другом
    elif data == 'menu_friend':
        keyboard = [
            [InlineKeyboardButton("🎮 Создать комнату", callback_data='friend_create')],
            [InlineKeyboardButton("🔍 Найти комнату", callback_data='friend_find')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]
        ]
        await query.edit_message_text(
            "👥 Игра с другом\n\n"
            "Создайте комнату и отправьте ID другу:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == 'friend_create':
        keyboard = [
            [InlineKeyboardButton("1 игра", callback_data='create_1')],
            [InlineKeyboardButton("3 игры", callback_data='create_3')],
            [InlineKeyboardButton("5 игр", callback_data='create_5')],
            [InlineKeyboardButton("10 игр", callback_data='create_10')],
            [InlineKeyboardButton("∞ Бесконечно", callback_data='create_infinite')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')]
        ]
        await query.edit_message_text(
            "🎮 Сколько игр сыграть?\n"
            "Выберите количество:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('create_'):
        if data == 'create_infinite':
            total_games = 999999
        else:
            total_games = int(data.split('_')[1])
        
        temp_lobby_name[user_id] = total_games
        
        # Добавляем выбор чата
        keyboard = [
            [InlineKeyboardButton("💬 С чатом", callback_data=f'lobby_chat_yes_{total_games}')],
            [InlineKeyboardButton("🎮 Без чата", callback_data=f'lobby_chat_no_{total_games}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')]
        ]
        await query.edit_message_text(
            f"📝 Выбрано игр: {'∞' if total_games == 999999 else total_games}\n\n"
            f"Включить чат между игроками?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('lobby_chat_'):
        parts = data.split('_')
        chat_enabled = (parts[2] == 'yes')
        total_games = int(parts[3])
        
        temp_lobby_chat[user_id] = {'enabled': chat_enabled}
        temp_lobby_name[user_id] = total_games
        
        chat_type = "💬 Обычный чат" if chat_enabled else "🎮 Без чата"
        await query.edit_message_text(
            f"📝 Выбрано игр: {'∞' if total_games == 999999 else total_games}\n\n"
            f"{chat_type}\n\n"
            f"Введите название комнаты\n"
            f"(или 'нет' для случайного названия):"
        )
    
    elif data == 'friend_find':
        if not lobbies:
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')]]
            await query.edit_message_text(
                "❌ Нет активных комнат.\n"
                "Создайте новую!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        text = "📋 Доступные комнаты:\n\n"
        keyboard = []
        
        for lobby_id, lobby in lobbies.items():
            if lobby['player2'] is None:
                lock = "🔒" if lobby['password'] else "🔓"
                chat_status = "💬" if lobby['chat_enabled'] else "🎮"
                games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
                creator_nick = get_nickname(lobby['creator'])
                text += f"{lock}{chat_status} {lobby['name']}\n"
                text += f"   Создатель: {creator_nick}\n"
                text += f"   Игр: {lobby['current']}/{games_count}\n"
                text += f"   Счет: {lobby['score1']}:{lobby['score2']}\n"
                text += f"   ID: {lobby_id}\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{lock}{chat_status} {lobby['name']}", 
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
    
    # Продолжить серию (бесконечные игры)
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
        
        # Сбрасываем счет, но сохраняем комнату
        lobby['score1'] = 0
        lobby['score2'] = 0
        lobby['current'] = 1
        
        # Создаем новую игру
        game_id = str(uuid.uuid4())[:8]
        game = TicTacToe(
            game_id,
            lobby['creator'],
            lobby['player2'],
            'multiplayer',
            total_games=lobby['total'],
            chat_enabled=lobby['chat_enabled'],
            lobby_id=lobby_id
        )
        
        games[game_id] = game
        player_game[lobby['creator']] = game_id
        player_game[lobby['player2']] = game_id
        lobby['game_id'] = game_id
        
        # Получаем ники
        creator_nick = get_nickname(lobby['creator'])
        player2_nick = get_nickname(lobby['player2'])
        
        games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
        score_display = game.get_score_display()
        header = f"👥 {creator_nick} (❌) vs {player2_nick} (⭕)\n{score_display}\n"
        match_info = f"⚔️ Матч 1/{games_count}\n\n"
        turn_text = f"Ход игрока {creator_nick} (❌)"
        chat_status = "💬 Чат есть" if game.chat_enabled else ""
        voice_status = "🎤 Голосовой чат активен (отправляйте голосовые!)"
        
        text = match_info + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\n{turn_text}"
        
        # Отправляем новые сообщения
        msg1 = await context.bot.send_message(
            lobby['creator'],
            text,
            reply_markup=create_game_keyboard(game_id, lobby['creator'], game)
        )
        game.player1_message_id = msg1.message_id
        game.player1_chat_id = msg1.chat_id
        
        msg2 = await context.bot.send_message(
            lobby['player2'],
            text,
            reply_markup=create_game_keyboard(game_id, lobby['creator'], game)
        )
        game.player2_message_id = msg2.message_id
        game.player2_chat_id = msg2.chat_id
        
        # Удаляем старые сообщения
        if game.player1_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=game.player1_chat_id,
                    message_id=game.player1_message_id
                )
            except:
                pass
        
        if game.player2_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=game.player2_chat_id,
                    message_id=game.player2_message_id
                )
            except:
                pass
    
    # Статистика
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
    
    # Помощь
    elif data == 'menu_help':
        text = (
            "❓ Помощь:\n\n"
            "🎮 Как играть:\n"
            "• Нажимайте на ⬜ клетки\n"
            "• Соберите 3 в ряд для победы\n\n"
            "✏️ Никнеймы:\n"
            "• Установите свой ник в меню\n"
            "• Ники сохраняются и отображаются в игре\n\n"
            "🤖 Игра с ботом:\n"
            "• Выберите уровень сложности (Easy, Medium, Hard, Нейросеть)\n"
            "• Можно играть бесконечные серии (∞)\n\n"
            "👥 Мультиплеер:\n"
            "• Создайте комнату с чатом или без\n"
            "• Можно выбрать количество игр или ∞ бесконечно\n"
            "• После завершения серии можно начать новую с 0\n\n"
            "🎤 Голосовой чат:\n"
            "• Просто отправляйте голосовые сообщения во время игры\n"
            "• Собеседник получит их сразу\n"
            "• Бот тоже отвечает голосом!\n"
            "• Работает как обычный чат в Telegram\n\n"
            "📝 Команды:\n"
            "/start - главное меню\n"
            "/join [ID] - подключиться"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Главное меню
    elif data == 'menu_main':
        if user_id in player_game:
            game_id = player_game[user_id]
            if game_id in games:
                del games[game_id]
            del player_game[user_id]
        
        welcome_text = "🎮 Главное меню\n\n"
        if user_id in user_nicknames:
            welcome_text += f"Ваш ник: {user_nicknames[user_id]}\n"
        welcome_text += "\nВыберите режим:"
        
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
    
    # Обработка ходов
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
        
        # Делаем ход
        result, status = game.make_move(position, user_id)
        
        if not result:
            await query.answer(status, show_alert=True)
            return
        
        # Получаем ники
        player1_nick = get_nickname(game.player1_id)
        player2_nick = get_nickname(game.player2_id) if game.player2_id else "Бот"
        
        # Формируем заголовок со счетом
        score_display = game.get_score_display()
        games_count = "∞" if game.total_games == 999999 else str(game.total_games)
        
        if game.mode == 'multiplayer' or (game.mode == 'bot' and game.total_games > 1):
            if game.mode == 'multiplayer':
                header = f"👥 {player1_nick} (❌) vs {player2_nick} (⭕)\n{score_display}\n"
            else:
                difficulty_names = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
                diff_icon = difficulty_names.get(game.difficulty, '🤖')
                header = f"👤 {player1_nick} (❌) vs {diff_icon} {player2_nick} ({game.difficulty})\n{score_display}\n"
            
            if game.total_games > 1:
                header = f"⚔️ Матч {game.current_game}/{games_count}\n" + header
        else:
            difficulty_names = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = difficulty_names.get(game.difficulty, '🤖')
            header = f"👤 {player1_nick} (❌) vs {diff_icon} {player2_nick} ({game.difficulty})\n"
        
        chat_status = "💬 Чат есть" if game.chat_enabled else ""
        voice_status = "🎤 Голосовой чат активен (отправляйте голосовые!)"
        
        # Проверяем результат
        if status == "win":
            # Определяем победителя
            winner_id = game.winner
            loser_id = game.player2_id if winner_id == game.player1_id else game.player1_id
            
            # Обновляем статистику
            if str(winner_id) in user_stats:
                user_stats[str(winner_id)]['wins'] += 1
                user_stats[str(winner_id)]['total'] += 1
            if str(loser_id) in user_stats:
                user_stats[str(loser_id)]['losses'] += 1
                user_stats[str(loser_id)]['total'] += 1
            save_data()
            
            winner_nick = get_nickname(winner_id)
            
            # Если мультиплеер, обновляем счет в лобби
            if game.mode == 'multiplayer':
                for lobby in lobbies.values():
                    if lobby['game_id'] == game_id:
                        lobby['score1'] = game.player1_score
                        lobby['score2'] = game.player2_score
                        break
            
            # Формируем текст с победителем
            if game.mode == 'bot' and game.total_games > 1 and game.current_game < game.total_games:
                text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
            else:
                text = f"🎉 Победил {winner_nick}!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
            
            # Завершаем игру
            game.game_over = True
            
            # Обновляем сообщения у обоих игроков
            await update_both_players(context, game, text)
            
            # Проверяем, есть ли следующая игра в серии
            await check_next_game(context, game_id)
            
        elif status == "draw":
            # Обновляем статистику
            if str(game.player1_id) in user_stats:
                user_stats[str(game.player1_id)]['draws'] += 1
                user_stats[str(game.player1_id)]['total'] += 1
            if game.player2_id and str(game.player2_id) in user_stats:
                user_stats[str(game.player2_id)]['draws'] += 1
                user_stats[str(game.player2_id)]['total'] += 1
            save_data()
            
            # Формируем текст с ничьей
            if game.mode == 'bot' and game.total_games > 1 and game.current_game < game.total_games:
                text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
            else:
                text = f"🤝 Ничья!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
            
            # Завершаем игру
            game.game_over = True
            
            # Обновляем сообщения у обоих игроков
            await update_both_players(context, game, text)
            
            # Проверяем, есть ли следующая игра в серии
            await check_next_game(context, game_id)
        
        elif status == "continue":
            if game.mode == 'bot':
                # Показываем ход игрока
                text = header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\n🤖 Бот думает..."
                await update_both_players(context, game, text)
                
                time.sleep(1)
                
                # Ход бота
                bot = BotPlayer(game.difficulty, game.chat_enabled)
                bot_move = bot.get_move(game)
                
                if bot_move is not None:
                    result, status = game.make_move(bot_move, 'bot')
                    
                    if status == "win":
                        # Определяем победителя (бот)
                        winner_id = 'bot'
                        loser_id = game.player1_id
                        
                        if str(loser_id) in user_stats:
                            user_stats[str(loser_id)]['losses'] += 1
                            user_stats[str(loser_id)]['total'] += 1
                        save_data()
                        
                        if game.total_games > 1 and game.current_game < game.total_games:
                            text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
                        else:
                            text = f"😢 Бот победил!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
                        
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    elif status == "draw":
                        if str(game.player1_id) in user_stats:
                            user_stats[str(game.player1_id)]['draws'] += 1
                            user_stats[str(game.player1_id)]['total'] += 1
                        save_data()
                        
                        if game.total_games > 1 and game.current_game < game.total_games:
                            text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
                        else:
                            text = f"🤝 Ничья!\n\n" + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}"
                        
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    else:
                        if game.current_turn == game.player1_id:
                            turn_text = "Ваш ход!"
                        else:
                            turn_text = "Ход бота..."
                        
                        text = header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\n{turn_text}"
                        await update_both_players(context, game, text, create_game_keyboard(game_id, game.player1_id, game))
            
            else:  # multiplayer
                # Определяем, чей сейчас ход
                if game.current_turn == game.player1_id:
                    turn_text = f"Ход игрока {player1_nick} (❌)"
                else:
                    turn_text = f"Ход игрока {player2_nick} (⭕)"
                
                text = header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\n{turn_text}"
                
                # Обновляем у обоих игроков
                await update_both_players(context, game, text, create_game_keyboard(game_id, game.current_turn, game))

async def check_next_game(context, game_id):
    """Проверяет, есть ли следующая игра в серии"""
    game = games.get(game_id)
    if not game:
        return
    
    # Для игры с ботом
    if game.mode == 'bot' and game.total_games > 1:
        if game.current_game < game.total_games:
            game.current_game += 1
            
            # Создаем новую доску
            game.board = ['⬜'] * 9
            game.game_over = False
            game.winner = None
            game.current_turn = game.player1_id
            
            # Получаем ник игрока
            player_nick = get_nickname(game.player1_id)
            
            difficulty_names = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = difficulty_names.get(game.difficulty, '🤖')
            
            # Формируем заголовок со счетом
            score_display = game.get_score_display()
            games_count = "∞" if game.total_games == 999999 else str(game.total_games)
            header = f"👤 {player_nick} (❌) vs {diff_icon} Бот ({game.difficulty})\n{score_display}\n"
            match_info = f"⚔️ Матч {game.current_game}/{games_count}\n\n"
            
            chat_status = "💬 Чат есть" if game.chat_enabled else ""
            voice_status = "🎤 Голосовой чат активен (отправляйте голосовые!)"
            text = match_info + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\nВаш ход!"
            
            # Обновляем сообщение
            try:
                await context.bot.edit_message_text(
                    chat_id=game.player1_chat_id,
                    message_id=game.player1_message_id,
                    text=text,
                    reply_markup=create_game_keyboard(game_id, game.player1_id, game)
                )
            except Exception as e:
                logger.error(f"Ошибка обновления следующей игры: {e}")
        
        else:
            # Серия завершена
            player_nick = get_nickname(game.player1_id)
            difficulty_names = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = difficulty_names.get(game.difficulty, '🤖')
            
            final_text = (
                f"🏁 Серия игр завершена!\n\n"
                f"Финальный счет:\n"
                f"{player_nick}: {game.player1_score}\n"
                f"Бот ({diff_icon} {game.difficulty}): {game.player2_score}\n\n"
                f"Чтобы сыграть снова, вернитесь в меню."
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
            
            # Очищаем игру
            if game_id in games:
                del games[game_id]
            if str(game.player1_id) in player_game:
                del player_game[str(game.player1_id)]
    
    # Для мультиплеера
    elif game.mode == 'multiplayer':
        # Ищем лобби с этой игрой
        for lobby_id, lobby in lobbies.items():
            if lobby['game_id'] == game_id:
                games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
                
                if lobby['current'] < lobby['total']:
                    # Начинаем следующую игру
                    lobby['current'] += 1
                    
                    # Создаем новую доску
                    game.board = ['⬜'] * 9
                    game.game_over = False
                    game.winner = None
                    game.current_game = lobby['current']
                    
                    # Определяем, кто ходит первым (чередуем)
                    if lobby['current'] % 2 == 0:
                        game.current_turn = lobby['player2']
                    else:
                        game.current_turn = lobby['creator']
                    
                    # Получаем ники
                    creator_nick = get_nickname(lobby['creator'])
                    player2_nick = get_nickname(lobby['player2'])
                    
                    score_display = game.get_score_display()
                    header = f"👥 {creator_nick} (❌) vs {player2_nick} (⭕)\n{score_display}\n"
                    match_info = f"⚔️ Матч {lobby['current']}/{games_count}\n\n"
                    
                    if game.current_turn == lobby['creator']:
                        turn_text = f"Ход игрока {creator_nick} (❌)"
                    else:
                        turn_text = f"Ход игрока {player2_nick} (⭕)"
                    
                    chat_status = "💬 Чат есть" if game.chat_enabled else ""
                    voice_status = "🎤 Голосовой чат активен (отправляйте голосовые!)"
                    text = match_info + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\n{turn_text}"
                    
                    # Обновляем сообщения у обоих игроков
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game.player1_chat_id,
                            message_id=game.player1_message_id,
                            text=text,
                            reply_markup=create_game_keyboard(game_id, game.current_turn, game)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обновления у игрока 1: {e}")
                    
                    try:
                        await context.bot.edit_message_text(
                            chat_id=game.player2_chat_id,
                            message_id=game.player2_message_id,
                            text=text,
                            reply_markup=create_game_keyboard(game_id, game.current_turn, game)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обновления у игрока 2: {e}")
                
                else:
                    # Серия завершена - показываем финальный счет и предлагаем продолжить
                    creator_nick = get_nickname(lobby['creator'])
                    player2_nick = get_nickname(lobby['player2'])
                    
                    # Определяем победителя серии
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
                    
                    # Отправляем финальный счет обоим игрокам
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
    """Подключение к лобби"""
    lobby = lobbies[lobby_id]
    
    # Создаем новую игру
    game_id = str(uuid.uuid4())[:8]
    game = TicTacToe(
        game_id,
        lobby['creator'],
        user_id,
        'multiplayer',
        total_games=lobby['total'],
        chat_enabled=lobby['chat_enabled'],
        lobby_id=lobby_id
    )
    
    games[game_id] = game
    player_game[lobby['creator']] = game_id
    player_game[user_id] = game_id
    
    lobby['player2'] = user_id
    lobby['game_id'] = game_id
    lobby['score1'] = 0
    lobby['score2'] = 0
    
    # Получаем ники
    creator_nick = get_nickname(lobby['creator'])
    joiner_nick = get_nickname(user_id)
    
    games_count = "∞" if lobby['total'] == 999999 else str(lobby['total'])
    score_display = game.get_score_display()
    header = f"👥 {creator_nick} (❌) vs {joiner_nick} (⭕)\n{score_display}\n"
    match_info = f"⚔️ Матч 1/{games_count}\n\n"
    turn_text = f"Ход игрока {creator_nick} (❌)"
    chat_status = "💬 Чат есть" if game.chat_enabled else ""
    voice_status = "🎤 Голосовой чат активен (отправляйте голосовые!)"
    
    text = match_info + header + game.get_board_display() + f"\n{chat_status}\n{voice_status}\n{turn_text}"
    
    # Отправляем сообщение создателю
    msg1 = await context.bot.send_message(
        lobby['creator'],
        text,
        reply_markup=create_game_keyboard(game_id, lobby['creator'], game)
    )
    game.player1_message_id = msg1.message_id
    game.player1_chat_id = msg1.chat_id
    
    # Отправляем сообщение подключившемуся
    msg2 = await context.bot.send_message(
        user_id,
        text,
        reply_markup=create_game_keyboard(game_id, lobby['creator'], game)
    )
    game.player2_message_id = msg2.message_id
    game.player2_chat_id = msg2.chat_id
    
    # Уведомление
    notification = f"✅ Подключено к комнате '{lobby['name']}'\nИгра началась!"
    
    if query:
        await query.edit_message_text(notification)
    else:
        await context.bot.send_message(user_id, notification)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    # Обработка голосовых сообщений (РАБОТАЕТ В ЛЮБОЙ МОМЕНТ БЕЗ КНОПОК)
    if update.message.voice:
        voice = update.message.voice
        
        # Проверяем, есть ли активная игра
        if user_id in player_game:
            game_id = player_game[user_id]
            game = games.get(game_id)
            
            if game:
                # Получаем файл голосового сообщения
                voice_file = await context.bot.get_file(voice.file_id)
                
                # Если игра с ботом
                if game.mode == 'bot' and game.chat_enabled:
                    # Отправляем подтверждение
                    await update.message.reply_text("🎤 Бот слушает...")
                    
                    # Генерируем ответ
                    bot_player = BotPlayer(game.difficulty, True)
                    if hasattr(bot_player, 'neural') and bot_player.neural:
                        # Получаем текстовый ответ от нейросети
                        response_text = bot_player.neural.get_chat_response(game, "голосовое сообщение")
                        
                        # Конвертируем текст в голос
                        audio_data = await voice_bot.text_to_speech(response_text, game.difficulty)
                        
                        if audio_data:
                            # Отправляем голосовой ответ
                            await context.bot.send_voice(
                                chat_id=user_id,
                                voice=audio_data,
                                caption=f"🤖 Бот ({game.difficulty}) отвечает:"
                            )
                        else:
                            # Если TTS не сработал, отправляем текстом
                            await update.message.reply_text(f"🤖 {response_text}")
                    
                    # Добавляем в историю чата
                    game.add_chat_message(user_id, "🎤 [Голосовое сообщение]")
                    game.add_chat_message('bot', "🎤 [Голосовой ответ]")
                    save_data()
                
                # Если мультиплеер
                elif game.mode == 'multiplayer' and game.chat_enabled:
                    # Определяем соперника
                    opponent_id = str(game.player2_id) if user_id == str(game.player1_id) else str(game.player1_id)
                    
                    if opponent_id:
                        # Пересылаем голосовое сообщение сопернику
                        await context.bot.send_voice(
                            chat_id=opponent_id,
                            voice=voice.file_id,
                            caption=f"🎤 Голосовое сообщение от {get_nickname(user_id)}"
                        )
                        
                        # Добавляем в историю чата
                        game.add_chat_message(user_id, "🎤 [Голосовое сообщение]")
                        save_data()
                        
                        await update.message.reply_text("✅ Голосовое сообщение отправлено сопернику!")
                
                return
            else:
                await update.message.reply_text("❌ Игра не найдена. Начните новую игру через /start")
                return
        else:
            await update.message.reply_text("❌ У вас нет активной игры. Начните игру через /start")
            return
    
    # Текстовые сообщения (остальная логика)
    text = update.message.text
    
    # Установка ника
    if user_id in temp_set_nickname:
        nickname = text[:20]
        user_nicknames[user_id] = nickname
        save_data()
        del temp_set_nickname[user_id]
        
        await update.message.reply_text(
            f"✅ Ник установлен: {nickname}\n\n"
            f"Возвращайтесь в меню: /start"
        )
    
    # Создание комнаты - название
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
    
    # Создание комнаты - пароль
    elif user_id in temp_lobby_password:
        data = temp_lobby_password[user_id]
        chat_config = temp_lobby_chat.get(user_id, {'enabled': False})
        chat_enabled = chat_config['enabled']
        
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
            'chat_enabled': chat_enabled,
            'created': time.time()
        }
        
        del temp_lobby_password[user_id]
        if user_id in temp_lobby_chat:
            del temp_lobby_chat[user_id]
        
        games_count = "∞" if data['total'] == 999999 else str(data['total'])
        chat_status = "💬 Обычный чат" if chat_enabled else "🎮 Без чата"
        
        await update.message.reply_text(
            f"✅ Комната создана!\n\n"
            f"🏷 Название: {data['name']}\n"
            f"🆔 ID: {lobby_id}\n"
            f"🎮 Серия: {games_count} игр\n"
            f"{chat_status}\n"
            f"🔒 Пароль: {pass_text}\n\n"
            f"Отправьте ID другу: /join {lobby_id}\n"
            f"Ожидайте подключения..."
        )
    
    # Подключение к комнате - пароль
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
    
    # Подключение по команде /join
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

def create_game_keyboard(game_id, current_player_id, game):
    """Создает клавиатуру для игры"""
    game_obj = games.get(game_id)
    if not game_obj:
        return None
    
    keyboard = []
    row = []
    
    for i in range(9):
        # Кнопка активна только для текущего игрока и если клетка свободна
        if game_obj.current_turn == current_player_id and game_obj.board[i] == '⬜' and not game_obj.game_over:
            callback = f'move_{i}'
        else:
            callback = 'no_move'
        
        row.append(InlineKeyboardButton(game_obj.board[i], callback_data=callback))
        
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    
    # Добавляем информационную кнопку о голосовом чате (неактивную)
    if game_obj.chat_enabled:
        keyboard.append([InlineKeyboardButton("🎤 Голосовой чат активен (просто отправьте голосовое!)", callback_data='no_move')])
    
    keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data='menu_main')])
    return InlineKeyboardMarkup(keyboard)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    
    # Проверяем, не вышел ли игрок из игры
    if update and update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        
        # Проверяем, есть ли у игрока активная игра
        if user_id in player_game:
            game_id = player_game[user_id]
            game = games.get(game_id)
            
            if game and game.mode == 'multiplayer' and game.player2_id:
                # Уведомляем второго игрока
                opponent_id = str(game.player2_id) if user_id == str(game.player1_id) else str(game.player1_id)
                
                try:
                    await context.bot.send_message(
                        opponent_id,
                        "⚠️ Соперник покинул игру.\n\nВозвращайтесь в меню: /start"
                    )
                except:
                    pass
                
                # Очищаем игру
                if game_id in games:
                    del games[game_id]
                if user_id in player_game:
                    del player_game[user_id]
                if opponent_id in player_game:
                    del player_game[opponent_id]

def main():
    print("🤖 Запуск бота...")
    print("✅ Голосовой чат активен для всех режимов")
    print("✅ Просто отправляйте голосовые сообщения во время игры")
    print("✅ Бот отвечает голосом!")
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_message))  # Обработка голосовых в любое время
    app.add_error_handler(error_handler)
    
    print("✅ Бот успешно запущен!")
    print("👉 Отправьте /start в Telegram")
    
    app.run_polling()

if __name__ == '__main__':
    main()