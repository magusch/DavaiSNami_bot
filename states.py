from aiogram.fsm.state import State, StatesGroup


class ReminderState(StatesGroup):
    waiting_for_time = State()
