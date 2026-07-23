from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard():
    buttons = [[InlineKeyboardButton(text="🛍️ Order Now", callback_data="order_now")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def products_keyboard(products):
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(text=f"{p['name']} - ${p['price']}", callback_data=f"prod_{p['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def share_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share Contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def region_keyboard():
    regions = ["Region North", "Region South", "Region East", "Region West", "Central Region"]
    buttons = []
    row = []
    for r in regions:
        row.append(InlineKeyboardButton(text=r, callback_data=f"region_{r}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_order_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_order")],
        [InlineKeyboardButton(text="🔄 Change", callback_data="change_order")]
    ])

def pending_actions_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Accept", callback_data=f"accept_{order_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{order_id}")
        ],
        [InlineKeyboardButton(text="✏️ Edit Amount", callback_data=f"edit_{order_id}")]
    ])

def admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton(text="✏️ Edit Product", callback_data="admin_edit")],
        [InlineKeyboardButton(text="❌ Delete Product", callback_data="admin_delete")],
        [InlineKeyboardButton(text="📊 Quick Report", callback_data="admin_report")]
    ])
