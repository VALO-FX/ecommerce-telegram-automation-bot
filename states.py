from aiogram.fsm.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_product = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_region = State()
    waiting_for_address = State()
    waiting_for_receipt = State()
    check_existing_user = State()

class AdminStates(StatesGroup):
    waiting_for_password = State()
    admin_menu = State()
    adding_product_name = State()
    adding_product_price = State()
    adding_product_image = State()
    editing_product_id = State()
    editing_product_field = State()
    editing_product_value = State()
    deleting_product_id = State()
