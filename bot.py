import asyncio
import logging
import random
import re
import time
import sqlite3
import json
import aiohttp
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
from typing import Optional, Dict, List, Tuple

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, GROUP_LINK, ADMIN_IDS, GROUP_ID
from database import (
    DB_PATH, init_db, get_user, create_user, update_user_team, user_has_team,
    get_team, get_all_teams, create_team, update_team, delete_team,
    get_fft_players, add_fft_player, remove_fft_player, get_fft_player,
    get_balance_topic_data, set_balance_topic_data, get_hltv_topic_data,
    set_hltv_topic_data, get_vrs_topic_data, set_vrs_topic_data,
    get_fft_topic_data, set_fft_topic_data, update_balance, get_balance,
    add_achievement, get_team_achievements, update_vrs_points,
    get_all_vrs_standings, update_team_winrate, add_player_to_team,
    remove_player_from_team, get_player_by_name, update_player_rating,
    update_player_role, update_player_nickname, add_transfer_history,
    add_trade_history, get_team_players_by_status, set_player_status,
    update_hltv_profile, create_hltv_profile_if_not_exists,
    add_hltv_match_history, update_team_coach, get_hltv_player_stats,
    update_hltv_player_stats, is_moderator, get_hltv_profile, get_all_users, save_hltv_message, get_hltv_message_id, get_hltv_topic_id, update_hltv_player_team
)
from utils import (
    generate_random_players, generate_random_coach, generate_random_winrates,
    simulate_match, calculate_rating_change_training, calculate_training_gains,
    calculate_individual_training_gain, get_winrate_percent, format_roster,
    format_balance_message, format_vrs_message, format_fft_list_message,
    format_hltv_profile, calculate_vrs_points, get_random_map_pool, get_map_pool
)
from states import (
    CreateTeam, TransferWait, TradeWait, ChangeRoleWait, SwapPlayerWait, AdminAddPlayerWait
)

router = Router()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

pending_transfers = {}
pending_trades = {}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[HEALTH] Health check server running on port {port}")
    server.serve_forever()

health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()
print("[HEALTH] Health check server thread started")

@router.message(F.chat.type == "private")
async def private_messages(message: Message):
    if message.text and message.text.startswith("/start"):
        await message.answer(f"<b>Бот работает только в группе владельца — {GROUP_LINK}</b>", parse_mode="HTML")

@router.message(Command("create_team"), F.chat.id == GROUP_ID)
async def cmd_create_team(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if user_has_team(user_id):
        await message.answer("<b>Вы уже создали свою команду, не пытайтесь обойти меня пжэ</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /create_team название команды</b>", parse_mode="HTML")
        return
    
    team_name = command.args.strip()
    
    if get_team(team_name):
        await message.answer(f"<b>Команда с названием '{team_name}' уже существует</b>", parse_mode="HTML")
        return
    
    players = generate_random_players()
    coach = generate_random_coach()
    winrates = generate_random_winrates()
    
    create_team(
        team_name=team_name,
        coach_name=coach["name"],
        coach_rating=coach["rating"],
        players=players,
        winrates=winrates,
        potential=100.0,
        synergy=100.0,
        happiness=100.0,
        spirit=100.0,
        atmosphere=100.0
    )
    
    if not get_user(user_id):
        create_user(user_id, username, team_name)
    else:
        update_user_team(user_id, team_name)
    
    await message.answer(f"<b>Вы успешно создали команду «{team_name}», теперь вы - владелец. Больше команду вы не сможете создать.</b>", parse_mode="HTML")

@router.message(Command("roster"), F.chat.id == GROUP_ID)
async def cmd_roster(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    text = message.text
    parts = text.split(maxsplit=1)
    
    if len(parts) > 1:
        team_name_query = parts[1]
        team_name = team_name_query.replace(".", " ")
        team = get_team(team_name)
        if not team:
            await message.answer(f"<b>Команда '{team_name}' не найдена</b>", parse_mode="HTML")
            return
        await message.answer(format_roster(team), parse_mode="HTML")
        return

    if not user or not user["main_team"]:
        await message.answer("<b>У вас нет команды. Создайте её через /create_team</b>", parse_mode="HTML")
        return
    
    team = get_team(user["main_team"])
    if not team:
        await message.answer("<b>Команда не найдена</b>", parse_mode="HTML")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить роль игрока", callback_data="change_role")],
        [InlineKeyboardButton(text="Переместить в запас/основу", callback_data="change_lineup")]
    ])
    
    await message.answer(format_roster(team), reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "change_role")
async def change_role_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await callback.answer("У вас нет команды", show_alert=True)
        return
    
    team = get_team(user["main_team"])
    if not team:
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    players = [p for p in team["players"] if p.get("status") == "main"]
    
    buttons = []
    for p in players:
        buttons.append([InlineKeyboardButton(text=p["name"], callback_data=f"role_player:{p['name']}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="roster_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("<b>Выберите игрока для смены роли:</b>", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChangeRoleWait.waiting_for_player)
    await callback.answer()

@router.callback_query(F.data.startswith("role_player:"))
async def change_role_select_player(callback: CallbackQuery, state: FSMContext):
    player_name = callback.data.split(":", 1)[1]
    await state.update_data(player_name=player_name)
    
    roles = ["IGL", "Rifler", "AWP", "Support", "Entry Fragger", "Lurker"]
    buttons = []
    for role in roles:
        buttons.append([InlineKeyboardButton(text=role, callback_data=f"set_role:{role}")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="change_role")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(f"<b>Выберите новую роль для {player_name}:</b>", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChangeRoleWait.waiting_for_role)
    await callback.answer()

@router.callback_query(F.data.startswith("set_role:"))
async def change_role_set(callback: CallbackQuery, state: FSMContext):
    new_role = callback.data.split(":", 1)[1]
    data = await state.get_data()
    player_name = data.get("player_name")
    
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await callback.answer("У вас нет команды", show_alert=True)
        return
    
    team = get_team(user["main_team"])
    if not team:
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    player = None
    for p in team["players"]:
        if p["name"] == player_name:
            player = p
            break
    
    if not player:
        await callback.answer("Игрок не найден", show_alert=True)
        return
    
    players = team["players"].copy()
    for i, p in enumerate(players):
        if p["name"] == player_name:
            players[i]["role"] = new_role
            break
    
    new_synergy = max(0, team["synergy"] - 0.80)
    update_team(team["team_name"], players=players, synergy=new_synergy)

    team = get_team(user["main_team"])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить роль игрока", callback_data="change_role")],
        [InlineKeyboardButton(text="Переместить в запас/основу", callback_data="change_lineup")]
    ])
    
    await callback.message.edit_text(format_roster(team), parse_mode="HTML")
    await callback.answer(f"Роль {player_name} изменена на {new_role}, сыгранность -0.80%")
    await state.clear()

@router.callback_query(F.data == "change_lineup")
async def change_lineup_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await callback.answer("У вас нет команды", show_alert=True)
        return
    
    team = get_team(user["main_team"])
    if not team:
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    main_players = [p for p in team["players"] if p.get("status") == "main"]
    reserve_players = [p for p in team["players"] if p.get("status") == "reserve"]
    
    buttons = []
    if reserve_players:
        buttons.append([InlineKeyboardButton(text="Из резерва в основу", callback_data="swap_to_main")])
    if main_players:
        buttons.append([InlineKeyboardButton(text="Из основы в резерв", callback_data="swap_to_reserve")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="roster_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("<b>Выберите действие:</b>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "swap_to_main")
async def swap_to_main_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    team = get_team(user["main_team"])
    
    reserve_players = [p for p in team["players"] if p.get("status") == "reserve"]
    
    buttons = []
    for p in reserve_players:
        buttons.append([InlineKeyboardButton(text=p["name"], callback_data=f"swap_main:{p['name']}")])
    buttons.append([InlineKeyboardButton(text="◀Назад", callback_data="change_lineup")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("<b>Выберите игрока из резерва:</b>", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(SwapPlayerWait.waiting_for_player)
    await callback.answer()

@router.callback_query(F.data == "swap_to_reserve")
async def swap_to_reserve_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    team = get_team(user["main_team"])
    
    main_players = [p for p in team["players"] if p.get("status") == "main"]
    
    buttons = []
    for p in main_players:
        buttons.append([InlineKeyboardButton(text=p["name"], callback_data=f"swap_reserve:{p['name']}")])
    buttons.append([InlineKeyboardButton(text="◀Назад", callback_data="change_lineup")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("<b>Выберите игрока из основы:</b>", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(SwapPlayerWait.waiting_for_player)
    await callback.answer()

@router.callback_query(F.data.startswith("swap_main:"))
async def swap_main_execute(callback: CallbackQuery, state: FSMContext):
    player_name = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    user = get_user(user_id)
    team = get_team(user["main_team"])

    player = None
    for p in team["players"]:
        if p["name"] == player_name and p.get("status") == "reserve":
            player = p
            break
    
    if not player:
        await callback.answer("Игрок не найден в резерве", show_alert=True)
        return

    main_players = [p for p in team["players"] if p.get("status") == "main"]
    if len(main_players) >= 5:
        to_swap = min(main_players, key=lambda x: x["rating"])
        
        players = team["players"].copy()
        for i, p in enumerate(players):
            if p["name"] == player_name:
                players[i]["status"] = "main"
            elif p["name"] == to_swap["name"]:
                players[i]["status"] = "reserve"
        
        new_synergy = max(0, team["synergy"] - 0.10)
        new_happiness = max(0, team["happiness"] - 0.15)
        new_atmosphere = max(0, team["atmosphere"] - 0.05)
        
        update_team(team["team_name"], players=players, synergy=new_synergy, happiness=new_happiness, atmosphere=new_atmosphere)
        
        await callback.message.edit_text(format_roster(team), parse_mode="HTML")
        await callback.answer(f"{player_name} перемещён в основу вместо {to_swap['name']}")
    else:
        players = team["players"].copy()
        for i, p in enumerate(players):
            if p["name"] == player_name:
                players[i]["status"] = "main"
                break
        
        update_team(team["team_name"], players=players)
        team = get_team(user["main_team"])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
           [InlineKeyboardButton(text="Изменить роль игрока", callback_data="change_role")],
           [InlineKeyboardButton(text="Переместить в запас/основу", callback_data="change_lineup")]
        ])
        await callback.message.edit_text(format_roster(team), parse_mode="HTML")
        await callback.answer(f"{player_name} перемещён в основу")
    
    await state.clear()

@router.callback_query(F.data.startswith("swap_reserve:"))
async def swap_reserve_execute(callback: CallbackQuery, state: FSMContext):
    player_name = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    user = get_user(user_id)
    team = get_team(user["main_team"])
    
    player = None
    for p in team["players"]:
        if p["name"] == player_name and p.get("status") == "main":
            player = p
            break
    
    if not player:
        await callback.answer("Игрок не найден в основе", show_alert=True)
        return
    
    players = team["players"].copy()
    for i, p in enumerate(players):
        if p["name"] == player_name:
            players[i]["status"] = "reserve"
            break
    
    new_synergy = max(0, team["synergy"] - 0.10)
    new_happiness = max(0, team["happiness"] - 0.15)
    new_atmosphere = max(0, team["atmosphere"] - 0.05)
    
    team = get_team(user["main_team"])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить роль игрока", callback_data="change_role")],
        [InlineKeyboardButton(text="Переместить в запас/основу", callback_data="change_lineup")]
    ])
    
    await callback.message.edit_text(format_roster(team), parse_mode="HTML")
    await callback.answer(f"{player_name} перемещён в запас")
    await state.clear()

@router.callback_query(F.data == "roster_back")
async def roster_back(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await callback.answer("У вас нет команды", show_alert=True)
        return
    
    team = get_team(user["main_team"])
    if not team:
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить роль игрока", callback_data="change_role")],
        [InlineKeyboardButton(text="Переместить в запас/основу", callback_data="change_lineup")]
    ])
    
    await callback.message.edit_text(format_roster(team), reply_markup=keyboard, parse_mode="HTML")
    await state.clear()
    await callback.answer()

@router.message(Command("training"), F.chat.id == GROUP_ID)
async def cmd_training(message: Message, command: CommandObject):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await message.answer("<b>У вас нет команды. Создайте её через /create_team</b>", parse_mode="HTML")
        return
    
    team = get_team(user["main_team"])
    if not team:
        await message.answer("<b>Команда не найдена</b>", parse_mode="HTML")
        return

    if command.args:
        player_name = command.args.strip()
        player = None
        for p in team["players"]:
            if p["name"].lower() == player_name.lower():
                player = p
                break
        
        if not player:
            await message.answer(f"<b>Игрок {player_name} не найден в вашей команде</b>", parse_mode="HTML")
            return
        
        now = time.time()
        if user.get("last_individual") and now - user["last_individual"] < 10800:
            remaining = 10800 - (now - user["last_individual"])
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await message.answer(f"<b>До следующей тренировки игрока осталось {hours} ч {minutes} мин</b>", parse_mode="HTML")
            return
        
        gain = calculate_individual_training_gain()
        old_rating = player["rating"]
        new_rating = min(100.0, old_rating + gain)
        
        players = team["players"].copy()
        for i, p in enumerate(players):
            if p["name"] == player["name"]:
                players[i]["rating"] = new_rating
                break
        
        potential_gain = random.uniform(0.10, 0.15)
        new_potential = min(100.0, team["potential"] + potential_gain)
        
        update_team(team["team_name"], players=players, potential=new_potential)
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE users SET last_individual = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"<b>Вы потренировали игрока {player_name}!\n\n"
            f"{player_name} [{old_rating:.2f}] >> [{new_rating:.2f}] +{gain:.2f}\n\n"
            f"Потенциал команды: +{potential_gain:.2f}%\n\n"
            f"Следующую тренировку игрока вы сможете провести через 3 часа.</b>",
            parse_mode="HTML"
        )
        return
    
    now = time.time()
    if user.get("last_training") and now - user["last_training"] < 7200:
        remaining = 7200 - (now - user["last_training"])
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await message.answer(f"<b>Вы не можете тренировать команду, так как тренировали ее недавно. До тренировки осталось {hours} ч {minutes} мин</b>", parse_mode="HTML")
        return
    
    changes = []
    players = team["players"].copy()
    coach_rating = team["coach_rating"]
    
    gains = calculate_training_gains()
    
    for i, player in enumerate(players):
        gain = gains["player"]
        old_rating = player["rating"]
        new_rating = min(100.0, old_rating + gain)
        players[i]["rating"] = new_rating
        changes.append({"name": player["name"], "old": old_rating, "new": new_rating, "gain": gain})
    
    coach_gain = gains["player"]
    old_coach = coach_rating
    new_coach = min(100.0, old_coach + coach_gain)
    changes.append({"name": "Тренер", "old": old_coach, "new": new_coach, "gain": coach_gain})
    
    new_synergy = min(100.0, team["synergy"] + gains["synergy"])
    new_potential = min(100.0, team["potential"] + gains["potential"])
    new_happiness = min(100.0, team["happiness"] + gains["happiness"])
    
    update_team(
        team["team_name"],
        players=players,
        coach_rating=new_coach,
        synergy=new_synergy,
        potential=new_potential,
        happiness=new_happiness
    )
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_training = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()
    
    msg_lines = [f"<b>Тренировка состава {team['team_name']}</b>"]
    for ch in changes:
        msg_lines.append(f"<b>{ch['name']} [{ch['old']:.2f}] >> [{ch['new']:.2f}] +{ch['gain']:.2f}</b>")
    msg_lines.append("")
    msg_lines.append(f"<b>Дух игроков: 100% +0%</b>")
    msg_lines.append(f"<b>Потенциал: 100% +{gains['potential']:.2f}%</b>")
    msg_lines.append(f"<b>Сыгранность: 100% +{gains['synergy']:.2f}%</b>")
    msg_lines.append(f"<b>Счастье: 100% +{gains['happiness']:.2f}%</b>")
    msg_lines.append(f"<b>Атмосфера: 100% +0%</b>")
    
    await message.answer("\n".join(msg_lines), parse_mode="HTML")

@router.message(Command("match"), F.chat.id == GROUP_ID)
async def cmd_match(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("<b>Использование: /match bo1 Team.Spirit MountHero\nФорматы: bo1, bo2, bo3, bo5</b>", parse_mode="HTML")
        return
    
    args = command.args.split()
    if len(args) != 3:
        await message.answer("<b>Неверный формат. Пример: /match bo1 Team.Spirit MountHero</b>", parse_mode="HTML")
        return
    
    bo_format = args[0].lower()
    team1_name = args[1].replace(".", " ")
    team2_name = args[2].replace(".", " ")
    
    valid_formats = ["bo1", "bo2", "bo3", "bo5"]
    if bo_format not in valid_formats:
        await message.answer("<b>Неверный формат. Доступно: bo1, bo2, bo3, bo5</b>", parse_mode="HTML")
        return
    
    team1 = get_team(team1_name)
    team2 = get_team(team2_name)
    
    if not team1:
        await message.answer(f"<b>Команда '{team1_name}' не найдена</b>", parse_mode="HTML")
        return
    if not team2:
        await message.answer(f"<b>Команда '{team2_name}' не найдена</b>", parse_mode="HTML")
        return
    
    maps_count = int(bo_format[2])
    result = simulate_match(team1, team2, maps_count)
    
    msg_lines = [f"<b>Матч {team1['team_name']} vs {team2['team_name']}</b>"]
    msg_lines.append(f"<b>Формат матча: {bo_format.upper()}</b>")
    msg_lines.append("")
    msg_lines.append("<b>Сыгранные карты:</b>")
    
    for map_result in result["map_results"]:
        msg_lines.append(f"<b>{map_result['map']} • {map_result['winner']} {map_result['score_winner']}-{map_result['score_loser']}</b>")

    msg_lines.append("")
    msg_lines.append(f"<b>Итог матча: {team1['team_name']} {result['score_team1']}-{result['score_team2']} {team2['team_name']}</b>")
    
    msg_lines.append("")
    msg_lines.append("<b>Статистика игроков:</b>")
    msg_lines.append("<b>Nick l K l D l A l K/D l ADR l Rating 3.0</b>")
    msg_lines.append("")
    
    for team_name, stats in result["players_stats"].items():
        msg_lines.append(f"<b>{team_name}</b>")
        for stat in stats:
            msg_lines.append(f"<b>{stat['name']} l {stat['kills']} l {stat['deaths']} l {stat['assists']} l {stat['kd']:.2f} l {stat['adr']:.1f} l {stat['rating']:.2f}</b>")
        msg_lines.append("")
    
    msg_lines.append(f"<b>MVP матча: {result['mvp']}</b>")
    msg_lines.append(f"<b>EVP матча: {result['evp']}</b>")
    
    await message.answer("\n".join(msg_lines), parse_mode="HTML")

@router.message(Command("tour"), F.chat.id == GROUP_ID)
async def cmd_tour(message: Message, command: CommandObject, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>У вас нет прав</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /tour bo3 Team.Falcons MountHero</b>", parse_mode="HTML")
        return
    
    args = command.args.split()
    if len(args) != 3:
        await message.answer("<b>Неверный формат. Пример: /tour bo3 Team.Falcons MountHero</b>", parse_mode="HTML")
        return
    
    bo_format = args[0].lower()
    team1_name = args[1].replace(".", " ")
    team2_name = args[2].replace(".", " ")
    
    team1 = get_team(team1_name)
    team2 = get_team(team2_name)
    
    if not team1 or not team2:
        await message.answer("<b>Одна из команд не найдена</b>", parse_mode="HTML")
        return
    
    maps_count = int(bo_format[2])
    result = simulate_match(team1, team2, maps_count, is_tour=True)
    
    for map_result in result["map_results"]:
        update_team_winrate(map_result["winner"], map_result["map"], "win")
        loser = team1_name if map_result["winner"] != team1_name else team2_name
        update_team_winrate(loser, map_result["map"], "lose")
    
    vrs_points = calculate_vrs_points(result["score_team1"], result["score_team2"], maps_count)
    update_vrs_points(team1_name, vrs_points["team1_points"], 1 if result["winner_team"] == team1_name else 0, 1 if result["winner_team"] == team2_name else 0)
    update_vrs_points(team2_name, vrs_points["team2_points"], 1 if result["winner_team"] == team2_name else 0, 1 if result["winner_team"] == team1_name else 0)
    
    await update_hltv_profiles_after_match(bot, team1, team2, result, message.chat.id)
    await update_vrs_topic(bot, message.chat.id)
    
    msg_lines = [f"<b>Матч {team1_name} vs {team2_name}</b>"]
    msg_lines.append(f"<b>Формат матча: {bo_format.upper()}</b>")
    msg_lines.append("")
    msg_lines.append("<b>Сыгранные карты:</b>")
    
    for map_result in result["map_results"]:
        msg_lines.append(f"<b>{map_result['map']} • {map_result['winner']} {map_result['score_winner']}-{map_result['score_loser']}</b>")
    
    msg_lines.append("")
    msg_lines.append(f"<b>Итог матча: {team1_name} {result['score_team1']}-{result['score_team2']} {team2_name}</b>")
    
    msg_lines.append("")
    msg_lines.append("<b>Статистика игроков:</b>")
    msg_lines.append("<b>Nick l K l D l A l K/D l ADR l Rating 3.0</b>")
    msg_lines.append("")
    
    for team_name, stats in result["players_stats"].items():
        msg_lines.append(f"<b>{team_name}</b>")
        for stat in stats:
            msg_lines.append(f"<b>{stat['name']} l {stat['kills']} l {stat['deaths']} l {stat['assists']} l {stat['kd']:.2f} l {stat['adr']:.1f} l {stat['rating']:.2f}</b>")
        msg_lines.append("")
    
    msg_lines.append(f"<b>MVP матча: {result['mvp']}</b>")
    msg_lines.append(f"<b>EVP матча: {result['evp']}</b>")
    
    await message.answer("\n".join(msg_lines), parse_mode="HTML")

@router.message(Command("fft"), F.chat.id == GROUP_ID)
async def cmd_fft(message: Message, command: CommandObject, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /fft ник рейтинг роль</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=2)
    if len(args) != 3:
        await message.answer("<b>Использование: /fft jame 50.27 AWP</b>", parse_mode="HTML")
        return
    
    name, rating_str, role = args
    try:
        rating = float(rating_str)
    except:
        await message.answer("<b>Рейтинг должен быть числом</b>", parse_mode="HTML")
        return
    
    add_fft_player(name, rating, role)
    await update_fft_topic(bot, message.chat.id)
    await message.answer(f"<b>Игрок {name} [{rating}] • {role} добавлен в FFT-лист</b>", parse_mode="HTML")

@router.message(Command("fftm"), F.chat.id == GROUP_ID)
async def cmd_fftm(message: Message, command: CommandObject, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /fftm ник рейтинг роль цена</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=3)
    if len(args) != 4:
        await message.answer("<b>Использование: /fftm jame 50.27 AWP 30000</b>", parse_mode="HTML")
        return
    
    name, rating_str, role, price_str = args
    try:
        rating = float(rating_str)
        price = int(price_str)
    except:
        await message.answer("<b>Рейтинг должен быть числом, цена целым числом</b>", parse_mode="HTML")
        return
    
    add_fft_player(name, rating, role)
    await update_fft_topic(bot, message.chat.id)
    await message.answer(f"<b>Игрок {name} [{rating}] • {role} добавлен в FFT-лист с ценой {price}$</b>", parse_mode="HTML")

@router.message(Command("ahfft"), F.chat.id == GROUP_ID)
async def cmd_ahfft(message: Message, command: CommandObject, bot: Bot):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await message.answer("<b>У вас нет команды</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /ahfft ник</b>", parse_mode="HTML")
        return
    
    player_name = command.args.strip()
    
    # Проверяем, тренер это или игрок
    is_coach = player_name.lower().startswith("coach ")
    if is_coach:
        player_name = player_name[6:].strip()  # убираем "coach "
    
    fft_player = get_fft_player(player_name)
    
    if not fft_player:
        await message.answer(f"<b>Игрок/тренер {player_name} не найден в FFT-листе</b>", parse_mode="HTML")
        return
    
    # Проверяем, что роль соответствует (если тренер - роль должна быть Coach)
    if is_coach and fft_player.get("role") != "Coach":
        await message.answer(f"<b>{player_name} не является тренером</b>", parse_mode="HTML")
        return
    
    if not is_coach and fft_player.get("role") == "Coach":
        await message.answer(f"<b>Чтобы взять тренера, используйте /ahfft coach {player_name}</b>", parse_mode="HTML")
        return

    price = fft_player.get("price", 0)
    if price > 0:
        if user["balance"] < price:
            await message.answer(f"<b>У вас недостаточно средств. Нужно {price}$</b>", parse_mode="HTML")
            return
        update_balance(user_id, user["balance"] - price)
    
    team = get_team(user["main_team"])
    
    if is_coach:
        # Добавляем тренера
        update_team(team["team_name"], coach_name=fft_player["name"], coach_rating=fft_player["rating"])
        await message.answer(f"<b>Вы успешно взяли нового тренера {fft_player['name']} [{fft_player['rating']}] в команду {team['team_name']} из FFT.</b>", parse_mode="HTML")
    else:
        # Добавляем игрока
        players = team["players"].copy()
        new_player = {
            "name": fft_player["name"],
            "rating": fft_player["rating"],
            "role": fft_player["role"],
            "status": "main" if len([p for p in players if p.get("status") == "main"]) < 5 else "reserve"
        }
        players.append(new_player)
        update_team(team["team_name"], players=players)
        await message.answer(f"<b>Вы успешно взяли нового игрока {fft_player['name']} [{fft_player['rating']}] • {fft_player['role']} к себе в команду из FFT.</b>", parse_mode="HTML")
    
    remove_fft_player(fft_player["name"])
    await update_fft_topic(bot, message.chat.id)

@router.message(Command("achiev"), F.chat.id == GROUP_ID)
async def cmd_achiev(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /achiev команда турнир место</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=2)
    if len(args) != 3:
        await message.answer("<b>Использование: /achiev MountHero IEM.Major.2026 1</b>", parse_mode="HTML")
        return
    
    team_name = args[0].replace(".", " ")
    tournament = args[1].replace(".", " ")
    try:
        place = int(args[2])
    except:
        await message.answer("<b>Место должно быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    add_achievement(team_name, tournament, place)
    await message.answer(f"<b>Достижение добавлено: {team_name} - {tournament} - {place} место</b>", parse_mode="HTML")


@router.message(Command("transfer"), F.chat.id == GROUP_ID)
async def cmd_transfer(message: Message, command: CommandObject):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await message.answer("<b>У вас нет команды</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /transfer ник/тренер команда цена</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=2)
    if len(args) != 3:
        await message.answer("<b>Использование: /transfer m0NESY Team.Spirit 320000\nИли: /transfer coach xander Team.Spirit 50000</b>", parse_mode="HTML")
        return
    
    player_name, target_team_name, price_str = args
    target_team_name = target_team_name.replace(".", " ")
    
    try:
        price = int(price_str)
    except:
        await message.answer("<b>Цена должна быть числом</b>", parse_mode="HTML")
        return
    
    from_team = get_team(user["main_team"])
    to_team = get_team(target_team_name)
    
    if not to_team:
        await message.answer(f"<b>Команда {target_team_name} не найдена</b>", parse_mode="HTML")
        return

    is_coach = player_name.lower().startswith("coach ")
    if is_coach:
        coach_name = player_name[6:].strip()
        if from_team.get("coach_name") != coach_name:
            await message.answer(f"<b>Тренер {coach_name} не найден в вашей команде</b>", parse_mode="HTML")
            return
        player_data = {"name": coach_name, "rating": from_team["coach_rating"], "role": "Coach", "is_coach": True}
    else:
        player = None
        for p in from_team["players"]:
            if p["name"].lower() == player_name.lower():
                player = p
                break
        if not player:
            await message.answer(f"<b>Игрок {player_name} не найден в вашей команде</b>", parse_mode="HTML")
            return
        player_data = player.copy()
        player_data["is_coach"] = False
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM users WHERE main_team = ?", (target_team_name,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await message.answer(f"<b>У команды {target_team_name} нет владельца</b>", parse_mode="HTML")
        return
    
    target_user_id = row[0]
    target_username = row[1] if row[1] else str(target_user_id)
    transfer_id = f"{user_id}_{target_user_id}_{int(time.time())}"
    
    pending_transfers[transfer_id] = {
        "from_user": user_id,
        "to_user": target_user_id,
        "player": player_data,
        "price": price,
        "from_team": from_team["team_name"],
        "to_team": to_team["team_name"],
        "is_coach": is_coach
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ДА", callback_data=f"transfer_yes:{transfer_id}"),
         InlineKeyboardButton(text="НЕТ", callback_data=f"transfer_no:{transfer_id}")]
    ])
    
    player_type = "тренера" if is_coach else "игрока"
    await message.answer(
        f"<b>@{target_username}, вам предложили {player_type} {player_data['name']} за {price}$. Вы согласны?</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(Command("trade"), F.chat.id == GROUP_ID)
async def cmd_trade(message: Message, command: CommandObject):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await message.answer("<b>У вас нет команды</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /trade игрок1 игрок2</b>", parse_mode="HTML")
        return
    
    args = command.args.split()
    if len(args) != 2:
        await message.answer("<b>Использование: /trade sAw m0NESY</b>", parse_mode="HTML")
        return
    
    my_player_name = args[0]
    target_player_name = args[1]
    
    my_team = get_team(user["main_team"])
    
    my_player = None
    for p in my_team["players"]:
        if p["name"].lower() == my_player_name.lower():
            my_player = p
            break
    
    if not my_player:
        await message.answer(f"<b>Игрок {my_player_name} не найден в вашей команде</b>", parse_mode="HTML")
        return
    
    target_player = None
    target_team = None
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name, players FROM teams")
    rows = cur.fetchall()
    for team_name, players_json in rows:
        players = json.loads(players_json)
        for p in players:
            if p["name"].lower() == target_player_name.lower():
                target_player = p
                target_team = team_name
                break
        if target_player:
            break
    conn.close()
    
    if not target_player:
        await message.answer(f"<b>Игрок {target_player_name} не найден</b>", parse_mode="HTML")
        return
    
    if target_team == my_team["team_name"]:
        await message.answer("<b>Нельзя обменяться игроком сам с собой</b>", parse_mode="HTML")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM users WHERE main_team = ?", (target_team,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await message.answer(f"<b>У команды {target_team} нет владельца</b>", parse_mode="HTML")
        return
    
    target_user_id = row[0]
    target_username = row[1] if row[1] else str(target_user_id)
    trade_id = f"{user_id}_{target_user_id}_{int(time.time())}"
    
    pending_trades[trade_id] = {
        "from_user": user_id,
        "to_user": target_user_id,
        "from_player": my_player.copy(),
        "to_player": target_player.copy(),
        "from_team": my_team["team_name"],
        "to_team": target_team
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ДА", callback_data=f"trade_yes:{trade_id}"),
         InlineKeyboardButton(text="НЕТ", callback_data=f"trade_no:{trade_id}")]
    ])
    
    await message.answer(
        f"<b>@{target_username}, вам предложили обмен! Вы отдаете своего игрока {target_player['name']}, а вам отдают игрока {my_player['name']}, согласны?</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(Command("addplayer"), F.chat.id == GROUP_ID)
async def cmd_addplayer(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /addplayer ник рейтинг роль команда</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=3)
    if len(args) != 4:
        await message.answer("<b>Использование: /addplayer holly 17.38 Lurker Team.Falcons</b>", parse_mode="HTML")
        return
    
    name, rating_str, role, team_name = args
    team_name = team_name.replace(".", " ")
    
    try:
        rating = float(rating_str)
    except:
        await message.answer("<b>Рейтинг должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    players = team["players"].copy()
    main_count = len([p for p in players if p.get("status") == "main"])
    status = "main" if main_count < 5 else "reserve"
    
    players.append({
        "name": name,
        "rating": rating,
        "role": role,
        "status": status
    })
    
    update_team(team_name, players=players)
    await message.answer(f"<b>Игрок {name} [{rating}] • {role} добавлен в команду {team_name} ({status})</b>", parse_mode="HTML")

@router.message(Command("addteam"), F.chat.id == GROUP_ID)
async def cmd_addteam(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /addteam название</b>", parse_mode="HTML")
        return
    
    team_name = command.args.strip()
    
    if get_team(team_name):
        await message.answer(f"<b>Команда {team_name} уже существует</b>", parse_mode="HTML")
        return
    
    players = generate_random_players()
    coach = generate_random_coach()
    winrates = generate_random_winrates()
    
    create_team(
        team_name=team_name,
        coach_name=coach["name"],
        coach_rating=coach["rating"],
        players=players,
        winrates=winrates,
        potential=100.0,
        synergy=100.0,
        happiness=100.0,
        spirit=100.0,
        atmosphere=100.0
    )
    
    await message.answer(f"<b>Команда {team_name} создана</b>", parse_mode="HTML")

@router.message(Command("editn"), F.chat.id == GROUP_ID)
async def cmd_editn(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /editn старый_ник новый_ник</b>", parse_mode="HTML")
        return
    
    args = command.args.split()
    if len(args) != 2:
        await message.answer("<b>Использование: /editn m0NESY hilo</b>", parse_mode="HTML")
        return
    
    old_name, new_name = args
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name, players FROM teams")
    rows = cur.fetchall()
    
    found = False
    for team_name, players_json in rows:
        players = json.loads(players_json)
        for i, p in enumerate(players):
            if p["name"].lower() == old_name.lower():
                players[i]["name"] = new_name
                cur.execute("UPDATE teams SET players = ? WHERE team_name = ?", (json.dumps(players), team_name))
                found = True
                break
        if found:
            break
    
    cur.execute("SELECT * FROM fft_players WHERE name = ?", (old_name,))
    if cur.fetchone():
        cur.execute("UPDATE fft_players SET name = ? WHERE name = ?", (new_name, old_name))
        found = True
    
    cur.execute("UPDATE hltv_profiles SET name = ? WHERE name = ?", (new_name, old_name))
    
    conn.commit()
    conn.close()
    
    if found:
        await message.answer(f"<b>Ник {old_name} изменен на {new_name}</b>", parse_mode="HTML")
    else:
        await message.answer(f"<b>Игрок {old_name} не найден</b>", parse_mode="HTML")

@router.message(Command("addmod"), F.chat.id == GROUP_ID)
async def cmd_addmod(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /addmod юзернейм/айди</b>", parse_mode="HTML")
        return
    
    identifier = command.args.strip()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO moderators (user_id) VALUES (?)", (identifier,))
    conn.commit()
    conn.close()
    
    await message.answer(f"<b>Пользователь {identifier} добавлен в модераторы</b>", parse_mode="HTML")

@router.message(Command("remmod"), F.chat.id == GROUP_ID)
async def cmd_remmod(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /remmod юзернейм/айди</b>", parse_mode="HTML")
        return
    
    identifier = command.args.strip()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM moderators WHERE user_id = ?", (identifier,))
    conn.commit()
    conn.close()
    
    await message.answer(f"<b>Пользователь {identifier} удален из модераторов</b>", parse_mode="HTML")

@router.message(Command("addmoney"), F.chat.id == GROUP_ID)
async def cmd_addmoney(message: Message, command: CommandObject, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not command.args:
        await message.answer("<b>Использование: /addmoney команда сумма</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("<b>Использование: /addmoney FURIA 360000</b>", parse_mode="HTML")
        return
    
    team_name = args[0].replace(".", " ")
    try:
        amount = int(args[1])
    except:
        await message.answer("<b>Сумма должна быть числом</b>", parse_mode="HTML")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, balance FROM users WHERE main_team = ?", (team_name,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await message.answer(f"<b>Команда {team_name} не найдена или у неё нет владельца</b>", parse_mode="HTML")
        return
    
    user_id, current_balance = row
    update_balance(user_id, current_balance + amount)
    
    await update_balance_topic(bot, message.chat.id)
    await message.answer(f"<b>Баланс команды {team_name} пополнен на {amount}$</b>", parse_mode="HTML")

@router.message(Command("addpot"), F.chat.id == GROUP_ID)
async def cmd_addpot(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("<b>Использование: /addpot команда процент</b>", parse_mode="HTML")
        return
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("<b>Использование: /addpot Team.Falcons 89%</b>", parse_mode="HTML")
        return
    team_name = args[0].replace(".", " ")
    percent_str = args[1].replace("%", "")
    try:
        percent = float(percent_str)
    except:
        await message.answer("<b>Процент должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    new_potential = min(100.0, team["potential"] + percent)
    update_team(team_name, potential=new_potential)
    await message.answer(f"<b>Потенциал команды {team_name} изменен на {new_potential}%</b>", parse_mode="HTML")

@router.message(Command("addche"), F.chat.id == GROUP_ID)
async def cmd_addche(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("<b>Использование: /addche команда процент</b>", parse_mode="HTML")
        return
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("<b>Использование: /addche MountHero 40%</b>", parse_mode="HTML")
        return
    team_name = args[0].replace(".", " ")
    percent_str = args[1].replace("%", "")
    try:
        percent = float(percent_str)
    except:
        await message.answer("<b>Процент должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    new_synergy = min(100.0, team["synergy"] + percent)
    update_team(team_name, synergy=new_synergy)
    await message.answer(f"<b>Сыгранность команды {team_name} изменена на {new_synergy}%</b>", parse_mode="HTML")

@router.message(Command("addhap"), F.chat.id == GROUP_ID)
async def cmd_addhap(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("<b>Использование: /addhap команда процент</b>", parse_mode="HTML")
        return
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("<b>Использование: /addhap FURIA 100%</b>", parse_mode="HTML")
        return
    team_name = args[0].replace(".", " ")
    percent_str = args[1].replace("%", "")
    try:
        percent = float(percent_str)
    except:
        await message.answer("<b>Процент должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    new_happiness = min(100.0, team["happiness"] + percent)
    update_team(team_name, happiness=new_happiness)
    await message.answer(f"<b>Счастье команды {team_name} изменено на {new_happiness}%</b>", parse_mode="HTML")

@router.message(Command("adddyx"), F.chat.id == GROUP_ID)
async def cmd_adddyx(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("<b>Использование: /adddyx команда процент</b>", parse_mode="HTML")
        return
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("<b>Использование: /adddyx MOUZ 50%</b>", parse_mode="HTML")
        return
    team_name = args[0].replace(".", " ")
    percent_str = args[1].replace("%", "")
    try:
        percent = float(percent_str)
    except:
        await message.answer("<b>Процент должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    new_spirit = min(100.0, team["spirit"] + percent)
    update_team(team_name, spirit=new_spirit)
    await message.answer(f"<b>Дух команды {team_name} изменен на {new_spirit}%</b>", parse_mode="HTML")

@router.message(Command("addatm"), F.chat.id == GROUP_ID)
async def cmd_addatm(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("<b>Использование: /addatm команда процент</b>", parse_mode="HTML")
        return
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("<b>Использование: /addatm 9z 36%</b>", parse_mode="HTML")
        return
    team_name = args[0].replace(".", " ")
    percent_str = args[1].replace("%", "")
    try:
        percent = float(percent_str)
    except:
        await message.answer("<b>Процент должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    new_atmosphere = min(100.0, team["atmosphere"] + percent)
    update_team(team_name, atmosphere=new_atmosphere)
    await message.answer(f"<b>Атмосфера команды {team_name} изменена на {new_atmosphere}%</b>", parse_mode="HTML")

@router.message(Command("pay"), F.chat.id == GROUP_ID)
async def cmd_pay(message: Message, command: CommandObject, bot: Bot):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user or not user["main_team"]:
        await message.answer("<b>Вы не зарегистрированы за командой</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /pay сумма @username</b>", parse_mode="HTML")
        return
    
    parts = command.args.split()
    if len(parts) != 2:
        await message.answer("<b>Неверный формат. Пример: /pay 50000 @username</b>", parse_mode="HTML")
        return
    
    amount_str, target_username = parts
    try:
        amount = int(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("<b>Сумма должна быть положительным числом</b>", parse_mode="HTML")
        return
    
    target_username = target_username.lstrip("@")
    target_user = None
    for u in get_all_users():
        if u["username"] == target_username:
            target_user = u
            break
    
    if not target_user:
        await message.answer("<b>Получатель не зарегистрирован</b>", parse_mode="HTML")
        return
    
    if user["balance"] < amount:
        await message.answer("<b>У вас недостаточно средств</b>", parse_mode="HTML")
        return
    
    update_balance(user["user_id"], user["balance"] - amount)
    update_balance(target_user["user_id"], target_user["balance"] + amount)
    
    await update_balance_topic(bot, message.chat.id)
    await message.answer(f"<b>Перевод {amount}$ пользователю @{target_username} выполнен</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("transfer_yes:"))
async def transfer_yes(callback: CallbackQuery):
    transfer_id = callback.data.split(":")[1]
    transfer = pending_transfers.get(transfer_id)
    
    if not transfer:
        await callback.answer("Предложение устарело", show_alert=True)
        return
    
    if callback.from_user.id != transfer["to_user"]:
        await callback.answer("Это не ваше предложение", show_alert=True)
        return
    
    from_team = get_team(transfer["from_team"])
    to_team = get_team(transfer["to_team"])
    
    if not from_team or not to_team:
        await callback.answer("Ошибка команд", show_alert=True)
        return
    
    to_user_balance = get_balance(transfer["to_user"])
    if to_user_balance < transfer["price"]:
        await callback.answer(f"Недостаточно средств. Нужно {transfer['price']}$", show_alert=True)
        return

    if transfer.get("is_coach"):
        remove_coach_from_team(transfer["from_team"])
        add_coach_to_team(transfer["to_team"], transfer["player"]["name"], transfer["player"]["rating"])
        
        update_hltv_player_team(transfer["player"]["name"], transfer["to_team"])
        update_hltv_profile(transfer["player"]["name"], current_team=transfer["to_team"])
    else:
        remove_player_from_team(transfer["from_team"], transfer["player"]["name"])
        
        players = to_team["players"].copy()
        main_count = len([p for p in players if p.get("status") == "main"])
        transfer["player"]["status"] = "main" if main_count < 5 else "reserve"
        players.append(transfer["player"])
        update_team(transfer["to_team"], players=players)

        update_hltv_player_team(transfer["player"]["name"], transfer["to_team"])
        update_hltv_profile(transfer["player"]["name"], current_team=transfer["to_team"])

    update_balance(transfer["from_user"], get_balance(transfer["from_user"]) + transfer["price"])
    update_balance(transfer["to_user"], get_balance(transfer["to_user"]) - transfer["price"])

    update_team(transfer["from_team"], 
                synergy=max(0, from_team["synergy"] - 10),
                potential=max(0, from_team["potential"] - 5),
                atmosphere=max(0, from_team["atmosphere"] - 10),
                happiness=max(0, from_team["happiness"] - 2),
                spirit=max(0, from_team["spirit"] - 15))
    
    update_team(transfer["to_team"],
                synergy=max(0, to_team["synergy"] - 10),
                potential=max(0, to_team["potential"] - 5),
                atmosphere=max(0, to_team["atmosphere"] - 10),
                happiness=max(0, to_team["happiness"] - 2),
                spirit=max(0, to_team["spirit"] - 15))
    
    add_transfer_history(transfer["player"]["name"], transfer["from_team"], transfer["to_team"], transfer["price"])
    
    await update_single_hltv_profile(callback.bot, callback.message.chat.id, transfer["player"]["name"])
    
    del pending_transfers[transfer_id]
    
    await callback.message.edit_text("<b>Трансфер успешно завершен!</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("transfer_no:"))
async def transfer_no(callback: CallbackQuery):
    transfer_id = callback.data.split(":")[1]
    if transfer_id in pending_transfers:
        del pending_transfers[transfer_id]
    await callback.message.edit_text("<b>Трансфер не удался</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("trade_yes:"))
async def trade_yes(callback: CallbackQuery):
    trade_id = callback.data.split(":")[1]
    trade = pending_trades.get(trade_id)
    
    if not trade:
        await callback.answer("Предложение устарело", show_alert=True)
        return
    
    if callback.from_user.id != trade["to_user"]:
        await callback.answer("Это не ваше предложение", show_alert=True)
        return

    from_is_coach = trade.get("from_is_coach", False)
    to_is_coach = trade.get("to_is_coach", False)

    if from_is_coach:
        remove_coach_from_team(trade["from_team"])
    else:
        remove_player_from_team(trade["from_team"], trade["from_player"]["name"])

    if to_is_coach:
        remove_coach_from_team(trade["to_team"])
    else:
        remove_player_from_team(trade["to_team"], trade["to_player"]["name"])
    
    from_team = get_team(trade["from_team"])
    to_team = get_team(trade["to_team"])

    if from_is_coach:
        add_coach_to_team(trade["to_team"], trade["from_player"]["name"], trade["from_player"]["rating"])
    else:
        players_to = to_team["players"].copy()
        main_count_to = len([p for p in players_to if p.get("status") == "main"])
        trade["from_player"]["status"] = "main" if main_count_to < 5 else "reserve"
        players_to.append(trade["from_player"])
        update_team(trade["to_team"], players=players_to)

    if to_is_coach:
        add_coach_to_team(trade["from_team"], trade["to_player"]["name"], trade["to_player"]["rating"])
    else:
        players_from = from_team["players"].copy()
        main_count_from = len([p for p in players_from if p.get("status") == "main"])
        trade["to_player"]["status"] = "main" if main_count_from < 5 else "reserve"
        players_from.append(trade["to_player"])
        update_team(trade["from_team"], players=players_from)
    
    # Обновление характеристик
    update_team(trade["from_team"],
                synergy=max(0, from_team["synergy"] - 2),
                potential=max(0, from_team["potential"] - 5),
                atmosphere=max(0, from_team["atmosphere"] - 3))
    
    update_team(trade["to_team"],
                synergy=max(0, to_team["synergy"] - 2),
                potential=max(0, to_team["potential"] - 5),
                atmosphere=max(0, to_team["atmosphere"] - 3))

    update_hltv_player_team(trade["from_player"]["name"], trade["to_team"])
    update_hltv_player_team(trade["to_player"]["name"], trade["from_team"])
    update_hltv_profile(trade["from_player"]["name"], current_team=trade["to_team"])
    update_hltv_profile(trade["to_player"]["name"], current_team=trade["from_team"])

    add_trade_history(trade["from_player"]["name"], trade["to_player"]["name"], trade["from_team"], trade["to_team"])
    
    await update_single_hltv_profile(callback.bot, callback.message.chat.id, trade["from_player"]["name"])
    await update_single_hltv_profile(callback.bot, callback.message.chat.id, trade["to_player"]["name"])
    
    del pending_trades[trade_id]
    
    await callback.message.edit_text("<b>Трейд игроками был завершен, поздравляем!</b>", parse_mode="HTML")
    await callback.answer()

async def update_single_hltv_profile(bot: Bot, chat_id: int, player_name: str):
    topic_data = get_hltv_topic_data()
    if not topic_data or not topic_data.get("topic_id"):
        print(f"Нет темы HLTV для обновления {player_name}")
        return
    
    profile = get_hltv_profile(player_name)
    if not profile:
        print(f"Профиль {player_name} не найден")
        return
    
    message_id = get_hltv_message_id(player_name)
    if not message_id:
        print(f"Нет message_id для {player_name}")
        return
    
    text = format_hltv_profile(profile)
    
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML"
        )
        print(f"Обновлён профиль {player_name} в теме")
    except Exception as e:
        print(f"Ошибка обновления {player_name}: {e}")

@router.callback_query(F.data.startswith("trade_no:"))
async def trade_no(callback: CallbackQuery):
    trade_id = callback.data.split(":")[1]
    if trade_id in pending_trades:
        del pending_trades[trade_id]
    await callback.message.edit_text("<b>Трейд был отклонен, видимо, не успешно.</b>", parse_mode="HTML")
    await callback.answer()

async def update_balance_topic(bot: Bot, chat_id: int):
    topic_data = get_balance_topic_data()
    message_text = format_balance_message()
    
    if topic_data and topic_data.get("topic_id") and topic_data.get("message_id"):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=topic_data["message_id"],
                text=message_text,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            print(f"Ошибка редактирования баланса: {e}")
            topic_data = None
    
    topic = await bot.create_forum_topic(chat_id, "Баланс")
    msg = await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        message_thread_id=topic.message_thread_id,
        parse_mode="HTML"
    )
    set_balance_topic_data(topic.message_thread_id, msg.message_id)

async def update_vrs_topic(bot: Bot, chat_id: int):
    topic_data = get_vrs_topic_data()
    standings = get_all_vrs_standings()
    message_text = format_vrs_message(standings)
    
    if topic_data and topic_data.get("topic_id") and topic_data.get("message_id"):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=topic_data["message_id"],
                text=message_text,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            print(f"Ошибка редактирования VRS: {e}")
            topic_data = None
    
    topic = await bot.create_forum_topic(chat_id, "Рейтинг VRS")
    msg = await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        message_thread_id=topic.message_thread_id,
        parse_mode="HTML"
    )
    set_vrs_topic_data(topic.message_thread_id, msg.message_id)

async def update_fft_topic(bot: Bot, chat_id: int):
    topic_data = get_fft_topic_data()
    players = get_fft_players()
    message_text = format_fft_list_message(players)
    
    if topic_data and topic_data.get("topic_id") and topic_data.get("message_id"):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=topic_data["message_id"],
                text=message_text,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            print(f"Ошибка редактирования FFT: {e}")
            topic_data = None
    
    topic = await bot.create_forum_topic(chat_id, "FFT игроки")
    msg = await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        message_thread_id=topic.message_thread_id,
        parse_mode="HTML"
    )
    set_fft_topic_data(topic.message_thread_id, msg.message_id)

async def update_hltv_profiles_after_match(bot: Bot, team1: Dict, team2: Dict, match_result: Dict, chat_id: int):
    topic_data = get_hltv_topic_data()
    topic_id = None
    
    if topic_data and topic_data.get("topic_id"):
        topic_id = topic_data["topic_id"]
    
    match_mvp = match_result.get("mvp", "")
    match_evp = match_result.get("evp", "")
    winner_team = match_result.get("winner_team", "")

    for team_name, stats in match_result["players_stats"].items():
        team = team1 if team_name == team1["team_name"] else team2
        is_winner = (team_name == winner_team)
        
        for stat in stats:
            player_name = stat["name"]
            is_mvp = (player_name == match_mvp)
            is_evp = (player_name == match_evp)
            
            create_hltv_profile_if_not_exists(player_name, team["team_name"])
            update_hltv_player_stats(player_name, stat, match_result["match_id"], is_winner, is_mvp, is_evp)
    
    if not topic_id:
        try:
            topic = await bot.create_forum_topic(chat_id, "HLTV профили")
            topic_id = topic.message_thread_id
            set_hltv_topic_data(topic_id, 0)
        except Exception as e:
            print(f"Ошибка создания темы HLTV: {e}")
            return
    
    for team_name, stats in match_result["players_stats"].items():
        for stat in stats:
            profile = get_hltv_profile(stat["name"])
            if not profile:
                continue
            
            text = format_hltv_profile(profile)
            message_id = get_hltv_message_id(stat["name"])
            
            if message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        parse_mode="HTML"
                    )
                    continue
                except Exception as e:
                    print(f"Ошибка редактирования {stat['name']}: {e}")
                    message_id = None
            
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    message_thread_id=topic_id,
                    parse_mode="HTML"
                )
                save_hltv_message(stat["name"], msg.message_id, topic_id)
            except Exception as e:
                print(f"Ошибка отправки {stat['name']}: {e}")
                if "message thread not found" in str(e):
                    try:
                        topic = await bot.create_forum_topic(chat_id, "HLTV профили")
                        topic_id = topic.message_thread_id
                        set_hltv_topic_data(topic_id, 0)
                        msg = await bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            message_thread_id=topic_id,
                            parse_mode="HTML"
                        )
                        save_hltv_message(stat["name"], msg.message_id, topic_id)
                    except Exception as e2:
                        print(f"Критическая ошибка HLTV: {e2}")

@router.message(Command("addcoach"), F.chat.id == GROUP_ID)
async def cmd_addcoach(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>У вас нет прав</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /addcoach команда ник рейтинг</b>", parse_mode="HTML")
        return
    
    args = command.args.split(maxsplit=2)
    if len(args) != 3:
        await message.answer("<b>Использование: /addcoach Team.Falcons xander 50.0</b>", parse_mode="HTML")
        return
    
    team_name = args[0].replace(".", " ")
    coach_name = args[1]
    try:
        coach_rating = float(args[2])
    except:
        await message.answer("<b>Рейтинг должен быть числом</b>", parse_mode="HTML")
        return
    
    team = get_team(team_name)
    if not team:
        await message.answer(f"<b>Команда {team_name} не найдена</b>", parse_mode="HTML")
        return
    
    update_team(team_name, coach_name=coach_name, coach_rating=coach_rating)
    await message.answer(f"<b>Тренер {coach_name} [{coach_rating}] добавлен в команду {team_name}</b>", parse_mode="HTML")

@router.message(Command("delplayer"), F.chat.id == GROUP_ID)
async def cmd_delplayer(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>У вас нет прав на эту команду</b>", parse_mode="HTML")
        return
    
    if not command.args:
        await message.answer("<b>Использование: /delplayer ник_игрока</b>", parse_mode="HTML")
        return
    
    player_name = command.args.strip()

    found = False
    team_name = None
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name, players FROM teams")
    rows = cur.fetchall()
    
    for team_name_db, players_json in rows:
        players = json.loads(players_json)
        for i, p in enumerate(players):
            if p["name"].lower() == player_name.lower():
                players.pop(i)
                cur.execute("UPDATE teams SET players = ? WHERE team_name = ?", (json.dumps(players), team_name_db))
                found = True
                team_name = team_name_db
                break
        if found:
            break
    
    if not found:
        cur.execute("DELETE FROM fft_players WHERE name = ?", (player_name,))
        if cur.rowcount > 0:
            found = True

    if found:
        cur.execute("DELETE FROM hltv_profiles WHERE name = ?", (player_name,))
        cur.execute("DELETE FROM hltv_messages WHERE player_name = ?", (player_name,))
    
    conn.commit()
    conn.close()
    
    if found:
        await message.answer(f"<b>Игрок {player_name} удалён из лиги!</b>", parse_mode="HTML")
    else:
        await message.answer(f"<b>Игрок {player_name} не найден в лиге</b>", parse_mode="HTML")

async def ping_self():
    bot_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not bot_url:
        print("[PING] Local mode, self-ping disabled")
        return
    
    while True:
        await asyncio.sleep(300)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(bot_url, timeout=10) as response:
                    if response.status == 200:
                        print(f"[PING] Self-ping successful")
                    else:
                        print(f"[PING] Self-ping returned {response.status}")
        except asyncio.TimeoutError:
            print(f"[PING] Self-ping timeout")
        except Exception as e:
            print(f"[PING] Self-ping failed: {e}")

async def start_ping():
    asyncio.create_task(ping_self())

async def main():
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vrs_standings")
    if cur.fetchone()[0] == 0:
        for team in get_all_teams():
            update_vrs_points(team, 0, 0, 0)
    conn.close()
    
    if os.environ.get("RENDER_EXTERNAL_URL"):
        asyncio.create_task(ping_self())
        print("[PING] Self-ping started")
    
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
