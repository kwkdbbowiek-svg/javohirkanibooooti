from aiogram.fsm.state import StatesGroup, State


class PurchaseStates(StatesGroup):
    waiting_for_receipt      = State()
    waiting_for_reject_reason = State()


class CourseStates(StatesGroup):
    title         = State()
    description   = State()
    price         = State()
    media         = State()
    channel_link  = State()
    channel_id    = State()
    edit_field    = State()


class CardStates(StatesGroup):
    card_number  = State()
    holder_name  = State()
    bank_name    = State()
    card_type    = State()


class WithdrawStates(StatesGroup):
    card_number  = State()
    card_holder  = State()
    amount       = State()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm             = State()


class SupportStates(StatesGroup):
    waiting_for_message = State()
    admin_reply         = State()


class AddAdminStates(StatesGroup):
    waiting_for_id = State()


class AddSponsorStates(StatesGroup):
    waiting_for_channel_id   = State()
    waiting_for_channel_name = State()
    waiting_for_channel_link = State()


class UserSearchStates(StatesGroup):
    waiting_for_query = State()
