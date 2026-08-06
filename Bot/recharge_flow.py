#---------- © sᴛᴀʟᴋᴇʀ@hehe_stalker
#---------- ᴘʀᴏJᴇᴄᴛ - ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ᴀᴄᴄᴏᴜɴᴛ sᴇʟʟɪɴɢ ʙᴏᴛ
#-------------------------------------------------------

import datetime
from bson import ObjectId
from aiogram import F
from aiogram.types import CallbackQuery, Message, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter, Command
from .mustjoin import check_join
import config


# ==============================
# FSM for Recharge
# ==============================
class RechargeState(StatesGroup):
    choose_method = State()
    waiting_deposit_screenshot = State()
    waiting_deposit_amount = State()


# ==============================
# Register Recharge Handlers
# ==============================
def register_recharge_handlers(dp, bot, users_col, txns_col, ADMIN_IDS):

    # ========= Entry =========
    @dp.callback_query(F.data == "recharge")
    async def recharge_start_button(cq: CallbackQuery, state: FSMContext):
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="▪️ INR", callback_data="upi_qr"),
            InlineKeyboardButton(text="▪️ Crypto", callback_data="crypto_pay"),
        )
        kb.row(InlineKeyboardButton(text="▪️ Previous", callback_data="back_main"))

        text = (
            "💰 <b>Add Funds to Your Account</b>\n"
            "––––––––––––––––––––––\n"
            "<u>Manual payments only</u>\n\n"
            "<b>Select payment method:</b>"
        )

        try:
            await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
            await state.update_data(recharge_msg_id=cq.message.message_id)
        except Exception:
            msg = await cq.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
            await state.update_data(recharge_msg_id=msg.message_id)

        await state.set_state(RechargeState.choose_method)
        await cq.answer()

    # ========= /recharge =========
    @dp.message(Command("recharge"))
    async def recharge_start_command(message: Message, state: FSMContext):
        if not await check_join(bot, message):
            return

        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="▪️ INR", callback_data="upi_qr"),
            InlineKeyboardButton(text="▪️ Crypto", callback_data="crypto_pay"),
        )
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_main"))

        msg = await message.answer(
            "💰 <b>Add Funds</b>\n\nChoose payment method:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await state.update_data(recharge_msg_id=msg.message_id)
        await state.set_state(RechargeState.choose_method)

    # ========= UPI =========
    @dp.callback_query(F.data == "upi_qr", StateFilter(RechargeState.choose_method))
    async def upi_qr(cq: CallbackQuery, state: FSMContext):
        await state.update_data(is_crypto=False)
        try:
            await cq.message.delete()
        except Exception:
            pass

        qr_image = FSInputFile("qr.jpg")
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="✅ Deposit Done", callback_data="send_deposit"))

        msg = await cq.message.answer_photo(
            photo=qr_image,
            caption="📲 <b>Send INR via UPI</b>\n\nClick <b>Deposit Done</b> after payment.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await state.update_data(recharge_msg_id=msg.message_id)
        await cq.answer()

    # ========= Crypto =========
    @dp.callback_query(F.data == "crypto_pay", StateFilter(RechargeState.choose_method))
    async def crypto_pay(cq: CallbackQuery, state: FSMContext):
        await state.update_data(is_crypto=True)

        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="Submit Payment", callback_data="crypto_submit"),
            InlineKeyboardButton(text="▪️ Previous", callback_data="deposit_now"),
        )
        kb.row(InlineKeyboardButton(text="🏠 Home", callback_data="back_main"))


        text = (
            "🪙 <b>Crypto Payment</b>\n\n"
            "<blockquote>• Binance Id - 1116914947\n"
            "• Cwallet - 61584991\n"
            "• Confirmation Name - AXCNE</blockquote>\n\n"
            "BEP20:\n<code>0x1f7c91d98384699a0bdb3509b47ea7579bef325e</code>\n\n"
            "POLYGON:\n<code>0x1f7c91d98384699a0bdb3509b47ea7579bef325e</code>\n\n"
            "💱 <b>1 USDT = ₹90</b>"
        )

        await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
        await cq.answer()

    # ========= Ask Screenshot =========
    @dp.callback_query(F.data.in_(["crypto_submit", "send_deposit"]))
    async def ask_screenshot(cq: CallbackQuery, state: FSMContext):
        await cq.message.delete()
        await cq.message.answer("📸 Send payment screenshot")
        await state.set_state(RechargeState.waiting_deposit_screenshot)
        await cq.answer()

    # ========= Screenshot =========
    @dp.message(StateFilter(RechargeState.waiting_deposit_screenshot), F.photo)
    async def screenshot_received(message: Message, state: FSMContext):
        await state.update_data(screenshot=message.photo[-1].file_id)

        kb = InlineKeyboardBuilder()
        for i in "123456789":
            kb.button(text=i, callback_data=f"amount_{i}")
        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(text="0", callback_data="amount_0"),
            InlineKeyboardButton(text=".", callback_data="amount_."),
        )
        kb.row(
            InlineKeyboardButton(text="❌", callback_data="amount_del"),
            InlineKeyboardButton(text="✅", callback_data="amount_send"),
        )

        msg = await message.answer("💰 Enter amount:\n0", reply_markup=kb.as_markup())
        await state.update_data(amount_value="", amount_msg_id=msg.message_id)
        await state.set_state(RechargeState.waiting_deposit_amount)

    # ========= Amount Input =========
    @dp.callback_query(StateFilter(RechargeState.waiting_deposit_amount))
    async def amount_input(cq: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        value = data.get("amount_value", "")

        key = cq.data.split("_")[1]
        if key == "del":
            value = value[:-1]
        elif key == "send":
            if not value:
                return await cq.answer("Enter valid amount", show_alert=True)

            txn = {
                "user_id": cq.from_user.id,
                "username": cq.from_user.username,
                "full_name": cq.from_user.full_name,
                "is_crypto": data["is_crypto"],
                "original_amount": float(value),
                "credited_amount": 0.0,
                "screenshot": data["screenshot"],
                "status": "pending",
                "created_at": datetime.datetime.utcnow()
            }
            txn_id = txns_col.insert_one(txn).inserted_id

            kb_admin = InlineKeyboardBuilder()
            kb_admin.button(text="✅ Approve", callback_data=f"approve_txn:{txn_id}")
            kb_admin.button(text="❌ Decline", callback_data=f"decline_txn:{txn_id}")
            kb_admin.adjust(2)

            for admin in ADMIN_IDS:
                await bot.send_photo(
                    admin,
                    data["screenshot"],
                    caption=f"User: {cq.from_user.username}\nAmount: {value}",
                    reply_markup=kb_admin.as_markup()
                )

            await cq.message.edit_text("✅ Payment sent for approval")
            await state.clear()
            return

        else:
            value += key

        await state.update_data(amount_value=value)
        await cq.message.edit_text(f"💰 Enter amount:\n{value or '0'}", reply_markup=cq.message.reply_markup)
        await cq.answer()

    # ========= APPROVE =========
    @dp.callback_query(F.data.startswith("approve_txn"))
    async def approve_txn(cq: CallbackQuery):
        txn_id = cq.data.split(":")[1]
        txn = txns_col.find_one({"_id": ObjectId(txn_id)})

        if not txn or txn["status"] == "approved":
            return await cq.answer("Invalid transaction", show_alert=True)

        credited = round(
            txn["original_amount"] * 90 if txn["is_crypto"] else txn["original_amount"],
            2
        )

        txns_col.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {"status": "approved", "credited_amount": credited}}
        )

        users_col.update_one(
            {"_id": txn["user_id"]},
            {"$inc": {"balance": credited}}
        )

        await bot.send_message(
            txn["user_id"],
            f"✅ Approved\nCredited: ₹{credited}"
        )

        await cq.message.edit_caption(cq.message.caption + "\n✅ Approved")
        await cq.answer("Approved")

    # ========= DECLINE =========
    @dp.callback_query(F.data.startswith("decline_txn"))
    async def decline_txn(cq: CallbackQuery):
        txn_id = cq.data.split(":")[1]
        txns_col.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {"status": "declined"}}
        )
        await cq.message.edit_caption(cq.message.caption + "\n❌ Declined")
        await cq.answer("Declined")
