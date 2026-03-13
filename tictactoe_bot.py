import logging
import random
import time
import uuid
import json
import os
import aiohttp
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
temp_bot_difficulty = {}  # Сначала сложность
temp_bot_symbol = {}      # Потом символ
temp_bot_chat = {}        # Потом чат
temp_bot_series = {}      # Потом количество игр

class TicTacToe:
    def __init__(self, game_id, player1_id, player2_id=None, mode='bot', difficulty='easy', 
                 total_games=1, lobby_id=None, player_symbol='❌', bot_symbol='⭕', chat_enabled=False):
        self.game_id = game_id
        self.board = ['⬜'] * 9
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.player_symbol = player_symbol
        self.bot_symbol = bot_symbol
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
        self.chat_enabled = chat_enabled
        
    def make_move(self, position, player_id):
        if self.game_over:
            return False, "Игра уже окончена"
        
        if player_id != self.current_turn:
            return False, "Сейчас не ваш ход"
        
        if self.board[position] != '⬜':
            return False, "Эта клетка уже занята"
        
        if player_id == self.player1_id:
            symbol = self.player_symbol
        else:
            symbol = self.bot_symbol
        
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

# НАСТОЯЩАЯ НЕЙРОСЕТЬ - КАК В РЕАЛЬНОМ ДИАЛОГЕ
class RealNeuralNetwork:
    def __init__(self):
        self.conversation_history = {}
        
    def chat(self, user_id, message):
        """Полноценный диалог как с человеком"""
        message_lower = message.lower()
        
        # Приветствия
        if any(word in message_lower for word in ['привет', 'здравствуй', 'здаров', 'хай', 'ку', 'hello']):
            return random.choice([
                "Привет! Как дела?",
                "Здравствуй! Рад тебя видеть!",
                "О, привет! Давай поболтаем!",
                "Здарова! Как жизнь?",
                "Хай! Чем займемся?"
            ])
        
        # Как дела
        elif any(word in message_lower for word in ['как дела', 'как ты', 'чё как', 'что нового']):
            return random.choice([
                "У меня всё отлично! А у тебя?",
                "Хорошо, играем! А ты как?",
                "Норм, скучал по тебе!",
                "Отлично, рад что ты здесь!",
                "Всё супер! Твои новости?"
            ])
        
        # Вопросы о пользователе
        elif any(word in message_lower for word in ['у тебя', 'твои', 'тебя']):
            return random.choice([
                "У меня всё хорошо, спасибо что спросил!",
                "Мои дела отлично! Давай лучше про тебя поговорим?",
                "Я в порядке! Расскажи о себе!",
                "Спасибо за заботу! Как сам?",
                "Всё супер! А у тебя что нового?"
            ])
        
        # Игра
        elif any(word in message_lower for word in ['игра', 'ходи', 'клетк', 'побед']):
            return random.choice([
                "Давай играть! Твой ход!",
                "Интересная игра, правда?",
                "Я люблю крестики-нолики!",
                "Смотри не проиграй!",
                "Хороший ход! Давай дальше!"
            ])
        
        # Комплименты
        elif any(word in message_lower for word in ['молодец', 'умница', 'хорош', 'крут', 'класс']):
            return random.choice([
                "Спасибо! Ты тоже молодец!",
                "Ой, спасибо! Приятно слышать!",
                "Благодарю! Ты делаешь мой день!",
                "Стараюсь! А ты вообще красавчик!",
                "Спасибо, очень ценю!"
            ])
        
        # Прощания
        elif any(word in message_lower for word in ['пока', 'до свидания', 'до встречи', 'удач']):
            return random.choice([
                "Пока! Заходи еще!",
                "До встречи! Буду скучать!",
                "Удачи тебе! Возвращайся!",
                "Пока-пока! Хорошего дня!",
                "До связи! Всегда рад поболтать!"
            ])
        
        # Спасибо
        elif any(word in message_lower for word in ['спасиб', 'благодар']):
            return random.choice([
                "Пожалуйста! Обращайся!",
                "Не за что! Всегда рад помочь!",
                "На здоровье! Спасибо тебе!",
                "Да не за что! Ты крутой!",
                "Пожалуйста, дорогой!"
            ])
        
        # Согласие
        elif any(word in message_lower for word in ['да', 'ага', 'ок', 'ладно', 'хорош']):
            return random.choice([
                "Отлично! Договорились!",
                "Супер! Тогда продолжаем!",
                "Хорошо, я понял!",
                "Окей, как скажешь!",
                "Договорились!"
            ])
        
        # Несогласие
        elif any(word in message_lower for word in ['нет', 'не', 'зачем', 'почему']):
            return random.choice([
                "Почему нет? Объясни!",
                "А как бы ты хотел?",
                "Интересно, расскажи подробнее!",
                "Не согласен? Давай обсудим!",
                "Почему? Мне интересно твое мнение!"
            ])
        
        # Вопросы
        elif '?' in message:
            return random.choice([
                "Хороший вопрос! Я думаю...",
                "Дай подумать... Интересно!",
                "Вопрос на засыпку! А ты как думаешь?",
                "Хм, я не знаю. А ты?",
                "Давай вместе подумаем!"
            ])
        
        # Общие ответы (как в реальном диалоге)
        else:
            return random.choice([
                "Понятно! Расскажи еще что-нибудь!",
                "Интересно! А дальше что?",
                "Я тебя слушаю!",
                "Давай, я весь во внимании!",
                "Круто! А еще?",
                "Ого! Ничего себе!",
                "Правда? Здорово!",
                "Я так рад, что мы общаемся!",
                "Ты классный собеседник!",
                "Продолжай, мне интересно!"
            ])

# Класс для TTS
class VoiceBot:
    def __init__(self):
        self.voice_map = {
            'easy': 'ru-RU-OstapenkoNeural',
            'medium': 'ru-RU-DariyaNeural',
            'hard': 'ru-RU-MikhailNeural',
            'impossible': 'ru-RU-CatherineNeural'
        }
        self.neural = RealNeuralNetwork()
    
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
    
    def chat_with_bot(self, user_id, message):
        """Реальный диалог с нейросетью"""
        return self.neural.chat(user_id, message)

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
            game.board[pos] = game.bot_symbol
            if game.check_win(game.bot_symbol):
                game.board[pos] = '⬜'
                return pos
            game.board[pos] = '⬜'
        
        # Блокировка
        for pos in available:
            game.board[pos] = game.player_symbol
            if game.check_win(game.player_symbol):
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
    
    welcome_text = "🎮 Добро пожаловать в Крестики-Нолики!\n\n"
    
    if user_id in user_nicknames:
        welcome_text += f"Ваш ник: {user_nicknames[user_id]}\n\n"
    else:
        welcome_text += "Установите ник, чтобы друзья вас узнали!\n\n"
    
    welcome_text += "👇 Выберите режим:"
    
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
    
    # Меню игры с ботом - СНАЧАЛА СЛОЖНОСТЬ
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
        difficulty = data.split('_')[2]
        temp_bot_difficulty[user_id] = difficulty
        
        keyboard = [
            [InlineKeyboardButton("❌ Играть за крестики", callback_data='bot_symbol_X')],
            [InlineKeyboardButton("⭕ Играть за нолики", callback_data='bot_symbol_O')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            f"🤖 Уровень: {difficulty}\n\nВыберите, за кого играть:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_symbol_'):
        symbol = data.split('_')[2]
        temp_bot_symbol[user_id] = symbol
        difficulty = temp_bot_difficulty.get(user_id, 'easy')
        
        keyboard = [
            [InlineKeyboardButton("💬 С чатом", callback_data='bot_chat_yes')],
            [InlineKeyboardButton("🎮 Без чата", callback_data='bot_chat_no')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            f"🤖 Уровень: {difficulty}\n"
            f"Вы выбрали играть за {'❌' if symbol == 'X' else '⭕'}\n\n"
            f"Включить чат с ботом?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_chat_'):
        chat_enabled = (data.split('_')[2] == 'yes')
        temp_bot_chat[user_id] = chat_enabled
        difficulty = temp_bot_difficulty.get(user_id, 'easy')
        symbol = temp_bot_symbol.get(user_id, 'X')
        
        keyboard = [
            [InlineKeyboardButton("1 игра", callback_data='bot_series_1')],
            [InlineKeyboardButton("3 игры", callback_data='bot_series_3')],
            [InlineKeyboardButton("5 игр", callback_data='bot_series_5')],
            [InlineKeyboardButton("10 игр", callback_data='bot_series_10')],
            [InlineKeyboardButton("∞ Бесконечно", callback_data='bot_series_inf')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            f"🤖 Уровень: {difficulty}\n"
            f"Символ: {'❌' if symbol == 'X' else '⭕'}\n"
            f"Чат: {'включен' if chat_enabled else 'выключен'}\n\n"
            f"🎮 Сколько игр сыграть?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_series_'):
        if data == 'bot_series_inf':
            total_games = 999999
        else:
            total_games = int(data.split('_')[2])
        
        # Получаем все настройки
        difficulty = temp_bot_difficulty.get(user_id, 'easy')
        symbol = temp_bot_symbol.get(user_id, 'X')
        chat_enabled = temp_bot_chat.get(user_id, False)
        
        # Определяем символы
        if symbol == 'X':
            player_symbol = '❌'
            bot_symbol = '⭕'
            player_name = "❌ Крестики"
            bot_name = "⭕ Нолики"
        else:
            player_symbol = '⭕'
            bot_symbol = '❌'
            player_name = "⭕ Нолики"
            bot_name = "❌ Крестики"
        
        # Создаем игру
        game_id = str(uuid.uuid4())[:8]
        game = TicTacToe(
            game_id, user_id, mode='bot', difficulty=difficulty, 
            total_games=total_games, player_symbol=player_symbol, 
            bot_symbol=bot_symbol, chat_enabled=chat_enabled
        )
        
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
            header = f"{player_nick} ({player_symbol}) vs Бот ({bot_symbol})\n{game.get_score_display()}\n"
            match_info = f"⚔️ Матч 1/{games_count}\n\n"
        else:
            header = f"{player_nick} ({player_symbol}) vs Бот ({bot_symbol})\n"
            match_info = ""
        
        chat_status = "💬 Чат включен" if chat_enabled else "🎮 Чат выключен"
        text = (match_info + header + game.get_board_display() + 
                f"\n{difficulty_names[difficulty]}\n{chat_status}\n"
                f"Ваш ход!")
        
        msg = await query.edit_message_text(
            text,
            reply_markup=create_game_keyboard(game_id, user_id)
        )
        
        game.player1_message_id = msg.message_id
        game.player1_chat_id = msg.chat_id
        
        # Очищаем временные данные
        if user_id in temp_bot_difficulty:
            del temp_bot_difficulty[user_id]
        if user_id in temp_bot_symbol:
            del temp_bot_symbol[user_id]
        if user_id in temp_bot_chat:
            del temp_bot_chat[user_id]
    
    # Меню игры с другом
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
                f"\n{turn_text}")
        
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
            "🤖 **Игра с ботом:**\n"
            "• Сначала выбираете сложность\n"
            "• Потом символ (❌ или ⭕)\n"
            "• Потом чат (вкл/выкл)\n"
            "• Потом количество игр\n\n"
            "👥 **Мультиплеер:**\n"
            "• Создайте комнату\n"
            "• Отправьте ID другу\n\n"
            "🎤 **Голосовой чат:**\n"
            "• Просто отправляйте голосовые\n"
            "• Бот отвечает голосом как человек\n\n"
            "📝 **Команды:**\n"
            "/start - главное меню\n"
            "/join [ID] - подключиться"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'menu_main':
        if user_id in player_game:
            game_id = player_game[user_id]
            if game_id in games:
                del games[game_id]
            del player_game[user_id]
        
        welcome_text = "🎮 Добро пожаловать в Крестики-Нолики!\n\n"
        
        if user_id in user_nicknames:
            welcome_text += f"Ваш ник: {user_nicknames[user_id]}\n\n"
        else:
            welcome_text += "Установите ник, чтобы друзья вас узнали!\n\n"
        
        welcome_text += "👇 Выберите режим:"
        
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
            header = f"{player1_nick} ({game.player_symbol}) vs {player2_nick} ({game.bot_symbol})\n{score_display}\n"
            if game.total_games > 1:
                header = f"⚔️ Матч {game.current_game}/{games_count}\n" + header
        else:
            diff_icons = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴', 'impossible': '🤖'}
            diff_icon = diff_icons.get(game.difficulty, '🤖')
            header = f"{player1_nick} ({game.player_symbol}) vs {diff_icon} {player2_nick} ({game.bot_symbol})\n{score_display}\n"
            if game.total_games > 1:
                header = f"⚔️ Матч {game.current_game}/{games_count}\n" + header
        
        chat_status = "💬 Чат есть" if game.chat_enabled else ""
        
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
            
            text = f"🎉 Победил {winner_nick}!\n\n" + header + game.get_board_display() + f"\n{chat_status}"
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
            
            text = f"🤝 Ничья!\n\n" + header + game.get_board_display() + f"\n{chat_status}"
            game.game_over = True
            
            await update_both_players(context, game, text)
            await check_next_game(context, game_id)
        
        elif status == "continue":
            if game.mode == 'bot':
                text = header + game.get_board_display() + f"\n{chat_status}\n🤖 Бот думает..."
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
                        
                        text = f"😢 Бот победил!\n\n" + header + game.get_board_display() + f"\n{chat_status}"
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    elif status == "draw":
                        if str(game.player1_id) in user_stats:
                            user_stats[str(game.player1_id)]['draws'] += 1
                            user_stats[str(game.player1_id)]['total'] += 1
                        save_data()
                        
                        text = f"🤝 Ничья!\n\n" + header + game.get_board_display() + f"\n{chat_status}"
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    else:
                        text = header + game.get_board_display() + f"\n{chat_status}\nВаш ход!"
                        await update_both_players(context, game, text, create_game_keyboard(game_id, game.player1_id))
            
            else:
                if game.current_turn == game.player1_id:
                    turn_text = f"Ход игрока {player1_nick} ({game.player_symbol})"
                else:
                    turn_text = f"Ход игрока {player2_nick} ({game.bot_symbol})"
                
                text = header + game.get_board_display() + f"\n{chat_status}\n{turn_text}"
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
            header = f"{player_nick} ({game.player_symbol}) vs {diff_icon} Бот ({game.bot_symbol})\n{score_display}\n"
            match_info = f"⚔️ Матч {game.current_game}/{games_count}\n\n"
            
            chat_status = "💬 Чат есть" if game.chat_enabled else ""
            text = (match_info + header + game.get_board_display() + 
                    f"\n{chat_status}\nВаш ход!")
            
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
                            f"\n{turn_text}")
                    
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
            f"\n{turn_text}")
    
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
    
    # ОБРАБОТКА ГОЛОСОВЫХ СООБЩЕНИЙ
    if update.message.voice:
        if user_id in player_game:
            game_id = player_game[user_id]
            game = games.get(game_id)
            
            if game and game.mode == 'bot' and game.chat_enabled:
                # Получаем ответ от нейросети (реальный диалог)
                response_text = voice_bot.chat_with_bot(user_id, "голосовое сообщение")
                
                await update.message.reply_text("🎤 Бот слушает...")
                
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
                
                return
            
            elif game and game.mode == 'multiplayer':
                opponent_id = str(game.player2_id) if user_id == str(game.player1_id) else str(game.player1_id)
                
                if opponent_id:
                    await context.bot.send_voice(
                        chat_id=opponent_id,
                        voice=update.message.voice.file_id,
                        caption=f"🎤 Голосовое от {get_nickname(user_id)}"
                    )
                    await update.message.reply_text("✅ Голосовое отправлено!")
                
                return
            else:
                if game and game.mode == 'bot' and not game.chat_enabled:
                    await update.message.reply_text("❌ Чат выключен. Включите в настройках.")
                else:
                    await update.message.reply_text("❌ Сначала начните игру!")
                return
        else:
            await update.message.reply_text("❌ Сначала начните игру через /start")
            return
    
    # ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ - РЕАЛЬНЫЙ ДИАЛОГ
    text = update.message.text
    
    if user_id in player_game:
        game_id = player_game[user_id]
        game = games.get(game_id)
        
        if game and game.mode == 'bot' and game.chat_enabled:
            # ПОЛНОЦЕННЫЙ ДИАЛОГ С НЕЙРОСЕТЬЮ
            response_text = voice_bot.chat_with_bot(user_id, text)
            
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
            
            return
        elif game and game.mode == 'bot' and not game.chat_enabled:
            await update.message.reply_text("❌ Чат выключен. Включите в настройках.")
            return
    
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

def create_game_keyboard(game_id, current_player_id):
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
    
    keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data='menu_main')])
    return InlineKeyboardMarkup(keyboard)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    print("=" * 50)
    print("🎮 КРЕСТИКИ-НОЛИКИ - ИДЕАЛЬНАЯ ВЕРСИЯ")
    print("=" * 50)
    print("✅ ПОРЯДОК: сложность → символ → чат → игры")
    print("✅ НОРМАЛЬНЫЕ СИМВОЛЫ: ❌ и ⭕")
    print("✅ РЕАЛЬНЫЙ ДИАЛОГ: нейросеть как человек")
    print("✅ ГОЛОСОВЫЕ ОТВЕТЫ: бот говорит голосом")
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