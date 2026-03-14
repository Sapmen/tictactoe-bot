import logging
import random
import time
import uuid
import json
import os
import atexit
import signal
import sys
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

# Загрузка сохраненных данных с защитой от повреждения
def load_data():
    global user_nicknames, user_stats
    try:
        if os.path.exists(NICKNAMES_FILE):
            with open(NICKNAMES_FILE, 'r', encoding='utf-8') as f:
                user_nicknames = json.load(f)
                # Конвертируем ключи обратно в строки (для совместимости)
                user_nicknames = {str(k): v for k, v in user_nicknames.items()}
        else:
            user_nicknames = {}
    except Exception as e:
        logger.error(f"Ошибка загрузки ников: {e}")
        # Создаем резервную копию поврежденного файла
        if os.path.exists(NICKNAMES_FILE):
            os.rename(NICKNAMES_FILE, NICKNAMES_FILE + '.bak')
        user_nicknames = {}
    
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                user_stats = json.load(f)
                # Конвертируем ключи обратно в строки
                user_stats = {str(k): v for k, v in user_stats.items()}
        else:
            user_stats = {}
    except Exception as e:
        logger.error(f"Ошибка загрузки статистики: {e}")
        if os.path.exists(STATS_FILE):
            os.rename(STATS_FILE, STATS_FILE + '.bak')
        user_stats = {}

# Сохранение данных с немедленной записью на диск
def save_data():
    try:
        # Сначала сохраняем во временный файл
        temp_nicknames = NICKNAMES_FILE + '.tmp'
        with open(temp_nicknames, 'w', encoding='utf-8') as f:
            json.dump(user_nicknames, f, ensure_ascii=False, indent=2)
        os.replace(temp_nicknames, NICKNAMES_FILE)  # Атомарная замена
    except Exception as e:
        logger.error(f"Ошибка сохранения ников: {e}")
    
    try:
        temp_stats = STATS_FILE + '.tmp'
        with open(temp_stats, 'w', encoding='utf-8') as f:
            json.dump(user_stats, f, ensure_ascii=False, indent=2)
        os.replace(temp_stats, STATS_FILE)
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {e}")

# Функция для сброса статистики конкретного игрока
def reset_user_stats(user_id):
    user_id_str = str(user_id)
    if user_id_str in user_stats:
        user_stats[user_id_str] = {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0}
        save_data()
        return True
    return False

# Сохраняем данные при выходе
def exit_handler():
    logger.info("Сохраняем данные перед выходом...")
    save_data()

atexit.register(exit_handler)

# Обработка сигналов для экстренного завершения
def signal_handler(sig, frame):
    logger.info(f"Получен сигнал {sig}, сохраняем данные...")
    save_data()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Загружаем данные при старте
load_data()
save_data()  # Сохраняем сразу после загрузки, чтобы создать файлы

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
temp_bot_difficulty = {}
temp_bot_symbol = {}
temp_bot_chat = {}
temp_bot_series = {}

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

# УЛУЧШЕННЫЕ УРОВНИ СЛОЖНОСТИ БОТОВ
class EasyBot:
    def get_move(self, game, available):
        return random.choice(available)

class MediumBot:
    def get_move(self, game, available):
        # 70% умных ходов, 30% случайных
        if random.random() < 0.7:
            # Пытается выиграть
            for pos in available:
                game.board[pos] = game.bot_symbol
                if game.check_win(game.bot_symbol):
                    game.board[pos] = '⬜'
                    return pos
                game.board[pos] = '⬜'
            
            # Пытается заблокировать
            for pos in available:
                game.board[pos] = game.player_symbol
                if game.check_win(game.player_symbol):
                    game.board[pos] = '⬜'
                    return pos
                game.board[pos] = '⬜'
            
            # Центр в приоритете
            if 4 in available:
                return 4
            
            # Углы
            corners = [0, 2, 6, 8]
            available_corners = [c for c in corners if c in available]
            if available_corners:
                return random.choice(available_corners)
        
        return random.choice(available)

class HardBot:
    def get_move(self, game, available):
        # 90% умных ходов
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
        
        # Создание двойных угроз
        for pos in available:
            game.board[pos] = game.bot_symbol
            threats = 0
            for combo in [[0,1,2], [3,4,5], [6,7,8], [0,3,6], [1,4,7], [2,5,8], [0,4,8], [2,4,6]]:
                if pos in combo:
                    line = [game.board[i] for i in combo]
                    if line.count(game.bot_symbol) == 2 and line.count('⬜') == 1:
                        threats += 1
            game.board[pos] = '⬜'
            if threats >= 2:
                return pos
        
        # Центр
        if 4 in available:
            return 4
        
        # Углы
        corners = [0, 2, 6, 8]
        available_corners = [c for c in corners if c in available]
        if available_corners:
            return random.choice(available_corners)
        
        return random.choice(available)

class ImpossibleBot:
    def get_move(self, game, available):
        # Минимакс алгоритм (идеальная игра)
        best_score = -float('inf')
        best_move = available[0]
        
        for pos in available:
            # Пробуем сходить
            game.board[pos] = game.bot_symbol
            
            # Оцениваем ход
            score = self.minimax(game, 0, False)
            
            # Отменяем ход
            game.board[pos] = '⬜'
            
            if score > best_score:
                best_score = score
                best_move = pos
        
        return best_move
    
    def minimax(self, game, depth, is_maximizing):
        # Проверка на победу бота
        if game.check_win(game.bot_symbol):
            return 10 - depth
        # Проверка на победу игрока
        if game.check_win(game.player_symbol):
            return depth - 10
        # Проверка на ничью
        if '⬜' not in game.board:
            return 0
        
        available = [i for i, cell in enumerate(game.board) if cell == '⬜']
        
        if is_maximizing:
            best_score = -float('inf')
            for pos in available:
                game.board[pos] = game.bot_symbol
                score = self.minimax(game, depth + 1, False)
                game.board[pos] = '⬜'
                best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for pos in available:
                game.board[pos] = game.player_symbol
                score = self.minimax(game, depth + 1, True)
                game.board[pos] = '⬜'
                best_score = min(score, best_score)
            return best_score

class BotPlayer:
    def __init__(self, difficulty='easy'):
        self.difficulty = difficulty
        self.easy_bot = EasyBot()
        self.medium_bot = MediumBot()
        self.hard_bot = HardBot()
        self.impossible_bot = ImpossibleBot()
        
    def get_move(self, game):
        available = [i for i, cell in enumerate(game.board) if cell == '⬜']
        
        if not available:
            return None
        
        if self.difficulty == 'easy':
            return self.easy_bot.get_move(game, available)
        elif self.difficulty == 'medium':
            return self.medium_bot.get_move(game, available)
        elif self.difficulty == 'hard':
            return self.hard_bot.get_move(game, available)
        else:  # impossible
            return self.impossible_bot.get_move(game, available)

# НАСТОЯЩАЯ НЕЙРОСЕТЬ - ИНДИВИДУАЛЬНЫЕ ОТВЕТЫ
class RealNeuralNetwork:
    def __init__(self):
        self.user_context = {}
        
    def get_response(self, user_id, message):
        """Генерирует индивидуальный ответ на основе сообщения"""
        message_lower = message.lower()
        
        # Инициализация контекста для нового пользователя
        if user_id not in self.user_context:
            self.user_context[user_id] = {
                'history': [],
                'mood': 'neutral',
                'topic': None
            }
        
        context = self.user_context[user_id]
        context['history'].append(message)
        if len(context['history']) > 10:
            context['history'].pop(0)
        
        # Приветствия
        if any(word in message_lower for word in ['привет', 'здравствуй', 'здаров', 'хай', 'ку', 'hello']):
            responses = [
                "Привет! Как твои дела?",
                "Здравствуй! Рад тебя видеть!",
                "О, привет! Давно не виделись!",
                "Хай! Как настроение?",
                "Здарова! Чем займемся сегодня?"
            ]
            context['mood'] = 'friendly'
            return random.choice(responses)
        
        # Вопросы о делах
        elif any(word in message_lower for word in ['как дела', 'как ты', 'чё как', 'что нового', 'как жизнь']):
            responses = [
                "У меня всё отлично! А у тебя как?",
                "Хорошо, вот играю с тобой! А ты как?",
                "Норм, скучал по тебе! Рассказывай!",
                "Отлично! Рад что ты спросил! У тебя как?",
                "Всё супер! Давай лучше про тебя поговорим?"
            ]
            return random.choice(responses)
        
        # Рассказы о себе
        elif any(word in message_lower for word in ['у меня', 'я сегодня', 'со мной']):
            responses = [
                "Ого, расскажи подробнее!",
                "Правда? Это очень интересно!",
                "Круто! А что дальше?",
                "Я тебя слушаю внимательно!",
                "Здорово! Продолжай!"
            ]
            return random.choice(responses)
        
        # Вопросы о игре
        elif any(word in message_lower for word in ['игра', 'ходи', 'клетк', 'побед', 'стратегия']):
            responses = [
                "Давай играть! Твой ход!",
                "Интересная партия получается!",
                "Я слежу за игрой внимательно!",
                "Отличный ход! Давай дальше!",
                "А ты хорошо играешь!"
            ]
            return random.choice(responses)
        
        # Комплименты
        elif any(word in message_lower for word in ['молодец', 'умница', 'хорош', 'крут', 'класс', 'отлично']):
            responses = [
                "Спасибо большое! Ты тоже молодец!",
                "Ой, спасибо! Очень приятно!",
                "Благодарю! Ты делаешь мой день лучше!",
                "Стараюсь! Ты вообще красавчик!",
                "Спасибо, очень ценю твои слова!"
            ]
            return random.choice(responses)
        
        # Прощания
        elif any(word in message_lower for word in ['пока', 'до свидания', 'до встречи', 'удач', 'прощай']):
            responses = [
                "Пока! Заходи еще, буду ждать!",
                "До встречи! Было приятно пообщаться!",
                "Удачи тебе! Возвращайся скорее!",
                "Пока-пока! Хорошего дня!",
                "До связи! Всегда рад поболтать!"
            ]
            return random.choice(responses)
        
        # Спасибо
        elif any(word in message_lower for word in ['спасиб', 'благодар']):
            responses = [
                "Пожалуйста! Обращайся в любой момент!",
                "Не за что! Всегда рад помочь!",
                "На здоровье! Спасибо тебе за общение!",
                "Да не за что! Ты классный собеседник!",
                "Пожалуйста, дорогой!"
            ]
            return random.choice(responses)
        
        # Вопросы о боте
        elif any(word in message_lower for word in ['ты кто', 'что ты', 'бот']):
            responses = [
                "Я нейросетевой бот, помогаю играть в крестики-нолики!",
                "Я твой виртуальный собеседник и партнер по игре!",
                "Я нейросеть, созданная для общения и игры!",
                "Я бот с искусственным интеллектом! Рад познакомиться!",
                "Я твой друг и помощник в игре!"
            ]
            return random.choice(responses)
        
        # Вопросы о погоде/жизни
        elif any(word in message_lower for word in ['погода', 'холодно', 'тепло', 'солнце']):
            responses = [
                "Я в интернете не чувствую погоду, но надеюсь у тебя всё хорошо!",
                "За окном не вижу, но желаю тебе хорошего дня!",
                "Не знаю, но пусть у тебя будет солнечно на душе!",
                "Погода не важна, когда есть хорошая игра!"
            ]
            return random.choice(responses)
        
        # Общие ответы (индивидуальные для каждого)
        else:
            responses = [
                "Понял тебя! Расскажи еще что-нибудь!",
                "Интересно! А что думаешь по этому поводу?",
                "Я тебя слушаю, продолжай!",
                "Давай, мне очень интересно!",
                "Ого! А дальше что было?",
                "Правда? Здорово!",
                "Я так рад, что мы общаемся!",
                "Ты классный собеседник, продолжай!",
                "Хм, интересная мысль!",
                "Расскажи подробнее об этом!"
            ]
            return random.choice(responses)

# Нейросеть для общения
neural_network = RealNeuralNetwork()

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
        
        difficulty = temp_bot_difficulty.get(user_id, 'easy')
        symbol = temp_bot_symbol.get(user_id, 'X')
        chat_enabled = temp_bot_chat.get(user_id, False)
        
        if symbol == 'X':
            player_symbol = '❌'
            bot_symbol = '⭕'
        else:
            player_symbol = '⭕'
            bot_symbol = '❌'
        
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
    
    # Статистика с кнопкой сброса
    elif data == 'menu_stats':
        user_id_str = str(user_id)
        stats = user_stats.get(user_id_str, {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0})
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
        
        # Добавляем кнопку сброса статистики
        keyboard = [
            [InlineKeyboardButton("🔄 Сбросить статистику", callback_data='reset_stats')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Сброс статистики
    elif data == 'reset_stats':
        user_id_str = str(user_id)
        
        # Запрашиваем подтверждение
        keyboard = [
            [InlineKeyboardButton("✅ Да, сбросить", callback_data='confirm_reset')],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data='menu_stats')]
        ]
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите сбросить всю статистику?\n\nЭто действие нельзя отменить.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Подтверждение сброса статистики
    elif data == 'confirm_reset':
        user_id_str = str(user_id)
        
        if reset_user_stats(user_id):
            text = "✅ Статистика успешно сброшена!"
        else:
            text = "❌ Ошибка при сбросе статистики"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='menu_main')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'menu_help':
        text = (
            "❓ **ПОМОЩЬ**\n\n"
            "🎮 **Как играть:**\n"
            "• Нажимайте на ⬜ клетки\n"
            "• Соберите 3 в ряд для победы\n\n"
            "🤖 **Уровни сложности:**\n"
            "• 🟢 Легкий - случайные ходы\n"
            "• 🟡 Средний - 70% умных ходов\n"
            "• 🔴 Сложный - двойные угрозы\n"
            "• 🤖 Нейросеть - минимакс (идеальная игра)\n\n"
            "👥 **Мультиплеер:**\n"
            "• Создайте комнату\n"
            "• Отправьте ID другу\n\n"
            "💬 **Чат с нейросетью:**\n"
            "• Просто пиши сообщения во время игры\n"
            "• Нейросеть отвечает индивидуально\n"
            "• Помнит контекст разговора\n\n"
            "📊 **Статистика:**\n"
            "• Сохраняется даже при сбоях\n"
            "• Можно сбросить кнопкой\n\n"
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
    text = update.message.text
    
    # ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ - НЕЙРОСЕТЬ ОТВЕЧАЕТ ИНДИВИДУАЛЬНО
    if user_id in player_game:
        game_id = player_game[user_id]
        game = games.get(game_id)
        
        if game and game.mode == 'bot' and game.chat_enabled:
            # НАСТОЯЩАЯ НЕЙРОСЕТЬ - ИНДИВИДУАЛЬНЫЙ ОТВЕТ
            response = neural_network.get_response(user_id, text)
            
            await update.message.reply_text(f"🤖 {response}")
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
    print("🎮 КРЕСТИКИ-НОЛИКИ - НАДЕЖНАЯ ВЕРСИЯ")
    print("=" * 50)
    print("✅ СОХРАНЕНИЕ ДАННЫХ: никнеймы и статистика")
    print("✅ АТОМАРНАЯ ЗАПИСЬ: без повреждения файлов")
    print("✅ АВТОСОХРАНЕНИЕ: при выходе и сигналах")
    print("✅ КНОПКА СБРОСА: в разделе статистики")
    print("✅ УЛУЧШЕННЫЕ УРОВНИ СЛОЖНОСТИ")
    print("=" * 50)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("🚀 Бот запущен! Отправьте /start в Telegram")
    app.run_polling()

if __name__ == '__main__':
    main()