"""
FSM (Finite State Machine) holatlari
"""
from aiogram.fsm.state import State, StatesGroup


class MovieSearchStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_title = State()


class MovieAddStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_title = State()
    waiting_for_media = State()
    waiting_for_genres = State()
    waiting_for_year = State()
    waiting_for_rating = State()
    waiting_for_description = State()


class MovieDeleteStates(StatesGroup):
    waiting_for_code = State()


class MusicStates(StatesGroup):
    waiting_for_query = State()


class StoryStates(StatesGroup):
    waiting_for_username = State()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm = State()


class SponsorAddStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_title = State()
    waiting_for_link = State()


class AdminUserStates(StatesGroup):
    waiting_for_user_id = State()
