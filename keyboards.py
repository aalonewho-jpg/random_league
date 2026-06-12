from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_transfer_keyboard(transfer_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ДА", callback_data=f"transfer_yes:{transfer_id}"),
            InlineKeyboardButton(text="НЕТ", callback_data=f"transfer_no:{transfer_id}")
        ]
    ])

def get_trade_keyboard(trade_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ДА", callback_data=f"trade_yes:{trade_id}"),
            InlineKeyboardButton(text="НЕТ", callback_data=f"trade_no:{trade_id}")
        ]
    ])

def get_roster_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Изменить роль", callback_data="change_role"),
            InlineKeyboardButton(text="Переместить в запас/основу", callback_data="change_lineup")
        ]
    ])

def get_players_keyboard(players: list, prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    for player in players:
        buttons.append([InlineKeyboardButton(text=player["name"], callback_data=f"{prefix}:{player['name']}")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="roster_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_roles_keyboard() -> InlineKeyboardMarkup:
    roles = ["IGL", "Rifler", "AWP", "Support", "Entry Fragger", "Lurker", "Coach"]
    buttons = []
    for role in roles:
        buttons.append([InlineKeyboardButton(text=role, callback_data=f"set_role:{role}")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="roster_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_lineup_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обменять основу и запас", callback_data="swap_main_reserve")],
        [InlineKeyboardButton(text="Назад", callback_data="roster_back")]
    ])