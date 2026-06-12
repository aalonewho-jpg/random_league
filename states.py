from aiogram.fsm.state import State, StatesGroup

class CreateTeam(StatesGroup):
    waiting_for_name = State()

class TransferWait(StatesGroup):
    waiting_for_player = State()
    waiting_for_team = State()
    waiting_for_price = State()

class TradeWait(StatesGroup):
    waiting_for_player1 = State()
    waiting_for_player2 = State()

class ChangeRoleWait(StatesGroup):
    waiting_for_player = State()
    waiting_for_role = State()

class SwapPlayerWait(StatesGroup):
    waiting_for_player = State()
    waiting_for_status = State()

class AdminAddPlayerWait(StatesGroup):
    waiting_for_name = State()
    waiting_for_rating = State()
    waiting_for_role = State()
    waiting_for_team = State()