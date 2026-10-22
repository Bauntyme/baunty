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


class MovieViewStates(StatesGroup):
    waiting_for_code = State()


class MovieEditStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_new_value = State()


class MovieAsilmediaSyncStates(StatesGroup):
    waiting_for_input = State()


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


class AnonQuestionStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_reply = State()


class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()


class RoundVideoStates(StatesGroup):
    waiting_for_video = State()


class DocsStates(StatesGroup):
    waiting_for_translit = State()
    waiting_for_pdf = State()
    waiting_for_ocr = State()
    waiting_for_translate = State()
    waiting_for_analyze = State()
    waiting_for_img_to_pdf = State()

