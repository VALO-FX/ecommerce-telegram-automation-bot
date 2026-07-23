import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import config
import database
import keyboards
from states import OrderStates, AdminStates
from ocr import extract_amount
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def is_employee(user_id: int) -> bool:
    return str(user_id) in [str(eid) for eid in config.EMPLOYEE_IDS]

async def download_photo(file_id: str) -> str | None:
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        local_path = f"temp_{file_id}.jpg"
        await bot.download_file(file_path, local_path)
        return local_path
    except Exception as e:
        logger.error(f"Failed to download photo: {e}")
        return None

def release_lock(order_id: int):
    with database.get_db() as conn:
        conn.execute(
            "UPDATE orders SET locked_by = NULL, locked_until = NULL WHERE id = ?",
            (order_id,)
        )
        conn.commit()

def is_lock_active(order: dict) -> bool:
    if order["locked_by"] is None or order["locked_until"] is None:
        return False
    try:
        locked_until = datetime.fromisoformat(order["locked_until"])
    except ValueError:
        return False
    now = datetime.now()
    if now > locked_until:
        release_lock(order["id"])
        return False
    return True

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Welcome! Choose an option:",
        reply_markup=keyboards.main_menu_keyboard()
    )

@dp.callback_query(F.data == "order_now")
async def start_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    with database.get_db() as conn:
        products = conn.execute(
            "SELECT id, name, price, product_image_file_id FROM products"
        ).fetchall()

    if not products:
        await callback.message.answer("No products available. Contact admin.")
        await callback.answer()
        return

    if len(products) == 1:
        product = products[0]
        await state.update_data(product_id=product["id"])
        try:
            if product["product_image_file_id"]:
                await callback.message.answer_photo(
                    photo=str(product["product_image_file_id"]),
                    caption=f"Product: {product['name']}\nPrice: ${product['price']}\n\nPlease enter your full name:"
                )
            else:
                await callback.message.answer(
                    f"Product: {product['name']}\nPrice: ${product['price']}\n\nPlease enter your full name:"
                )
        except Exception as e:
            logger.error(f"Failed to send product photo: {e}")
            await callback.message.answer(
                f"Product: {product['name']}\nPrice: ${product['price']}\n\nPlease enter your full name:"
            )
        await state.set_state(OrderStates.waiting_for_name)
    else:
        await callback.message.answer(
            "Select a product from the list:",
            reply_markup=keyboards.products_keyboard(products)
        )
        await state.set_state(OrderStates.waiting_for_product)
    await callback.answer()

@dp.callback_query(OrderStates.waiting_for_product, F.data.startswith("prod_"))
async def product_chosen(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(OrderStates.check_existing_user)
    await check_previous_info(callback.from_user.id, callback.message, state)
    await callback.answer()

async def check_previous_info(user_id: int, message, state: FSMContext):
    with database.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if user:
        text = (
            f"We have your previous info:\n"
            f"Name: {user['name']}\n"
            f"Phone: {user['phone']}\n"
            f"Region: {user['state_province']}\n"
            f"Address: {user['address']}\n\n"
            f"Do you want to use this?"
        )
        buttons = [
            [InlineKeyboardButton(text="Yes, use this info", callback_data="use_previous")],
            [InlineKeyboardButton(text="No, enter new info", callback_data="new_info")]
        ]
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        await message.answer("Please enter your full name:")
        await state.set_state(OrderStates.waiting_for_name)

@dp.callback_query(OrderStates.check_existing_user, F.data == "use_previous")
async def use_previous_info(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    with database.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    await state.update_data(name=user["name"], phone=user["phone"], region=user["state_province"], address=user["address"])
    data = await state.get_data()
    product_id = data["product_id"]
    with database.get_db() as conn:
        product = conn.execute("SELECT name, price FROM products WHERE id=?", (product_id,)).fetchone()
    summary = (
        f"Order Summary:\n"
        f"Name: {user['name']}\n"
        f"Phone: {user['phone']}\n"
        f"Region: {user['state_province']}\n"
        f"Address: {user['address']}\n"
        f"Product: {product['name']}\n"
        f"Amount: ${product['price']}\n\n"
        f"Please confirm."
    )
    await callback.message.answer(summary, reply_markup=keyboards.confirm_order_keyboard())
    await state.set_state("confirm_order")
    await callback.answer()

@dp.callback_query(OrderStates.check_existing_user, F.data == "new_info")
async def new_info(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Please enter your full name:")
    await state.set_state(OrderStates.waiting_for_name)
    await callback.answer()

@dp.message(StateFilter(OrderStates.waiting_for_name))
async def name_entered(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer(
        "Share your phone number:",
        reply_markup=keyboards.share_phone_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_phone)

@dp.message(StateFilter(OrderStates.waiting_for_phone), F.contact | F.text)
async def phone_entered(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    await state.update_data(phone=phone)
    await message.answer(
        "Select your region:",
        reply_markup=keyboards.region_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_region)

@dp.callback_query(StateFilter(OrderStates.waiting_for_region), F.data.startswith("region_"))
async def region_chosen(callback: CallbackQuery, state: FSMContext):
    region = callback.data.replace("region_", "")
    await state.update_data(region=region)
    await callback.message.answer("Enter your detailed address:")
    await state.set_state(OrderStates.waiting_for_address)
    await callback.answer()

@dp.message(StateFilter(OrderStates.waiting_for_address))
async def address_entered(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    name = data["name"]
    phone = data["phone"]
    region = data["region"]
    product_id = data["product_id"]

    with database.get_db() as conn:
        conn.execute(
            "REPLACE INTO users (user_id, phone, name, state_province, address) VALUES (?,?,?,?,?)",
            (message.from_user.id, phone, name, region, address)
        )
        conn.commit()

    with database.get_db() as conn:
        product = conn.execute(
            "SELECT name, price FROM products WHERE id=?",
            (product_id,)
        ).fetchone()

    if not product:
        await message.answer("Error: product not found. Please start over.")
        await state.clear()
        return

    summary = (
        f"Order Summary:\n"
        f"Name: {name}\n"
        f"Phone: {phone}\n"
        f"Region: {region}\n"
        f"Address: {address}\n"
        f"Product: {product['name']}\n"
        f"Amount: ${product['price']}\n\n"
        f"Please confirm."
    )
    await message.answer(summary, reply_markup=keyboards.confirm_order_keyboard())
    await state.set_state("confirm_order")

@dp.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_receipt)
    await callback.message.answer(
        "Please upload the payment receipt (screenshot or photo):"
    )
    await callback.answer()

@dp.callback_query(F.data == "change_order")
async def change_order(callback: CallbackQuery, state: FSMContext):
    buttons = [
        [InlineKeyboardButton(text="Change Name", callback_data="change_name")],
        [InlineKeyboardButton(text="Change Phone", callback_data="change_phone")],
        [InlineKeyboardButton(text="Change Region", callback_data="change_region")],
        [InlineKeyboardButton(text="Change Address", callback_data="change_address")],
        [InlineKeyboardButton(text="Cancel", callback_data="cancel_change")]
    ]
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("What do you want to change?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data == "change_name")
async def change_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter your new full name:")
    await state.set_state(OrderStates.waiting_for_name)
    await callback.answer()

@dp.callback_query(F.data == "change_phone")
async def change_phone(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Share your new phone number:", reply_markup=keyboards.share_phone_keyboard())
    await state.set_state(OrderStates.waiting_for_phone)
    await callback.answer()

@dp.callback_query(F.data == "change_region")
async def change_region(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Select your new region:", reply_markup=keyboards.region_keyboard())
    await state.set_state(OrderStates.waiting_for_region)
    await callback.answer()

@dp.callback_query(F.data == "change_address")
async def change_address(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter your new detailed address:")
    await state.set_state(OrderStates.waiting_for_address)
    await callback.answer()

@dp.callback_query(F.data == "cancel_change")
async def cancel_change(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    with database.get_db() as conn:
        product = conn.execute("SELECT name, price FROM products WHERE id=?", (data["product_id"],)).fetchone()
    summary = (
        f"Order Summary:\n"
        f"Name: {data['name']}\n"
        f"Phone: {data['phone']}\n"
        f"Region: {data['region']}\n"
        f"Address: {data['address']}\n"
        f"Product: {product['name']}\n"
        f"Amount: ${product['price']}\n\n"
        f"Please confirm."
    )
    await callback.message.answer(summary, reply_markup=keyboards.confirm_order_keyboard())
    await callback.answer()

@dp.message(StateFilter(OrderStates.waiting_for_receipt), F.photo)
async def receipt_uploaded(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    product_id = data["product_id"]
    user_id = message.from_user.id

    local_path = await download_photo(file_id)
    extracted_amount = None
    if local_path:
        try:
            extracted_amount = extract_amount(local_path)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    amount = extracted_amount if extracted_amount is not None else 0

    with database.get_db() as conn:
        conn.execute(
            "INSERT INTO orders (user_id, product_id, amount, payment_image_file_id, status) "
            "VALUES (?,?,?,?,'pending')",
            (user_id, product_id, amount, file_id)
        )
        conn.commit()

    await message.answer("Your order has been received. We will review your payment and confirm shortly.")
    await state.clear()

@dp.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext):
    if not is_employee(message.from_user.id):
        await message.answer("Access denied.")
        return
    await message.answer("Enter admin password:")
    await state.set_state(AdminStates.waiting_for_password)

@dp.message(StateFilter(AdminStates.waiting_for_password))
async def admin_check_password(message: Message, state: FSMContext):
    if message.text != config.ADMIN_PASSWORD:
        await message.answer("Wrong password.")
        return
    await message.answer("Admin panel:", reply_markup=keyboards.admin_menu_keyboard())
    await state.set_state(AdminStates.admin_menu)

@dp.callback_query(StateFilter(AdminStates.admin_menu), F.data == "admin_add")
async def admin_add_product_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter product name:")
    await state.set_state(AdminStates.adding_product_name)
    await callback.answer()

@dp.message(StateFilter(AdminStates.adding_product_name))
async def admin_add_product_name(message: Message, state: FSMContext):
    await state.update_data(admin_product_name=message.text.strip())
    await message.answer("Enter product price ($):")
    await state.set_state(AdminStates.adding_product_price)

@dp.message(StateFilter(AdminStates.adding_product_price), F.text.regexp(r'^\d+$'))
async def admin_add_product_price(message: Message, state: FSMContext):
    await state.update_data(admin_product_price=int(message.text))
    await message.answer("Send product image (photo):")
    await state.set_state(AdminStates.adding_product_image)

@dp.message(StateFilter(AdminStates.adding_product_image), F.photo)
async def admin_add_product_image(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    name = data["admin_product_name"]
    price = data["admin_product_price"]
    with database.get_db() as conn:
        conn.execute(
            "INSERT INTO products (name, price, product_image_file_id) VALUES (?,?,?)",
            (name, price, file_id)
        )
        conn.commit()
    await message.answer(f"Product '{name}' added successfully.")
    await state.set_state(AdminStates.admin_menu)
    await message.answer("Admin panel:", reply_markup=keyboards.admin_menu_keyboard())

@dp.message(Command("pending"))
async def list_pending(message: Message):
    if not is_employee(message.from_user.id):
        await message.answer("You are not authorized.")
        return

    with database.get_db() as conn:
        orders = conn.execute("""
            SELECT o.id, o.user_id, o.product_id, o.amount,
                   o.payment_image_file_id, o.locked_by, o.locked_until,
                   u.name as user_name, u.phone,
                   p.name as product_name, p.price
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            JOIN products p ON o.product_id = p.id
            WHERE o.status = 'pending'
        """).fetchall()

    if not orders:
        await message.answer("No pending orders.")
        return

    for order in orders:
        if order["locked_by"] is not None and is_lock_active(order):
            if order["locked_by"] != message.from_user.id:
                await message.answer(f"Order #{order['id']} is being processed by another employee.")
                continue

        with database.get_db() as conn:
            locked_until = datetime.now() + timedelta(seconds=60)
            conn.execute(
                "UPDATE orders SET locked_by = ?, locked_until = ? WHERE id = ?",
                (message.from_user.id, locked_until.isoformat(), order["id"])
            )
            conn.commit()

        caption = (
            f"Order #{order['id']}\n"
            f"Customer: {order['user_name']}\n"
            f"Phone: {order['phone']}\n"
            f"Product: {order['product_name']}\n"
            f"Expected Price: ${order['price']}\n"
            f"OCR extracted: ${order['amount']}"
        )

        await message.answer_photo(
            photo=str(order["payment_image_file_id"]),
            caption=caption,
            reply_markup=keyboards.pending_actions_keyboard(order["id"])
        )

@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: CallbackQuery):
    if not is_employee(callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return

    order_id = int(callback.data.split("_")[1])
    with database.get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    if not order or order["status"] != "pending":
        await callback.answer("Order already processed.")
        return
    if not is_lock_active(order) or order["locked_by"] != callback.from_user.id:
        await callback.answer("You cannot process this order.", show_alert=True)
        return

    now = datetime.now().isoformat()
    with database.get_db() as conn:
        conn.execute(
            "UPDATE orders SET status='accepted', accepted_at=?, locked_by=NULL, locked_until=NULL WHERE id=?",
            (now, order_id)
        )
        conn.commit()

        row_data = conn.execute("""
            SELECT u.name as user_name, u.phone, u.state_province as region, u.address,
                   p.name as product_name, o.amount
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            JOIN products p ON o.product_id = p.id
            WHERE o.id = ?
        """, (order_id,)).fetchone()

        if row_data:
            await asyncio.to_thread(
                sheets.append_order,
                order_data={
                    "name": row_data["user_name"],
                    "phone": row_data["phone"],
                    "region": row_data["region"],
                    "address": row_data["address"],
                    "product": row_data["product_name"],
                    "amount": row_data["amount"]
                },
                spreadsheet_id=config.SPREADSHEET_ID,
                worksheet_name=config.SHEET_NAME
            )

    try:
        await bot.send_message(
            order["user_id"],
            f"Your order #{order_id} has been accepted. We will ship it soon."
        )
    except Exception:
        pass

    await callback.answer("Order accepted!")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"Order #{order_id} accepted.")

async def send_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    with database.get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = ?", (today,)).fetchone()[0]
        accepted = conn.execute("SELECT COUNT(*) FROM orders WHERE date(accepted_at) = ? AND status='accepted'", (today,)).fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM orders WHERE status='rejected' AND date(created_at) = ?", (today,)).fetchone()[0]
        total_amount = conn.execute("SELECT SUM(amount) FROM orders WHERE status='accepted' AND date(accepted_at) = ?", (today,)).fetchone()[0] or 0

    report = (
        f"📊 Daily Report ({today})\n"
        f"📦 Total orders: {total}\n"
        f"✅ Accepted: {accepted}\n"
        f"❌ Rejected: {rejected}\n"
        f"💰 Total sales: ${total_amount:,}"
    )
    for admin_id in config.EMPLOYEE_IDS:
        try:
            await bot.send_message(chat_id=int(admin_id), text=report)
        except Exception as e:
            logger.error(f"Failed to send report to {admin_id}: {e}")

async def main():
    database.init_db()
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    hour, minute = config.REPORT_TIME.split(":")
    scheduler.add_job(send_daily_report, "cron", hour=int(hour), minute=int(minute))
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
