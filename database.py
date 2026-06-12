import sqlite3
import json
import time
from typing import Optional, Dict, List, Any

DB_PATH = "database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            main_team TEXT,
            balance INTEGER DEFAULT 50000,
            last_training INTEGER DEFAULT 0,
            last_individual INTEGER DEFAULT 0
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_name TEXT PRIMARY KEY,
            coach_name TEXT,
            coach_rating REAL,
            players TEXT,
            winrates TEXT,
            potential REAL,
            synergy REAL,
            happiness REAL,
            spirit REAL,
            atmosphere REAL,
            vrs_points INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fft_players (
            name TEXT PRIMARY KEY,
            rating REAL,
            role TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT,
            tournament TEXT,
            place INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vrs_standings (
            team_name TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hltv_profiles (
            name TEXT PRIMARY KEY,
            rating_3 REAL DEFAULT 0,
            kd REAL DEFAULT 0,
            kills INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            rounds_played INTEGER DEFAULT 0,
            mvps INTEGER DEFAULT 0,
            evps INTEGER DEFAULT 0,
            current_team TEXT,
            team_history TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hltv_messages (
            player_name TEXT PRIMARY KEY,
            message_id INTEGER,
            topic_id INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            from_team TEXT,
            to_team TEXT,
            price INTEGER,
            timestamp INTEGER
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1 TEXT,
            player2 TEXT,
            team1 TEXT,
            team2 TEXT,
            timestamp INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            key TEXT PRIMARY KEY,
            topic_id INTEGER,
            message_id INTEGER
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS moderators (
            user_id TEXT PRIMARY KEY
        )
    """)
    
    conn.commit()
    conn.close()

def get_user(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "main_team": row[2],
            "balance": row[3],
            "last_training": row[4],
            "last_individual": row[5]
        }
    return None

def get_all_users() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, main_team, balance FROM users")
    rows = cur.fetchall()
    conn.close()
    return [{
        "user_id": r[0],
        "username": r[1],
        "main_team": r[2],
        "balance": r[3]
    } for r in rows]

def create_user(user_id: int, username: str, main_team: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id, username, main_team) VALUES (?, ?, ?)", (user_id, username, main_team))
    conn.commit()
    conn.close()

def update_user_team(user_id: int, main_team: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET main_team = ? WHERE user_id = ?", (main_team, user_id))
    conn.commit()
    conn.close()

def user_has_team(user_id: int) -> bool:
    user = get_user(user_id)
    return user is not None and user["main_team"] is not None

def update_balance(user_id: int, new_balance: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def get_team(team_name: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams WHERE team_name = ?", (team_name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "team_name": row[0],
            "coach_name": row[1],
            "coach_rating": row[2],
            "players": json.loads(row[3]),
            "winrates": json.loads(row[4]),
            "potential": row[5],
            "synergy": row[6],
            "happiness": row[7],
            "spirit": row[8],
            "atmosphere": row[9],
            "vrs_points": row[10] if len(row) > 10 else 0,
            "wins": row[11] if len(row) > 11 else 0,
            "losses": row[12] if len(row) > 12 else 0
        }
    return None

def get_all_teams() -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name FROM teams")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def create_team(team_name: str, coach_name: str, coach_rating: float, players: List[Dict], winrates: Dict,
                potential: float, synergy: float, happiness: float, spirit: float, atmosphere: float):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO teams (team_name, coach_name, coach_rating, players, winrates, potential, synergy, happiness, spirit, atmosphere)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (team_name, coach_name, coach_rating, json.dumps(players), json.dumps(winrates), potential, synergy, happiness, spirit, atmosphere))
    conn.commit()
    conn.close()

def update_team(team_name: str, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    fields = []
    values = []
    for key, value in kwargs.items():
        if key == "players":
            value = json.dumps(value)
        elif key == "winrates":
            value = json.dumps(value)
        fields.append(f"{key} = ?")
        values.append(value)
    values.append(team_name)
    cur.execute(f"UPDATE teams SET {', '.join(fields)} WHERE team_name = ?", values)
    conn.commit()
    conn.close()

def delete_team(team_name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM teams WHERE team_name = ?", (team_name,))
    conn.commit()
    conn.close()

def update_team_winrate(team_name: str, map_name: str, result: str):
    team = get_team(team_name)
    if not team:
        return
    winrates = team["winrates"]
    if map_name not in winrates:
        winrates[map_name] = {"wins": 0, "losses": 0}
    if result == "win":
        winrates[map_name]["wins"] += 1
    else:
        winrates[map_name]["losses"] += 1
    update_team(team_name, winrates=winrates)

def get_team_winrate(team_name: str, map_name: str) -> float:
    team = get_team(team_name)
    if not team:
        return 0
    winrates = team["winrates"]
    if map_name not in winrates:
        return 0
    data = winrates[map_name]
    total = data["wins"] + data["losses"]
    if total == 0:
        return 0
    return data["wins"] / total * 100

def get_fft_players() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM fft_players")
    rows = cur.fetchall()
    conn.close()
    return [{"name": r[0], "rating": r[1], "role": r[2]} for r in rows]

def add_fft_player(name: str, rating: float, role: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO fft_players (name, rating, role) VALUES (?, ?, ?)", (name, rating, role))
    conn.commit()
    conn.close()

def get_fft_player(name: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM fft_players WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"name": row[0], "rating": row[1], "role": row[2]}
    return None

def remove_fft_player(name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM fft_players WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def add_player_to_team(team_name: str, player: Dict):
    team = get_team(team_name)
    if not team:
        return
    players = team["players"].copy()
    players.append(player)
    update_team(team_name, players=players)

def remove_player_from_team(team_name: str, player_name: str):
    team = get_team(team_name)
    if not team:
        return
    players = [p for p in team["players"] if p["name"] != player_name]
    update_team(team_name, players=players)

def get_player_by_name(player_name: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name, players FROM teams")
    rows = cur.fetchall()
    conn.close()
    for team_name, players_json in rows:
        players = json.loads(players_json)
        for p in players:
            if p["name"].lower() == player_name.lower():
                return {"team": team_name, "player": p}
    return None

def update_player_rating(team_name: str, player_name: str, new_rating: float):
    team = get_team(team_name)
    if not team:
        return
    players = team["players"].copy()
    for i, p in enumerate(players):
        if p["name"] == player_name:
            players[i]["rating"] = new_rating
            break
    update_team(team_name, players=players)

def update_player_role(team_name: str, player_name: str, new_role: str):
    team = get_team(team_name)
    if not team:
        return
    players = team["players"].copy()
    for i, p in enumerate(players):
        if p["name"] == player_name:
            players[i]["role"] = new_role
            break
    update_team(team_name, players=players)

def update_player_nickname(old_name: str, new_name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name, players FROM teams")
    rows = cur.fetchall()
    for team_name, players_json in rows:
        players = json.loads(players_json)
        for i, p in enumerate(players):
            if p["name"] == old_name:
                players[i]["name"] = new_name
                cur.execute("UPDATE teams SET players = ? WHERE team_name = ?", (json.dumps(players), team_name))
                break
    conn.commit()
    conn.close()

def set_player_status(team_name: str, player_name: str, status: str):
    team = get_team(team_name)
    if not team:
        return
    players = team["players"].copy()
    for i, p in enumerate(players):
        if p["name"] == player_name:
            players[i]["status"] = status
            break
    update_team(team_name, players=players)

def get_team_players_by_status(team_name: str, status: str) -> List[Dict]:
    team = get_team(team_name)
    if not team:
        return []
    return [p for p in team["players"] if p.get("status") == status]

def update_team_coach(team_name: str, coach_name: str, coach_rating: float):
    update_team(team_name, coach_name=coach_name, coach_rating=coach_rating)

def add_achievement(team_name: str, tournament: str, place: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO achievements (team_name, tournament, place) VALUES (?, ?, ?)", (team_name, tournament, place))
    conn.commit()
    conn.close()

def get_team_achievements(team_name: str) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT tournament, place FROM achievements WHERE team_name = ?", (team_name,))
    rows = cur.fetchall()
    conn.close()
    return [{"tournament": r[0], "place": r[1]} for r in rows]

def update_vrs_points(team_name: str, points: int, wins: int = 0, losses: int = 0):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO vrs_standings (team_name, points, wins, losses)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(team_name) DO UPDATE SET
            points = points + ?,
            wins = wins + ?,
            losses = losses + ?
    """, (team_name, points, wins, losses, points, wins, losses))
    conn.commit()
    conn.close()

def get_all_vrs_standings() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT team_name, points, wins, losses FROM vrs_standings ORDER BY points DESC")
    rows = cur.fetchall()
    conn.close()
    return [{"team_name": r[0], "points": r[1], "wins": r[2], "losses": r[3]} for r in rows]

def get_hltv_player_stats(name: str) -> Optional[Dict]:
    return get_hltv_profile(name)

def update_hltv_player_team(player_name: str, new_team: str):
    profile = get_hltv_profile(player_name)
    if not profile:
        print(f"Profile for {player_name} not found")
        return
    
    old_team = profile.get("current_team", "Unknown")
    team_history = profile.get("team_history", [])
    
    print(f"Updating {player_name}: {old_team} -> {new_team}")
    print(f"Old history: {team_history}")
    
    if old_team and old_team != "Unknown" and old_team not in team_history:
        team_history.append(old_team)
    
    if new_team and new_team not in team_history:
        team_history.append(new_team)
 
    if len(team_history) > 10:
        team_history = team_history[-10:]
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE hltv_profiles 
        SET current_team = ?, team_history = ?
        WHERE name = ?
    """, (new_team, json.dumps(team_history), player_name))
    conn.commit()
    conn.close()
    
    print(f"Updated {player_name}: current_team={new_team}, history={team_history}")

def create_hltv_profile_if_not_exists(name: str, current_team: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM hltv_profiles WHERE name = ?", (name,))
    if not cur.fetchone():
        cur.execute("INSERT INTO hltv_profiles (name, current_team, team_history) VALUES (?, ?, ?)", (name, current_team, json.dumps([])))
    conn.commit()
    conn.close()

def get_hltv_profile(name: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM hltv_profiles WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "name": row[0],
            "rating_3": row[1],
            "kd": row[2],
            "kills": row[3],
            "assists": row[4],
            "deaths": row[5],
            "games_played": row[6],
            "wins": row[7],
            "losses": row[8],
            "rounds_played": row[9],
            "mvps": row[10],
            "evps": row[11],
            "current_team": row[12],
            "team_history": json.loads(row[13]) if row[13] else []
        }
    return None

def update_hltv_player_stats(name: str, match_stats: Dict, match_id: str, is_winner: bool = False, is_mvp: bool = False, is_evp: bool = False):
    profile = get_hltv_profile(name)
    if not profile:
        return
    
    new_kills = profile["kills"] + match_stats["kills"]
    new_assists = profile["assists"] + match_stats["assists"]
    new_deaths = profile["deaths"] + match_stats["deaths"]
    new_games = profile["games_played"] + 1
    new_kd = new_kills / new_deaths if new_deaths > 0 else new_kills
    new_rating = match_stats["rating"]
    avg_rating = (profile["rating_3"] * profile["games_played"] + new_rating) / new_games

    new_wins = profile["wins"] + (1 if is_winner else 0)
    new_losses = profile["losses"] + (0 if is_winner else 1)

    new_mvps = profile["mvps"] + (1 if is_mvp else 0)
    new_evps = profile["evps"] + (1 if is_evp else 0)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE hltv_profiles 
        SET kills = ?, assists = ?, deaths = ?, games_played = ?, 
            kd = ?, rating_3 = ?, wins = ?, losses = ?, mvps = ?, evps = ?
        WHERE name = ?
    """, (new_kills, new_assists, new_deaths, new_games, new_kd, avg_rating, new_wins, new_losses, new_mvps, new_evps, name))
    conn.commit()
    conn.close()

def update_hltv_profile(name: str, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    fields = []
    values = []
    for key, value in kwargs.items():
        if key == "team_history":
            value = json.dumps(value)
        fields.append(f"{key} = ?")
        values.append(value)
    values.append(name)
    cur.execute(f"UPDATE hltv_profiles SET {', '.join(fields)} WHERE name = ?", values)
    conn.commit()
    conn.close()

def add_hltv_match_history(name: str, match_data: Dict):
    profile = get_hltv_profile(name)
    if not profile:
        return
    history = profile.get("match_history", [])
    history.append(match_data)
    update_hltv_profile(name, match_history=json.dumps(history))

def save_hltv_message(player_name: str, message_id: int, topic_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO hltv_messages (player_name, message_id, topic_id) VALUES (?, ?, ?)",
                (player_name, message_id, topic_id))
    conn.commit()
    conn.close()

def get_hltv_message_id(player_name: str) -> Optional[int]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT message_id FROM hltv_messages WHERE player_name = ?", (player_name,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_hltv_topic_id() -> Optional[int]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT topic_id FROM hltv_messages LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def add_transfer_history(player_name: str, from_team: str, to_team: str, price: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO transfer_history (player_name, from_team, to_team, price, timestamp) VALUES (?, ?, ?, ?, ?)",
                (player_name, from_team, to_team, price, int(time.time())))
    conn.commit()
    conn.close()

def add_trade_history(player1: str, player2: str, team1: str, team2: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO trade_history (player1, player2, team1, team2, timestamp) VALUES (?, ?, ?, ?, ?)",
                (player1, player2, team1, team2, int(time.time())))
    conn.commit()
    conn.close()

def get_balance_topic_data() -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT topic_id, message_id FROM topics WHERE key = 'balance'")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"topic_id": row[0], "message_id": row[1]}
    return None

def set_balance_topic_data(topic_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO topics (key, topic_id, message_id) VALUES ('balance', ?, ?)", (topic_id, message_id))
    conn.commit()
    conn.close()

def get_hltv_topic_data() -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT topic_id, message_id FROM topics WHERE key = 'hltv'")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"topic_id": row[0], "message_id": row[1]}
    return None

def set_hltv_topic_data(topic_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO topics (key, topic_id, message_id) VALUES ('hltv', ?, ?)", (topic_id, message_id))
    conn.commit()
    conn.close()

def get_vrs_topic_data() -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT topic_id, message_id FROM topics WHERE key = 'vrs'")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"topic_id": row[0], "message_id": row[1]}
    return None

def set_vrs_topic_data(topic_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO topics (key, topic_id, message_id) VALUES ('vrs', ?, ?)", (topic_id, message_id))
    conn.commit()
    conn.close()

def get_fft_topic_data() -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT topic_id, message_id FROM topics WHERE key = 'fft'")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"topic_id": row[0], "message_id": row[1]}
    return None

def set_fft_topic_data(topic_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO topics (key, topic_id, message_id) VALUES ('fft', ?, ?)", (topic_id, message_id))
    conn.commit()
    conn.close()

def is_moderator(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM moderators WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    return row is not None