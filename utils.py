import random
import json
import time
import sqlite3
from typing import Dict, List, Tuple, Optional
from database import get_team, get_team_winrate, get_team_achievements, get_all_vrs_standings, get_hltv_profile, DB_PATH
from config import MAP_POOL

FIRST_NAMES = [
    "frozen", "pimp", "lwoq", "prefworld", "vlone", "phzy", "mONESY", "NiKo", "ZyWoo", "device",
    "s1mple", "electroNic", "Perfecto", "B1T", "flamie", "GuardiaN", "kennyS", "olofmeister",
    "get_right", "f0rest", "GeT_RiGhT", "shox", "JW", "flusha", "KRIMZ", "TACO", "fer", "coldzera",
    "FalleN", "Stewie2K", "EliGE", "Twistzz", "NAF", "rooRooo", "Jame", "Yekindar", "FL1T",
    "qikert", "SANJI", "buster", "scooby", "zonic", "karrigan", "rain", "broky", "ropz", "huNter",
    "nexa", "Hooxi", "stavn", "jabbi", "cadiaN", "TeSeS", "sjuush", "degster", "w0nderful",
    "zorte", "n0rb3r7", "KaiR0N", "magnojez", "zont1x", "donk", "sh1ro", "chopper", "magixx",
    "ArtFr0st", "t3ureau", "Smoggy", "nAts", "chronicle", "Redgar", "d3ffo", "Sheydos", "ANGE1",
    "yay", "victor", "crashies", "Marved", "s0m", "tenZ", "ShahZaM", "dapr", "zekken", "johnqt",
    "Ethan", "boostio", "Cryocells", "jawgemo", "Demon1", "leaf", "Skadoodle", "hiko", "ScreaM",
    "Nivera", "ardiis", "trexx", "rhyme", "fearoth", "pymer", "h4rn", "k0rupt", "vico", "SluSh",
    "D3vastator", "Pogromka", "zomb1e", "Kiro", "noxio", "verto", "ravage", "pulse", "Vexor",
    "titan", "cypher", "spectr", "glitch", "Rezzi", "morph", "Zynx", "Kyz", "raptorr", "fury",
    "blast", "warden", "Revenant", "shroud", "ninja", "myth", "highDistortion", "chocoTaco",
    "WackyJacky", "Fugglet", "TGLTN", "purdy", "Kickstart", "Shrimzy", "roth", "relo", "fludd",
    "sparky", "M1me", "vox"
]
ROLES = ["AWP", "Rifler", "Entry Fragger", "Support", "Lurker", "IGL", "Coach"]
COACH_NAMES = [
    "xander", "juve", "minise", "jumpy", "asier", "kRaSnaL", "promise", "solEk", "gxx", "damp",
    "quix", "zELOS", "kzyy", "sdy", "flarich", "nukkye", "differ", "blad3", "lmbt", "hally",
    "swani", "enkay", "jamez", "valen", "boomB", "fURIous", "razor", "crash", "liTTle",
    "psy", "groove", "xoma", "mikSa", "kuben", "loord", "zeus", "dead", "F_1N", "Johnta",
    "Tank", "r1ngo", "sAw", "keita", "mithR", "towB", "Ryu", "Stratos", "neL", "Ceh9",
    "markeloff", "AnJ", "petar", "Devilwalk", "hooch", "VALENCIA", "oxigE"
]

# Глобальное множество занятых ников (для уникальности)
_used_nicks = set()

def _load_used_nicks():
    global _used_nicks
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM players")
        rows = cur.fetchall()
        _used_nicks = {row[0] for row in rows}
        conn.close()
    except:
        _used_nicks = set()

def _get_unique_nick() -> str:
    global _used_nicks
    if not _used_nicks:
        _load_used_nicks()
    
    available_nicks = [n for n in FIRST_NAMES if n not in _used_nicks]
    if not available_nicks:
        base = random.choice(FIRST_NAMES)
        counter = 1
        while f"{base}{counter}" in _used_nicks:
            counter += 1
        return f"{base}{counter}"
    
    nick = random.choice(available_nicks)
    _used_nicks.add(nick)
    return nick

def generate_random_players() -> List[Dict]:
    players = []
    selected_roles = random.sample([r for r in ROLES if r != "Coach"], 5)
    for i in range(5):
        rating = round(random.uniform(5.00, 6.00), 2)
        players.append({
            "name": _get_unique_nick(),
            "rating": rating,
            "role": selected_roles[i],
            "status": "main"
        })
    return players

def generate_random_coach() -> Dict:
    return {
        "name": random.choice(COACH_NAMES),
        "rating": round(random.uniform(5.00, 6.00), 2)
    }

def generate_random_winrates() -> Dict:
    winrates = {}
    for map_name in MAP_POOL:
        winrates[map_name] = {"wins": 0, "losses": 0}
    return winrates

def calculate_training_gains() -> Dict:
    return {
        "player": round(random.uniform(0.09, 0.20), 2),
        "synergy": round(random.uniform(0.10, 0.30), 2),
        "potential": round(random.uniform(0.05, 0.15), 2),
        "happiness": round(random.uniform(0.04, 0.10), 2)
    }

def calculate_individual_training_gain() -> float:
    return round(random.uniform(0.40, 0.75), 2)

def calculate_rating_change_training(player_rating: float) -> float:
    gain = round(random.uniform(0.09, 0.20), 2)
    new_rating = min(100.0, player_rating + gain)
    return new_rating - player_rating

def get_team_strength(team: Dict) -> float:
    player_rating_sum = sum(p["rating"] for p in team["players"])
    coach_rating = team["coach_rating"]
    synergy = team["synergy"] / 100
    potential = team["potential"] / 100
    spirit = team["spirit"] / 100
    happiness = team["happiness"] / 100
    atmosphere = team["atmosphere"] / 100
    
    base_strength = (player_rating_sum + coach_rating) * synergy * potential
    morale_factor = (spirit + happiness + atmosphere) / 3
    return base_strength * morale_factor

def get_map_advantage(team: Dict, map_name: str) -> float:
    winrate = get_team_winrate(team["team_name"], map_name)
    return winrate / 100

def simulate_match(team1: Dict, team2: Dict, maps_count: int, is_tour: bool = False) -> Dict:
    available_maps = MAP_POOL.copy()
    random.shuffle(available_maps)

    team1_score = 0
    team2_score = 0
    map_results = []

    main_team1 = [p for p in team1["players"] if p.get("status") == "main"]
    main_team2 = [p for p in team2["players"] if p.get("status") == "main"]

    players_data = {}
    for p in main_team1:
        players_data[p["name"]] = {"team": team1["team_name"], "rating": p["rating"], "kills": 0, "deaths": 0, "assists": 0}
    for p in main_team2:
        players_data[p["name"]] = {"team": team2["team_name"], "rating": p["rating"], "kills": 0, "deaths": 0, "assists": 0}

    needed_wins = {1: 1, 2: 1, 3: 2, 5: 3}[maps_count]

    def get_team_power(team):
        main_players = [p for p in team["players"] if p.get("status") == "main"]
        total_rating = sum(p["rating"] for p in main_players) + team["coach_rating"]
        synergy = team["synergy"] / 100
        potential = team["potential"] / 100
        morale = (team["spirit"] + team["happiness"] + team["atmosphere"]) / 300
        return total_rating * synergy * potential * morale

    team1_power = get_team_power(team1)
    team2_power = get_team_power(team2)

    team1_is_stronger = team1_power > team2_power

    if team1_is_stronger:
        match_winner_is_team1 = random.random() < 0.7
    else:
        match_winner_is_team1 = random.random() > 0.7

    for map_name in available_maps[:maps_count]:
        if team1_score >= needed_wins or team2_score >= needed_wins:
            break

        map_bonus1 = 1 + (get_team_winrate(team1["team_name"], map_name) - 50) / 100
        map_bonus2 = 1 + (get_team_winrate(team2["team_name"], map_name) - 50) / 100

        power1 = team1_power * map_bonus1
        power2 = team2_power * map_bonus2

        total = power1 + power2
        win_prob = power1 / total if total > 0 else 0.5

        if match_winner_is_team1:
            win_prob = min(0.75, win_prob + 0.1)
        else:
            win_prob = max(0.25, win_prob - 0.1)

        score1 = 0
        score2 = 0

        while score1 < 13 and score2 < 13:
            if random.random() < win_prob:
                score1 += 1
            else:
                score2 += 1

        while score1 == 13 and score2 == 13:
            score1 = 13
            score2 = 13
            for _ in range(6):
                if random.random() < win_prob:
                    score1 += 1
                else:
                    score2 += 1

        if score1 > score2:
            team1_score += 1
        else:
            team2_score += 1

        map_results.append({
            "map": map_name,
            "winner": team1["team_name"] if score1 > score2 else team2["team_name"],
            "score_winner": score1 if score1 > score2 else score2,
            "score_loser": score2 if score1 > score2 else score1
        })

    match_winner = team1["team_name"] if team1_score > team2_score else team2["team_name"]
    match_loser = team2["team_name"] if team1_score > team2_score else team1["team_name"]

    total_rounds = sum(tr["score_winner"] + tr["score_loser"] for tr in map_results)

    team1_players_sorted = sorted(main_team1, key=lambda x: x["rating"], reverse=True)
    team2_players_sorted = sorted(main_team2, key=lambda x: x["rating"], reverse=True)

    if match_winner == team1["team_name"]:
        winner_players = team1_players_sorted
        loser_players = team2_players_sorted
    else:
        winner_players = team2_players_sorted
        loser_players = team1_players_sorted

    for idx, player in enumerate(winner_players):
        if idx == 0:
            kills = random.randint(50, 70)
            deaths = random.randint(10, 17)
        elif idx == 1:
            kills = random.randint(40, 60)
            deaths = random.randint(12, 19)
        elif idx == 2:
            kills = random.randint(35, 50)
            deaths = random.randint(13, 20)
        else:
            kills = random.randint(25, 40)
            deaths = random.randint(14, 22)

        assists = random.randint(4, 18)

        for name in players_data:
            if players_data[name]["team"] == match_winner and name == player["name"]:
                players_data[name]["kills"] = kills
                players_data[name]["deaths"] = deaths
                players_data[name]["assists"] = assists

    for idx, player in enumerate(loser_players):
        if idx == 0:
            kills = random.randint(25, 40)
            deaths = random.randint(23, 30)
        elif idx == 1:
            kills = random.randint(20, 35)
            deaths = random.randint(20, 30)
        else:
            kills = random.randint(15, 30)
            deaths = random.randint(18, 37)

        assists = random.randint(2, 15)

        for name in players_data:
            if players_data[name]["team"] == match_loser and name == player["name"]:
                players_data[name]["kills"] = kills
                players_data[name]["deaths"] = deaths
                players_data[name]["assists"] = assists

    team1_stats = []
    team2_stats = []

    for name, data in players_data.items():
        kd_ratio = data["kills"] / max(1, data["deaths"])
        adr = round(40 + (data["kills"] / max(1, total_rounds)) * 110, 1)
        adr = min(150, max(40, adr))

        kpr = data["kills"] / max(1, total_rounds)
        apr = data["assists"] / max(1, total_rounds)

        rating_value = min(2.5, max(0.3, (kd_ratio * 0.5) + (kpr * 2.0 * 0.3) + (apr * 1.5 * 0.2)))

        stat = {
            "name": name,
            "kills": data["kills"],
            "deaths": data["deaths"],
            "assists": data["assists"],
            "kd": round(kd_ratio, 2),
            "adr": round(adr, 1),
            "rating": round(rating_value, 2)
        }
        if data["team"] == team1["team_name"]:
            team1_stats.append(stat)
        else:
            team2_stats.append(stat)

    all_stats = team1_stats + team2_stats
    all_stats.sort(key=lambda x: x["rating"], reverse=True)
    mvp = all_stats[0]["name"] if all_stats else "None"
    evp = all_stats[1]["name"] if len(all_stats) > 1 else "None"

    return {
        "map_results": map_results,
        "players_stats": {team1["team_name"]: team1_stats, team2["team_name"]: team2_stats},
        "mvp": mvp,
        "evp": evp,
        "winner_team": match_winner,
        "score_team1": team1_score,
        "score_team2": team2_score,
        "match_id": f"{int(time.time())}_{random.randint(1000, 9999)}"
    }

def calculate_vrs_points(team1_score: int, team2_score: int, maps_count: int) -> Dict:
    if team1_score > team2_score:
        return {"team1_points": 32, "team2_points": 17}
    elif team2_score > team1_score:
        return {"team1_points": 17, "team2_points": 32}
    else:
        return {"team1_points": 10, "team2_points": 10}

def format_roster(team: Dict) -> str:
    main_players = [p for p in team["players"] if p.get("status") == "main"]
    reserve_players = [p for p in team["players"] if p.get("status") == "reserve"]
    
    lines = [f"<b> • {team['team_name']} • </b>", ""]
    lines.append("<b>• Основной состав:</b>")
    for p in main_players:
        lines.append(f"<b>{p['name']} [{p['rating']:.2f}] • {p['role']}</b>")
    
    if reserve_players:
        lines.append("")
        lines.append("<b>Замена:</b>")
        for p in reserve_players:
            lines.append(f"<b>{p['name']} [{p['rating']:.2f}] • {p['role']}</b>")
    
    lines.append("")
    lines.append(f"<b>Тренер команды:</b>")
    lines.append(f"<b>{team['coach_name']} [{team['coach_rating']:.2f}] • Coach</b>")
    
    lines.append("")
    lines.append("<b>Винрейт карт у команды:</b>")
    for map_name in MAP_POOL:
        winrate = get_team_winrate(team["team_name"], map_name)
        lines.append(f"<b>{map_name} • {winrate:.0f}%</b>")
    
    lines.append("")
    lines.append("<b>[ • ХАРАКТЕРИСТИКИ • ]</b>")
    lines.append(f"<b>1 • Дух игроков: {team['spirit']:.2f}%</b>")
    lines.append(f"<b>2 • Потенциал: {team['potential']:.2f}%</b>")
    lines.append(f"<b>3 • Сыгранность: {team['synergy']:.2f}%</b>")
    lines.append(f"<b>4 • Счастье: {team['happiness']:.2f}%</b>")
    lines.append(f"<b>5 • Атмосфера: {team['atmosphere']:.2f}%</b>")
    
    standings = get_all_vrs_standings()
    position = next((i+1 for i, s in enumerate(standings) if s["team_name"] == team["team_name"]), len(standings))
    lines.append("")
    lines.append(f"<b># Место в рейтинге: #{position}</b>")
    
    lines.append("")
    lines.append("<b>Достижения команды:</b>")
    achievements = get_team_achievements(team["team_name"])
    if achievements:
        for ach in achievements:
            lines.append(f"<b>{ach['tournament']} — {ach['place']} место</b>")
    else:
        lines.append("<b>Пустовато, многовато!</b>")
    
    return "\n".join(lines)

def format_balance_message() -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT users.balance, teams.team_name 
        FROM users 
        JOIN teams ON users.main_team = teams.team_name 
        ORDER BY users.balance DESC
    """)
    rows = cur.fetchall()
    conn.close()
    
    lines = ["<b>Баланс всех команд:</b>"]
    for i, (balance, team_name) in enumerate(rows, 1):
        lines.append(f"<b>#{i} • {team_name} - {balance}$</b>")
    
    if not rows:
        lines.append("<b>Нет команд</b>")
    
    return "\n".join(lines)

def format_vrs_message(standings: List[Dict]) -> str:
    lines = ["<b>Рейтинг команд по VRS поинтам:</b>"]
    for i, s in enumerate(standings, 1):
        lines.append(f"<b>#{i} • {s['team_name']} l {s['wins']} l {s['losses']} l {s['points']}</b>")
    return "\n".join(lines)

def format_fft_list_message(players: List[Dict]) -> str:
    if not players:
        return "<b>Список FFT игроков пуст.</b>"
    
    lines = ["<b>Список FFT игроков на проекте:</b>"]
    for p in players:
        if p.get("price", 0) > 0:
            lines.append(f"<b>{p['name']} [{p['rating']:.2f}] • {p['role']} - {p['price']}$</b>")
        else:
            lines.append(f"<b>{p['name']} [{p['rating']:.2f}] • {p['role']}</b>")
    lines.append("")
    lines.append("<b>Напишите в трансферах /ahfft ник чтобы взять какого-то игрока к себе в команду.</b>")
    return "\n".join(lines)

def format_hltv_profile(profile: Dict) -> str:
    history_str = " > ".join(profile.get("team_history", []))
    if not history_str:
        history_str = profile.get("current_team", "None")
    
    return f"""<b>HLTV profile «{profile['name']}»:</b>

<b>Rating 3.0: {profile['rating_3']:.2f}</b>
<b>K/D: {profile['kd']:.2f}</b>
<b>Kills: {profile['kills']}</b>
<b>Assists: {profile['assists']}</b>
<b>Deaths: {profile['deaths']}</b>

<b>Сыграно игр: {profile['games_played']}</b>
<b>Побед: {profile['wins']}</b>
<b>Поражений: {profile['losses']}</b>
<b>Сыграно раундов: {profile['rounds_played']}</b>

<b>MVP: {profile['mvps']}</b>
<b>EVP: {profile['evps']}</b>

<b>Находится в команде: {profile['current_team']}</b>
<b>История команд: {history_str}</b>"""

def get_random_map_pool(count: int) -> List[str]:
    return random.sample(MAP_POOL, count)

def get_map_pool() -> List[str]:
    return MAP_POOL.copy()

def get_winrate_percent(team_name: str, map_name: str) -> float:
    return get_team_winrate(team_name, map_name)