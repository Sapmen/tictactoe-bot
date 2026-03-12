import logging
import random
import time
import uuid
import json
import os
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
                # Конвертируем ключи обратно в int
                user_nicknames = {int(k): v for k, v in user_nicknames.items()}
        else:
            user_nicknames = {}
    except:
        user_nicknames = {}
    
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                user_stats = json.load(f)
                # Конвертируем ключи обратно в int
                user_stats = {int(k): v for k, v in user_stats.items()}
        else:
            user_stats = {}
    except:
        user_stats = {}

# Сохранение данных
def save_data():
    try:
        with open(NICKNAMES_FILE, 'w', encoding='utf-8') as f:
            # Конвертируем ключи в строки для JSON
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
temp_bot_series = {}

class TicTacToe:
    def __init__(self, game_id, player1_id, player2_id=None, mode='bot', difficulty='easy', total_games=1):
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

class NeuralNetworkBot:
    def __init__(self):
        pass
        
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

class BotPlayer:
    def __init__(self, difficulty='easy'):
        self.difficulty = difficulty
        self.neural = NeuralNetworkBot() if difficulty == 'impossible' else None
        
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
            return self.neural.get_move(game)
    
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
        
        keyboard = [
            [InlineKeyboardButton("1 игра", callback_data='bot_series_1')],
            [InlineKeyboardButton("3 игры", callback_data='bot_series_3')],
            [InlineKeyboardButton("5 игр", callback_data='bot_series_5')],
            [InlineKeyboardButton("10 игр", callback_data='bot_series_10')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_bot')]
        ]
        await query.edit_message_text(
            "🎮 Сколько игр сыграть с ботом?\n"
            "Выберите количество:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('bot_series_'):
        total_games = int(data.split('_')[2])
        difficulty = temp_bot_series[user_id]['difficulty']
        del temp_bot_series[user_id]
        
        # Создаем игру
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
        
        if total_games > 1:
            header = f"🤖 {player_nick} (❌) vs Бот (⭕)\n{game.get_score_display()}\n"
            match_info = f"⚔️ Матч 1/{total_games}\n\n"
        else:
            header = f"🤖 {player_nick} (❌) vs Бот (⭕)\n"
            match_info = ""
        
        text = match_info + header + game.get_board_display() + "\nВаш ход!"
        
        msg = await query.edit_message_text(
            text,
            reply_markup=create_game_keyboard(game_id, user_id)
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
            [InlineKeyboardButton("◀️ Назад", callback_data='menu_friend')]
        ]
        await query.edit_message_text(
            "🎮 Сколько игр сыграть?\n"
            "Выберите количество:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('create_'):
        total_games = int(data.split('_')[1])
        temp_lobby_name[user_id] = total_games
        
        await query.edit_message_text(
            f"📝 Выбрано игр: {total_games}\n\n"
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
                creator_nick = get_nickname(lobby['creator'])
                text += f"{lock} {lobby['name']}\n"
                text += f"   Создатель: {creator_nick}\n"
                text += f"   Игр: {lobby['current']}/{lobby['total']}\n"
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
            "• Выберите уровень сложности\n"
            "• Можно играть серии до 10 игр\n"
            "• Счет сохраняется между играми\n\n"
            "👥 Мультиплеер:\n"
            "• Создайте комнату\n"
            "• Отправьте ID другу\n"
            "• Оба игрока получают поле\n"
            "• После каждой игры виден счет\n"
            "• Если игрок покидает игру, вы получите уведомление\n\n"
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
        
        if game.mode == 'multiplayer' or (game.mode == 'bot' and game.total_games > 1):
            header = f"👤 {player1_nick} (❌) vs {'🤖' if game.mode == 'bot' else '👤'} {player2_nick} (⭕)\n{score_display}\n"
            if game.total_games > 1:
                header = f"⚔️ Матч {game.current_game}/{game.total_games}\n" + header
        else:
            header = f"👤 {player1_nick} (❌) vs 🤖 {player2_nick} (⭕)\n"
        
        # Проверяем результат
        if status == "win":
            user_stats[user_id]['wins'] += 1
            user_stats[user_id]['total'] += 1
            save_data()
            
            winner_nick = get_nickname(user_id)
            
            # Если мультиплеер, обновляем статистику соперника
            if game.mode == 'multiplayer' and game.player2_id:
                opponent_id = str(game.player2_id) if user_id == str(game.player1_id) else str(game.player1_id)
                if opponent_id in user_stats:
                    user_stats[opponent_id]['losses'] += 1
                    user_stats[opponent_id]['total'] += 1
                    save_data()
                
                # Обновляем счет в лобби
                for lobby in lobbies.values():
                    if lobby['game_id'] == game_id:
                        if user_id == str(game.player1_id):
                            lobby['score1'] = game.player1_score
                            lobby['score2'] = game.player2_score
                        else:
                            lobby['score1'] = game.player2_score
                            lobby['score2'] = game.player1_score
                        break
            
            # Формируем текст с победителем и счетом
            if game.mode == 'bot' and game.total_games > 1 and game.current_game < game.total_games:
                text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display()
            else:
                text = f"🎉 Победил {winner_nick}!\n\n" + header + game.get_board_display()
            
            # Завершаем игру
            game.game_over = True
            
            # Обновляем сообщения у обоих игроков
            await update_both_players(context, game, text)
            
            # Проверяем, есть ли следующая игра в серии
            await check_next_game(context, game_id)
            
        elif status == "draw":
            user_stats[user_id]['draws'] += 1
            user_stats[user_id]['total'] += 1
            save_data()
            
            # Если мультиплеер, обновляем статистику соперника
            if game.mode == 'multiplayer' and game.player2_id:
                opponent_id = str(game.player2_id) if user_id == str(game.player1_id) else str(game.player1_id)
                if opponent_id in user_stats:
                    user_stats[opponent_id]['draws'] += 1
                    user_stats[opponent_id]['total'] += 1
                    save_data()
            
            # Формируем текст с ничьей и счетом
            if game.mode == 'bot' and game.total_games > 1 and game.current_game < game.total_games:
                text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display()
            else:
                text = f"🤝 Ничья!\n\n" + header + game.get_board_display()
            
            # Завершаем игру
            game.game_over = True
            
            # Обновляем сообщения у обоих игроков
            await update_both_players(context, game, text)
            
            # Проверяем, есть ли следующая игра в серии
            await check_next_game(context, game_id)
        
        elif status == "continue":
            if game.mode == 'bot':
                # Показываем ход игрока
                text = header + game.get_board_display() + "\n🤖 Бот думает..."
                await update_both_players(context, game, text)
                
                time.sleep(1)
                
                # Ход бота
                bot = BotPlayer(game.difficulty)
                bot_move = bot.get_move(game)
                
                if bot_move is not None:
                    result, status = game.make_move(bot_move, 'bot')
                    
                    if status == "win":
                        user_stats[user_id]['losses'] += 1
                        user_stats[user_id]['total'] += 1
                        save_data()
                        
                        if game.mode == 'bot' and game.total_games > 1 and game.current_game < game.total_games:
                            text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display()
                        else:
                            text = f"😢 Бот победил!\n\n" + header + game.get_board_display()
                        
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    elif status == "draw":
                        user_stats[user_id]['draws'] += 1
                        user_stats[user_id]['total'] += 1
                        save_data()
                        
                        if game.mode == 'bot' and game.total_games > 1 and game.current_game < game.total_games:
                            text = f"✅ Матч {game.current_game} завершен!\n\n" + header + game.get_board_display()
                        else:
                            text = f"🤝 Ничья!\n\n" + header + game.get_board_display()
                        
                        await update_both_players(context, game, text)
                        await check_next_game(context, game_id)
                    
                    else:
                        text = header + game.get_board_display() + "\nВаш ход!"
                        await update_both_players(context, game, text, create_game_keyboard(game_id, game.player1_id))
            
            else:  # multiplayer
                # Определяем, чей сейчас ход
                if game.current_turn == game.player1_id:
                    turn_text = f"Ход игрока {player1_nick} (❌)"
                else:
                    turn_text = f"Ход игрока {player2_nick} (⭕)"
                
                text = header + game.get_board_display() + f"\n{turn_text}"
                
                # Обновляем у обоих игроков
                await update_both_players(context, game, text, create_game_keyboard(game_id, game.current_turn))

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
            
            # Формируем заголовок со счетом
            score_display = game.get_score_display()
            header = f"👤 {player_nick} (❌) vs 🤖 Бот (⭕)\n{score_display}\n"
            match_info = f"⚔️ Матч {game.current_game}/{game.total_games}\n\n"
            
            text = match_info + header + game.get_board_display() + "\nВаш ход!"
            
            # Обновляем сообщение
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
            # Серия завершена
            player_nick = get_nickname(game.player1_id)
            final_text = (
                f"🏁 Серия игр завершена!\n\n"
                f"Финальный счет:\n"
                f"{player_nick}: {game.player1_score}\n"
                f"Бот: {game.player2_score}\n\n"
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
                    match_info = f"⚔️ Матч {lobby['current']}/{lobby['total']}\n\n"
                    
                    if game.current_turn == lobby['creator']:
                        turn_text = f"Ход игрока {creator_nick} (❌)"
                    else:
                        turn_text = f"Ход игрока {player2_nick} (⭕)"
                    
                    text = match_info + header + game.get_board_display() + f"\n{turn_text}"
                    
                    # Обновляем сообщения у обоих игроков
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
                    # Серия завершена
                    creator_nick = get_nickname(lobby['creator'])
                    player2_nick = get_nickname(lobby['player2'])
                    
                    final_text = (
                        f"🏁 Серия игр завершена!\n\n"
                        f"Финальный счет:\n"
                        f"{creator_nick}: {lobby['score1']}\n"
                        f"{player2_nick}: {lobby['score2']}\n\n"
                        f"Чтобы сыграть снова, создайте новую комнату."
                    )
                    
                    keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data='menu_main')]]
                    
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
                    
                    # Удаляем лобби
                    del lobbies[lobby_id]
                    
                    # Очищаем игру
                    if game_id in games:
                        del games[game_id]
                    if str(lobby['creator']) in player_game:
                        del player_game[str(lobby['creator'])]
                    if str(lobby['player2']) in player_game:
                        del player_game[str(lobby['player2'])]
                
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
        total_games=lobby['total']
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
    
    score_display = game.get_score_display()
    header = f"👥 {creator_nick} (❌) vs {joiner_nick} (⭕)\n{score_display}\n"
    match_info = f"⚔️ Матч 1/{lobby['total']}\n\n"
    turn_text = f"Ход игрока {creator_nick} (❌)"
    
    text = match_info + header + game.get_board_display() + f"\n{turn_text}"
    
    # Отправляем сообщение создателю
    msg1 = await context.bot.send_message(
        lobby['creator'],
        text,
        reply_markup=create_game_keyboard(game_id, lobby['creator'])
    )
    game.player1_message_id = msg1.message_id
    game.player1_chat_id = msg1.chat_id
    
    # Отправляем сообщение подключившемуся
    msg2 = await context.bot.send_message(
        user_id,
        text,
        reply_markup=create_game_keyboard(game_id, lobby['creator'])
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
            f"🎮 Игр: {total_games}\n\n"
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
        
        await update.message.reply_text(
            f"✅ Комната создана!\n\n"
            f"🏷 Название: {data['name']}\n"
            f"🆔 ID: {lobby_id}\n"
            f"🎮 Серия: {data['total']} игр\n"
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
    """Создает клавиатуру для игры"""
    game = games.get(game_id)
    if not game:
        return None
    
    keyboard = []
    row = []
    
    for i in range(9):
        # Кнопка активна только для текущего игрока и если клетка свободна
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
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("✅ Бот успешно запущен!")
    print("👉 Отправьте /start в Telegram")
    
    app.run_polling()

if __name__ == '__main__':
    main()