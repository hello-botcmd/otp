#---------- © sᴛᴀʟᴋᴇʀ@hehe_stalker
#---------- ᴘʀᴏJᴇᴄᴛ - ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ᴀᴄᴄᴏᴜɴᴛ sᴇʟʟɪɴɢ ʙᴏᴛ
#-------------------------------------------------------
import os
import asyncio
import html
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pymongo import MongoClient
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiogram.utils.deep_linking import create_start_link
import re
from aiogram import types
import random
from aiogram.types import InputMediaVideo
from Bot.recharge_flow import register_recharge_handlers
from Bot.mustjoin import check_join
from Bot.admin_add_session import register_add_session_handlers
from config import BOT_TOKEN, ADMIN_IDS

# ================= MongoDB Setup =================
MONGO_URI = os.getenv("MONGO_URI") or "mongodb+srv://accountBot:Stalker123@accountbot.ba4pyd0.mongodb.net/?appName=AccountBot"
client = MongoClient(MONGO_URI)
db = client["QuickCodes"]
users_col = db["users"]
orders_col = db["orders"]
countries_col = db["countries"]
numbers_col = db["numbers"]

# ================= Bot Setup =================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ================= FSM =================
class AddSession(StatesGroup):
    waiting_country = State()
    waiting_number = State()
    waiting_otp = State()
    waiting_password = State()

# ================= Helpers =================
def get_or_create_user(user_id: int, username: str | None):
    user = users_col.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "username": username or None, "balance": 0.0}
        users_col.insert_one(user)
    return user

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ================ Automatic OTP Listener =================
async def otp_listener(number_doc, user_id):
    string_session = number_doc.get("string_session")
    if not string_session:
        return

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        return

    pattern = re.compile(r"\b\d{5}\b")  # OTP pattern

    try:
        while True:
            async for msg in client.iter_messages(777000, limit=5):
                if msg.message:
                    match = pattern.search(msg.message)
                    if match:
                        code = match.group(0)

                        # --- Send OTP to user ---
                        await bot.send_message(
                            user_id,
                            f"✅ OTP for +{number_doc['number']}:\n\nOTP - <code>{code}</code>\nPass - <code>OTPBOT123</code>\n\n<pre>Order Completed ✅</pre>",
                            parse_mode="HTML"
                        )
                        # --- Get buyer info ---
                        user = users_col.find_one({"_id": user_id})
                        buyer_name = user.get("username") or f"User {user_id}"
                        country = number_doc.get("country", "Unknown")
                        price = number_doc.get("price", "N/A")
                        number = number_doc.get("number", "Unknown")
                        
                        channel_message = (
                            f"<pre>✅ <b>𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖯𝗎𝗋𝖼𝗁𝖺𝗌𝖾 𝖲𝗎𝖼𝖼𝖾𝗌𝗌𝖿𝗎𝗅</b></pre>\n\n"
                            f"• For country :- {country}\n"
                            f"<b>• Application Type :- Telegram </b>\n\n"
                            f"<b>• Number :- h̶i̶d̶d̶e̶n̶•••• 📞</b>\n"
                            f"<b>• OTP :- {code}</b>\n"
                            f"<b>• Price :- ₹{price}</b>\n\n"
                            f"We are glad to have you as a customer!\n"
                            f"<b>• Support - @FreezeFund</b>"
                        )
                        await bot.send_message("@tgaltlogs", channel_message, parse_mode="HTML")
                        balance = user.get("balance", "N/A")
                        admin_message = (
                            f"<pre>📢 New Purchase Alert</pre>\n\n"
                            f"<pre>• Application: Telegram</pre>\n"
                            f"<b>• Country:</b> {country}\n"
                            f"<b>• Number:</b> +{number}\n"
                            f"<b>• OTP Received:</b> <code>{code}</code>\n\n"
                            f"<b>👤 User:</b> {buyer_name} (<code>{user_id}</code>)\n"
                            f"<b>💰 User Balance:</b> ₹{balance}"
                        )
                        await bot.send_message("@tgaltlogs", admin_message, parse_mode="HTML")
                        numbers_col.update_one(
                            {"_id": number_doc["_id"]},
                            {"$set": {"last_otp": code, "otp_fetched_at": datetime.now(timezone.utc)}})
                        await client.disconnect()
                        return

            await asyncio.sleep(3)
    except Exception as e:
        await client.disconnect()
        await bot.send_message(
            user_id,
            f"❌ OTP listener error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML"
        )
    
# ================= START =================
@dp.message(Command("start"))
async def cmd_start(m: Message):
    
    
    args = m.text.split()
    referred_by = None
    is_ref_link = False

    # Check if user started via referral link
    if len(args) > 1 and args[1].startswith("ref"):
        is_ref_link = True
        try:
            referred_by = int(args[1][3:])
        except:
            referred_by = None

    # Check if user already exists
    user = users_col.find_one({"_id": m.from_user.id})

    if user:
        # Existing user
        if is_ref_link:
            # Notify referrer if this user was referred just now
            if "referred_by" not in user and referred_by and referred_by != m.from_user.id:
                users_col.update_one({"_id": m.from_user.id}, {"$set": {"referred_by": referred_by}})
                
                # Notify the referrer
                try:
                    ref_user = users_col.find_one({"_id": referred_by})
                    if ref_user:
                        await bot.send_message(
                            chat_id=referred_by,
                            text=(
                                f"👋 <b>New Referral!</b>\n"
                                f"@{m.from_user.username or m.from_user.full_name} just started the bot using your referral link.\n\n"
                                f"💰 You’ll now earn <b>2%</b> whenever they add balance!"
                            ),
                            parse_mode="HTML"
                        )
                except Exception as e:
                    print("Referral notify error:", e)

            await m.answer("🌟")
        else:
            
            user_data = {
                "_id": m.from_user.id,
                "username": m.from_user.username or None,
                "balance": 0.0,
                "joined_at": datetime.now(timezone.utc),
            }
            
            if referred_by and referred_by != m.from_user.id:
                user_data["referred_by"] = referred_by
                users_col.insert_one(user_data)
                
                await m.answer("you have been counted in New Users list! .")

        # Notify referrer if user was referred
        if referred_by and referred_by != m.from_user.id:
            try:
                ref_user = users_col.find_one({"_id": referred_by})
                if ref_user:
                    await bot.send_message(
                        chat_id=referred_by,
                        text=(
                            f"👋 <b>New Referral!</b>\n"
                            f"@{m.from_user.username or m.from_user.full_name} just started the bot using your referral link.\n\n"
                            f"💰 You’ll earn <b>2%</b> whenever they add balance!"
                        ),
                        parse_mode="HTML"
                    )
            except Exception as e:
                print("Referral notify error:", e)

    if not await check_join(bot, m):
        return

    # Ensure user exists in DB
    get_or_create_user(m.from_user.id, m.from_user.username)
    user_id = m.from_user.id
    full_name = m.from_user.full_name  # always use the name
    user_mention = f"<a href='tg://user?id={user_id}'>{full_name}</a>"
    user = users_col.find_one({"_id": user_id})
    balance = f"₹{user['balance']:.2f} " if user else "₹0 "
    
# ================= Main Start Menu =================
    caption = (
        f"<blockquote> Hey, {user_mention}!</blockquote>\n"
        f"<b>𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖳𝗈 Account Robot- 𝖥𝖺𝗌𝗍𝖾𝗌𝗍 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖲𝖾𝗅𝗅𝖾𝗋 𝖡𝗈𝗍🥂</b>"
        f"<blockquote>- 𝖠𝗎𝗍𝗈𝗆𝖺𝗍𝗂𝖼 𝖮𝖳𝖯𝗌 📌 </blockquote>"
        f"<blockquote expandable> 🚀 𝖧𝗈𝗐 𝗍𝗈 𝗎𝗌𝖾 𝖡𝗈𝗍 : \n• 𝖱𝖾𝖼𝗁𝖺𝗋𝗀𝖾\n• 𝖲𝖾𝗅𝖾𝖼𝗍 𝖢𝗈𝗎𝗇𝗍𝗋𝗒 \n• 𝖡𝗎𝗒 𝖺𝖼𝖼𝗈𝗎𝗇𝗍\n• 𝖦𝖾𝗍 𝗇𝗎𝗆𝖻𝖾𝗋 & 𝖫𝗈𝗀𝗂𝗇 𝗍𝗁𝗋𝗈𝗎𝗀𝗁 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝗈𝗋 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖷\n• 𝖱𝖾𝖼𝖾𝗂𝗏𝖾 𝖮𝖳𝖯 & 𝗒𝗈𝗎'𝗋𝖾 𝖣𝗈𝗇𝖾 !</blockquote>\n🚀 𝖤𝗇𝗃𝗈𝗒 𝖥𝖺𝗌𝗍 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖻𝗎𝗒𝗂𝗇𝗀 𝖤𝗑𝗉𝖾𝗋𝗂𝖾𝗇𝖼𝖾 <a href='https://files.catbox.moe/277p2q.mp4'>!</a>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Balance", callback_data="balance"),
            InlineKeyboardButton(text="🛒 Buy Account", callback_data="buy")
        ],
        [
            InlineKeyboardButton(text="🥂 Sell Account", callback_data="sell")
        ],
        [
            InlineKeyboardButton(text="💳 Recharge", callback_data="recharge"),
            InlineKeyboardButton(text="👤 Account", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="➕ More..", callback_data="more_menu"),
            InlineKeyboardButton(text="⚡ Refer", callback_data="refer")
    
        ],
        [
            InlineKeyboardButton(text="Redeem 🎉", callback_data="redeem"),
            
        ]
    ])
    await m.answer(caption, parse_mode="HTML", reply_markup=kb)

    



# ================= More.. Menu =================
@dp.callback_query(lambda cq: cq.data == "more_menu")
async def more_menu(cq: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sales Log", url="https://t.me/TgAltLogs")],
        [InlineKeyboardButton(text="Support", url="https://t.me/FreezeFund")],
        [InlineKeyboardButton(text="About Account", callback_data="stats")],
        [InlineKeyboardButton(text="Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton(text="Contact Support", url="https://t.me/TgAltSupport")],
        [InlineKeyboardButton(text="How to Buy Account", url="https://t.me/tgaltlogs")],
        [InlineKeyboardButton(text="How to Sell Account", url="https://t.me/tgaltlogs")],
        [InlineKeyboardButton(text="How to Recharge", url="https://t.me/tgaltlogs")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]
    ])

    await cq.message.edit_text(
        "<b>View more services and help :</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await cq.answer()  # optional: remove "loading..." notification


#=============== Back Button =================
@dp.callback_query(lambda cq: cq.data == "back_main")
async def back_main(cq: CallbackQuery):
    user_id = cq.from_user.id
    full_name = cq.from_user.full_name  # always use the name
    user_mention = f"<a href='tg://user?id={user_id}'>{full_name}</a>"
    user = users_col.find_one({"_id": user_id})
    balance = f"{user['balance']:.2f} ₹" if user else "0 ₹"
    
    # Rebuild main menu dynamically (reuse your send_main_menu logic)
    photo_url = "https://files.catbox.moe/scgaoh.jpg"
    caption = (
        f"<blockquote> Hey, {user_mention}!</blockquote>\n"
        f"<b>𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖳𝗈 Account Robot- 𝖥𝖺𝗌𝗍𝖾𝗌𝗍 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖲𝖾𝗅𝗅𝖾𝗋 𝖡𝗈𝗍🥂</b>"
        f"<blockquote>- 𝖠𝗎𝗍𝗈𝗆𝖺𝗍𝗂𝖼 𝖮𝖳𝖯𝗌 📌 </blockquote>"
        f"<blockquote expandable> 🚀 𝖧𝗈𝗐 𝗍𝗈 𝗎𝗌𝖾 𝖡𝗈𝗍 : \n• 𝖱𝖾𝖼𝗁𝖺𝗋𝗀𝖾\n• 𝖲𝖾𝗅𝖾𝖼𝗍 𝖢𝗈𝗎𝗇𝗍𝗋𝗒 \n• 𝖡𝗎𝗒 𝖺𝖼𝖼𝗈𝗎𝗇𝗍\n• 𝖦𝖾𝗍 𝗇𝗎𝗆𝖻𝖾𝗋 & 𝖫𝗈𝗀𝗂𝗇 𝗍𝗁𝗋𝗈𝗎𝗀𝗁 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝗈𝗋 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖷\n• 𝖱𝖾𝖼𝖾𝗂𝗏𝖾 𝖮𝖳𝖯 & 𝗒𝗈𝗎'𝗋𝖾 𝖣𝗈𝗇𝖾 !</blockquote>\n🚀 𝖤𝗇𝗃𝗈𝗒 𝖥𝖺𝗌𝗍 𝖠𝖼𝖼𝗈𝗎𝗇𝗍 𝖻𝗎𝗒𝗂𝗇𝗀 𝖤𝗑𝗉𝖾𝗋𝗂𝖾𝗇𝖼𝖾 <a href='https://files.catbox.moe/277p2q.mp4'>!</a>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Balance", callback_data="balance"),
            InlineKeyboardButton(text="🛒 Buy Account", callback_data="buy")
        ],
        [
            InlineKeyboardButton(text="🥂 Sell Account", callback_data="sell")
        ],
        [
            InlineKeyboardButton(text="💳 Recharge", callback_data="recharge"),
            InlineKeyboardButton(text="👤 Account", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="➕ More..", callback_data="more_menu"),
            InlineKeyboardButton(text="⚡ Refer", callback_data="refer")
    
        ],
        [
            InlineKeyboardButton(text="Redeem 🎉", callback_data="redeem"),
            
        ]
    ])
    
    await cq.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
    await cq.answer()

    

        
#================ Balance =================
@dp.callback_query(F.data == "balance")
async def show_balance(cq: CallbackQuery):
    user = users_col.find_one({"_id": cq.from_user.id})
    await cq.answer(f"💰 Balance: {user['balance']:.2f} ₹" if user else "💰 Balance: 0 ₹", show_alert=True)

@dp.message(Command("balance"))
async def cmd_balance(msg: Message):
    user = users_col.find_one({"_id": msg.from_user.id})
    await msg.answer(f"💰 Balance: {user['balance']:.2f} ₹" if user else "💰 Balance: 0 ₹")

#================= Buy Flow =================

# Initial "Buy" message with server selection
@dp.callback_query(lambda c: c.data == "buy")
async def callback_buy(cq: CallbackQuery):
    await cq.answer()
    user = get_or_create_user(cq.from_user.id, cq.from_user.username)  # Fetch user info

    text = (
        f"🍷 <b>Buy Ready Telegram Accounts</b>:\n"
        f"––––––—————––––——–––•\n"
        f"<u>• One-click Telegram account purchase\n"
        f"• 100% activation & code delivery\n"
        f"• All accounts are clean [100% No Spam]\n"
        f"• Request multiple codes for free</u>\n"
        f"<b>• Total balance -</b> ₹{user['balance']}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="◍ Server- 1", callback_data="buy_server1")
    )
    kb.row(
        InlineKeyboardButton(text="◍ Server- 2", callback_data="buy_server2")
    )
    kb.row(InlineKeyboardButton(text="▪️ Previous", callback_data="back_main"))

    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


#Server 1 continues to normal country menu
@dp.callback_query(lambda c: c.data == "buy_server1")
async def callback_buy_server1(cq: CallbackQuery):
    await cq.answer()
    await send_country_menu(cq)  # Use the same country menu function


# Server 2 shows alert: out of stock
@dp.callback_query(lambda c: c.data == "buy_server2")
async def callback_buy_server2(cq: CallbackQuery):
    await cq.answer("⚠️ Currently this stock is out of stock!", show_alert=True)


# ================= Country Menu with Pagination =================
COUNTRIES_PER_PAGE = 10

async def send_country_menu(cq: CallbackQuery, page: int = 0):
    countries = await asyncio.to_thread(lambda: list(countries_col.find({})))
    total = len(countries)

    if total == 0:
        return await cq.message.edit_text("❌ No countries available. Admin must add stock first.")
    user_id = cq.from_user.id
    full_name = cq.from_user.full_name  # always use the name
    user_mention = f"<a href='tg://user?id={user_id}'>{full_name}</a>"
    user = users_col.find_one({"_id": user_id})
    balance = f"₹{user['balance']:.2f} " if user else "₹0 "

    # Pagination logic
    start = page * COUNTRIES_PER_PAGE
    end = start + COUNTRIES_PER_PAGE
    paginated = countries[start:end]

    kb = InlineKeyboardBuilder()
    for c in paginated:
        kb.button(text=html.escape(c["name"]), callback_data=f"country:{c['name']}")
    kb.adjust(2)

    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="▪️Previous", callback_data=f"countries_page:{page-1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="Next▪️", callback_data=f"countries_page:{page+1}"))
    if nav_buttons:
        kb.row(*nav_buttons)

    # Return to main menu
    kb.row(InlineKeyboardButton(text="▪️Home", callback_data="back_main"))

    text = f"<b><u>Buy SpamFree Telegram accounts:</u></b>\n––––––––––––––————––•\n◍ <u><b>Total balance:</b></u> {balance}  \n<u>◍ Server:</u> Server (1)\n◍ <b>Page </b>{page+1} of {(total - 1)//COUNTRIES_PER_PAGE + 1}\n✅ <a href=\"https://t.me/tgdrxapi\">Sucessful Purchases</a>\n➖➖➖➖➖➖➖➖➖➖➖"
    await cq.message.edit_text(text, reply_markup=kb.as_markup(),parse_mode="HTML", disable_web_page_preview=True)


# ================= Country Pagination Callback =================
@dp.callback_query(lambda c: c.data.startswith("countries_page:"))
async def paginate_countries(cq: CallbackQuery):
    _, page_str = cq.data.split(":")
    try:
        page = int(page_str)
    except ValueError:
        page = 0
    await send_country_menu(cq, page)
    await cq.answer()

# =============== Country Selection =================
@dp.callback_query(lambda c: c.data.startswith("country:"))
async def callback_country(cq: CallbackQuery):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)

    country = await asyncio.to_thread(lambda: countries_col.find_one({"name": country_name}))
    if not country:
        return await cq.answer("❌ Country not found", show_alert=True)

    text = (
        f"<b>Click Buy to Purchase an account:</b>\n––––––––––––—————–•\n"
        f"<blockquote> <b>Country: {html.escape(country['name'])}</b> </blockquote>\n"
        f"◍ <b><u>Price</u></b>: ₹{country['price']}\n"
        f"◍ <b><u>Stock</u></b>: {country['stock']}\n"
        f"◍ <b><u>Server</u></b> - (1)\n––––––––––––—————–•"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="▪️ Buy", callback_data=f"buy_now:{country_name}")
    )
    kb.row(
        InlineKeyboardButton(text="▪️ Back", callback_data="buy")
    )

    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
# ================= Buy Now Flow =================



# ================= Buy Now Flow =================
@dp.callback_query(F.data.startswith("buy_now:"))
async def callback_buy_now(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)
    country, user = await asyncio.to_thread(lambda: (
        countries_col.find_one({"name": country_name}),
        get_or_create_user(cq.from_user.id, cq.from_user.username)
    ))
    if not country:
        return await cq.answer("❌ Country not found", show_alert=True)
    await state.update_data(country_name=country_name, country_price=country["price"], country_stock=country["stock"])
    await state.set_state("waiting_quantity")
    await cq.message.edit_text(
        f"📦 How many {html.escape(country_name)} accounts do you want to buy?\n"
        "📝 Send only a number (e.g., 1, 5, 10)."
    )

# ================= Handle Quantity =================
@dp.message(StateFilter("waiting_quantity"))
async def handle_quantity(msg: Message, state: FSMContext):
    data = await state.get_data()
    country_name = data["country_name"]
    country_price = data["country_price"]
    country_stock = data["country_stock"]
    try:
        quantity = int(msg.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        return await msg.answer("❌ Invalid number. Please send a valid integer.")

    total_cost = country_price * quantity
    user = await asyncio.to_thread(lambda: get_or_create_user(msg.from_user.id, msg.from_user.username))
    user_balance = user.get("balance", 0)
    if user_balance < total_cost:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="💳 Add Funds", callback_data="recharge"))
        return await msg.answer(
            f"🚫 Insufficient Balance!\n💰 Your Balance: ₹{user_balance:.2f}\n🧾 Total Required: ₹{total_cost:.2f}",
            reply_markup=kb.as_markup()
        )

        
    if country_stock < quantity:
        await state.clear()  # <- ADD THIS LINE
        return await msg.answer(f"❌ Only {country_stock} account(s) left for {country_name}.")

    unsold_numbers = await asyncio.to_thread(lambda: list(numbers_col.find({"country": country_name, "used": False}).limit(quantity)))
    if len(unsold_numbers) < quantity:
        return await msg.answer(f"❌ Only {len(unsold_numbers)} account(s) available for {country_name}.")

    new_balance = user_balance - total_cost

    # ===== DB Update safely =====
    def update_db():
        try:
            users_col.update_one({"_id": user["_id"]}, {"$set": {"balance": new_balance}})
            for num in unsold_numbers:
                numbers_col.update_one({"_id": num["_id"]}, {"$set": {"used": True}})
                orders_col.insert_one({
                    "user_id": user["_id"],
                    "country": country_name,
                    "number": num["number"],
                    "price": country_price,
                    "status": "purchased",
                    "created_at": datetime.now(timezone.utc)
                })
            countries_col.update_one({"name": country_name}, {"$inc": {"stock": -quantity}})
        except Exception as e:
            print("DB update error:", e)
    await asyncio.to_thread(update_db)

    # Send numbers and start OTP listeners automatically
    for num in unsold_numbers:
        await msg.answer(
            f"<pre>✅ Purchased {country_name} account!</pre>\n📱 Number:<code> +{num['number']}</code>\n💸 Deducted: ₹{country_price}\n💰 Balance Left: ₹{new_balance:.2f}\n\n<blockquote>Note: If any problem receiving OTP, then please Instantly DM support @FreezeFund</blockquote>"
        )
        # start OTP listener in background
        asyncio.create_task(otp_listener(num, msg.from_user.id))

    await state.clear()

# ================= Admin Add Number Flow =================
@dp.message(Command("add"))
async def cmd_add_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("❌ No countries found. Add some countries first in DB.")
    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c["name"], callback_data=f"add_country:{c['name']}")
    kb.adjust(2)
    await msg.answer("🌍 Select the country you want to add a number for:", reply_markup=kb.as_markup())
    await state.set_state(AddSession.waiting_country)

@dp.callback_query(F.data.startswith("add_country:"))
async def callback_add_country(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)
    await state.update_data(country=country_name)
    await cq.message.answer(f"📞 Enter the phone number for {country_name} (e.g., +14151234567):")
    await state.set_state(AddSession.waiting_number)

@dp.message(AddSession.waiting_number)
async def add_number_get_code(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = msg.text.strip()
    await state.update_data(number=phone)

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await msg.answer("📩 Code sent! Please enter the OTP you received on Telegram or SMS:")
        await state.update_data(session=session.save(), phone_code_hash=sent.phone_code_hash)
        await client.disconnect()
        await state.set_state(AddSession.waiting_otp)
    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Failed to send code: {e}")

@dp.message(AddSession.waiting_otp)
async def add_number_verify_code(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = data["number"]
    session_str = data["session"]
    phone_code_hash = data.get("phone_code_hash")

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()
    try:
        await client.sign_in(phone=phone, code=msg.text.strip(), phone_code_hash=phone_code_hash)
        string_session = client.session.save()
        await client.disconnect()

        numbers_col.insert_one({
            "country": country,
            "number": phone,
            "string_session": string_session,
            "used": False
        })
        countries_col.update_one({"name": country}, {"$inc": {"stock": 1}}, upsert=True)
        # Send confirmation with string session for verification
        await msg.answer(f"✅ Added number {phone} for {country} successfully!\n🔑 String Session:\n<code>{string_session}</code>", parse_mode="HTML")
        await state.clear()

    except Exception as e:
        if "PASSWORD" in str(e).upper() or "two-step" in str(e).lower():
            await msg.answer("🔐 Two-step verification is enabled. Please send the password for this account:")
            await state.update_data(session=session_str)
            await state.set_state(AddSession.waiting_password)
        else:
            await msg.answer(f"❌ Error verifying code: {e}")
            await client.disconnect()

@dp.message(AddSession.waiting_password)
async def add_number_with_password(msg: Message, state: FSMContext):
    data = await state.get_data()
    country = data["country"]
    phone = data["number"]
    session_str = data["session"]

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()
    try:
        await client.sign_in(password=msg.text.strip())
        string_session = client.session.save()
        await client.disconnect()

        numbers_col.insert_one({
            "country": country,
            "number": phone,
            "string_session": string_session,
            "used": False
        })
        countries_col.update_one({"name": country}, {"$inc": {"stock": 1}}, upsert=True)
        # Send confirmation with string session for verification
        await msg.answer(
            f"✅ Added number {phone} (with 2FA) for {country} successfully!\n\n"
            f"🔑 String Session:\n<blockquote expandable><code>{string_session}</code></blockquote>",
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Error signing in with password: {e}")

# ===== Admin Country Commands =====
@dp.message(Command("addcountry"))
async def cmd_add_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    await msg.answer("🌍 Send the country name and price separated by a comma (e.g., India,50):")
    await state.set_state("adding_country")

@dp.message(StateFilter("adding_country"))
async def handle_add_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if "," not in msg.text:
        return await msg.answer("❌ Invalid format. Example: India,50")
    name, price = msg.text.split(",", 1)
    try:
        price = float(price.strip())
    except ValueError:
        return await msg.answer("❌ Invalid price format.")
    countries_col.update_one({"name": name.strip()}, {"$set": {"price": price, "stock": 0}}, upsert=True)
    await msg.answer(f"✅ Country {name.strip()} added/updated with price {price}.")
    await state.clear()

# ================ Admin: Remove Country =================
class RemoveCountry(StatesGroup):
    waiting_for_name = State()


@dp.message(Command("removecountry"))
async def cmd_remove_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    await msg.answer("🌍 Please enter the exact country name you want to remove:")
    await state.set_state(RemoveCountry.waiting_for_name)


@dp.message(StateFilter(RemoveCountry.waiting_for_name))
async def handle_remove_country_name(msg: Message, state: FSMContext):
    country_name = msg.text.strip()
    result = countries_col.delete_one({"name": country_name})

    if result.deleted_count == 0:
        await msg.answer(f"❌ Country <b>{country_name}</b> not found.", parse_mode="HTML")
    else:
        await msg.answer(f"✅ Country <b>{country_name}</b> removed successfully.", parse_mode="HTML")

    await state.clear()

@dp.message(Command("db"))
async def cmd_db(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("❌ No countries found in DB.")

    text = "📚 <b>Numbers in Database by Country:</b>\n\n"

    for c in countries:
        country_name = c["name"]
        numbers = list(numbers_col.find({"country": country_name}))
        text += f"🌍 <b>{country_name}:</b>\n"
        if numbers:
            for num in numbers:
                text += f"• {num['number']} {'✅' if num.get('used') else ''}\n"
        else:
            text += "No number\n"
        text += "\n"

    await msg.answer(text, parse_mode="HTML")



# ====================== SELL ACCOUNT FEATURE (FIXED & FULL) ======================

sell_prices_col = db["sell_prices"]

# --- FSM States ---
class SetPrices(StatesGroup):
    waiting_list = State()

class SellSession(StatesGroup):
    waiting_sell_number = State()
    waiting_sell_otp = State()
    waiting_sell_password = State()


# --- Admin Command: Set Sell Prices ---
@dp.message(Command("setprices"))
async def cmd_set_prices(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    await msg.answer(
        "📋 Send the price list in this format:\n\n"
        "<code>+1 USA 🇺🇸 - ₹10\n+91 India 🇮🇳 - ₹29\n+44 UK 🇬🇧 - ₹15</code>\n\n"
        "⚠️ Sending new list will overwrite the old one."
    )
    await state.set_state(SetPrices.waiting_list)


@dp.message(StateFilter(SetPrices.waiting_list))
async def handle_set_prices(msg: Message, state: FSMContext):
    text = msg.text.strip()
    sell_prices_col.delete_many({})

    pattern = re.compile(
        r"(\+\d{1,4})\s+([A-Za-z\s🇮🇳🇺🇸🇬🇧🇩🇪🇫🇷🇷🇺🇯🇵🇨🇳🇰🇷]+)\s*-\s*₹?\s*(\d+)",
        flags=re.UNICODE
    )

    entries = pattern.findall(text)
    if not entries:
        return await msg.answer(
            "❌ Invalid format detected.\nUse:\n<code>+1 USA 🇺🇸 - ₹10</code>\n<code>+91 India 🇮🇳 - ₹29</code>"
        )

    for code, name, price in entries:
        sell_prices_col.insert_one({
            "code": code.strip(),
            "name": name.strip(),
            "price": int(price)
        })

    prices = "\n".join([f"{c} {n} - ₹{p}" for c, n, p in entries])
    await msg.answer(f"✅ Price list updated successfully!\n\n<pre>{prices}</pre>", parse_mode="HTML")
    await state.clear()


# --- Callback for Sell Button ---
@dp.callback_query(F.data == "sell")
async def callback_sell(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    prices = list(sell_prices_col.find({}))
    if not prices:
        return await cq.message.answer("❌ No sell prices set by admins yet.")

    text = "<b>💸 Sell Your Telegram Accounts!</b>\n\n"
    text += "Check the current buying prices:\n\n"
    for p in prices:
        text += f"<code>{p['code']} {p['name']}</code> - ₹{p['price']}\n"
    text += "\nSend the number (with +countrycode) you want to sell (e.g. +14151234567)."

    await cq.message.answer(text, parse_mode="HTML")
    await state.set_state(SellSession.waiting_sell_number)


# --- User Sends Number ---
@dp.message(StateFilter(SellSession.waiting_sell_number))
async def user_sells_number(msg: Message, state: FSMContext):
    phone = msg.text.strip()
    if not phone.startswith("+"):
        return await msg.answer("❌ Send valid phone number with country code (e.g., +14151234567).")

    # Find country
    all_prices = list(sell_prices_col.find({}))
    matched = None
    for p in all_prices:
        if phone.startswith(p["code"]):
            matched = p
            break

    if not matched:
        return await msg.answer("❌ Sorry, we don't buy numbers from that country currently.")

    country_name = matched["name"]
    price = matched["price"]

    await msg.answer(
        f"🌍 <b>Country:</b> {country_name}\n💰 <b>Price:</b> ₹{price}\n\n"
        f"📩 Sending OTP to {phone}..."
    )

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()

    try:
        sent = await client.send_code_request(phone)
        await state.update_data(
            session=session.save(),
            phone=phone,
            phone_code_hash=sent.phone_code_hash,
            price=price,
            country_name=country_name,
        )
        await msg.answer("📩 Code sent! Please enter the OTP you received on Telegram or SMS:")
        await client.disconnect()
        await state.set_state(SellSession.waiting_sell_otp)
    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Failed to send code: {e}")


# --- User Sends OTP ---
@dp.message(StateFilter(SellSession.waiting_sell_otp))
async def user_sells_otp(msg: Message, state: FSMContext):
    data = await state.get_data()
    phone = data["phone"]
    session_str = data["session"]
    phone_code_hash = data["phone_code_hash"]
    price = data["price"]
    country_name = data["country_name"]

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=msg.text.strip(), phone_code_hash=phone_code_hash)
        string_session = client.session.save()
        await client.disconnect()

        # Store string session now that it's authorized
        await state.update_data(string_session=string_session)

        await msg.answer("🔐 If the account has a password, please send it now.\nIf not, send 'skip'.")
        await state.set_state(SellSession.waiting_sell_password)

    except Exception as e:
        # Handle Two-Factor case
        if "PASSWORD" in str(e).upper() or "two-step" in str(e).lower():
            await msg.answer("🔐 Two-step verification enabled! Please send the password.")
            await state.set_state(SellSession.waiting_sell_password)
            await client.disconnect()
            await state.update_data(string_session=session_str)
        else:
            await client.disconnect()
            await msg.answer(f"❌ Error verifying code: {e}")


# --- Handle 2FA Password or Skip ---
@dp.message(StateFilter(SellSession.waiting_sell_password))
async def user_sell_password(msg: Message, state: FSMContext):
    data = await state.get_data()
    phone = data["phone"]
    country_name = data["country_name"]
    price = data["price"]
    session_str = data["session"]
    string_session = data.get("string_session")

    password = msg.text.strip() if msg.text.lower() != "skip" else None

    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()

    # If string session already authorized, skip re-login
    if not string_session:
        try:
            if password and password.lower() != "skip":
                await client.sign_in(password=password)
            string_session = client.session.save()
        except Exception as e:
            await client.disconnect()
            return await msg.answer(f"❌ Error signing in with password: {e}")

    await client.disconnect()

    # Save number to DB (so OTP listener works)
    numbers_col.update_one(
        {"number": phone},
        {
            "$set": {
                "country": country_name,
                "number": phone,
                "string_session": string_session,
                "used": False
            }
        },
        upsert=True
    )

    # Send to Admin Group
    kb = InlineKeyboardBuilder()
    kb.button(text="📩 Get OTP", callback_data=f"get_otp:{phone}")
    kb.button(text=f"✅ Approve ₹{price}", callback_data=f"approve_sell:{msg.from_user.id}:{phone}:{price}")
    kb.adjust(1)

    user = get_or_create_user(msg.from_user.id, msg.from_user.username)
    text = (
        f"<b>📤 New Account Submitted for Sale</b>\n\n"
        f"👤 User: {user.get('username') or msg.from_user.id} (<code>{msg.from_user.id}</code>)\n"
        f"🌍 Country: {country_name}\n"
        f"📞 Number: {phone}\n"
        f"💸 Price: ₹{price}\n"
        f"💰 Balance: ₹{user.get('balance', 0)}\n\n"
        f"🔑 String Session:\n<blockquote expandable><code>{string_session}</code></blockquote>\n"
        f"{'🔐 Password: ' + password if password else '🔓 No password provided.'}"
    )

    await bot.send_message(
        "-1003237240464",  # your admin group ID
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await msg.answer(
        f"✅ Your number {phone} sent for admin approval.\nYou’ll be paid ₹{price} after verification."
    )
    await state.clear()


# --- Admin: Get OTP Button ---
@dp.callback_query(F.data.startswith("get_otp:"))
async def callback_admin_get_otp(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("❌ Not authorized.")
    phone = cq.data.split(":")[1]
    number_doc = numbers_col.find_one({"number": phone})
    if not number_doc:
        return await cq.answer("❌ Number session not found.", show_alert=True)
    await cq.answer("Listening for OTP...")
    asyncio.create_task(otp_listener(number_doc, cq.from_user.id))


# --- Admin: Approve Sell ---
@dp.callback_query(F.data.startswith("approve_sell:"))
async def callback_approve_sell(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("❌ Not authorized.", show_alert=True)
    _, user_id, phone, price = cq.data.split(":")
    user_id, price = int(user_id), int(price)

    users_col.update_one({"_id": user_id}, {"$inc": {"balance": price}})

    await bot.send_message(
        user_id,
        f"🎉 Your sold account {phone} has been approved!\n💰 ₹{price} added to your balance."
    )

    await cq.answer("✅ Approved and balance added.", show_alert=True)
    await cq.message.edit_text(cq.message.text + "\n\n✅ Approved by admin.")
    

# --- Add Sell Button in Main Menu ---
# Add this line inside your main menu keyboard in cmd_start():
# kb.row(InlineKeyboardButton(text="💸 Sell Account", callback_data="sell"))



#============== Admin: Edit Country =================
class EditCountry(StatesGroup):
    waiting_new_name = State()
    waiting_new_price = State()

@dp.message(Command("editcountry"))
async def cmd_edit_country(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    countries = list(countries_col.find({}))
    if not countries:
        return await msg.answer("📭 No countries to edit.")
    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c["name"], callback_data=f"editcountry:{c['name']}")
    kb.adjust(2)
    await msg.answer("🌍 Select a country to edit:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("editcountry:"))
async def callback_edit_country(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    _, country_name = cq.data.split(":", 1)
    country = countries_col.find_one({"name": country_name})
    if not country:
        return await cq.message.edit_text(f"❌ Country {country_name} not found.")

    await state.update_data(country_name=country_name)

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✏️ Change Name", callback_data="editcountry_change_name"),
        InlineKeyboardButton(text="💰 Change Price", callback_data="editcountry_change_price")
    )
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="editcountry_cancel"))
    await cq.message.edit_text(
        f"🛠️ Editing Country: <b>{country_name}</b>\n"
        f"💸 Current Price: ₹{country['price']}",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "editcountry_change_name")
async def callback_edit_change_name(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    data = await state.get_data()
    country_name = data.get("country_name")
    await cq.message.answer(f"✏️ Send new name for <b>{country_name}</b>:", parse_mode="HTML")
    await state.set_state(EditCountry.waiting_new_name)

@dp.message(StateFilter(EditCountry.waiting_new_name))
async def handle_new_country_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    old_name = data.get("country_name")
    new_name = msg.text.strip()

    countries_col.update_one({"name": old_name}, {"$set": {"name": new_name}})
    numbers_col.update_many({"country": old_name}, {"$set": {"country": new_name}})
    await msg.answer(f"✅ Country name changed from <b>{old_name}</b> → <b>{new_name}</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "editcountry_change_price")
async def callback_edit_change_price(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    data = await state.get_data()
    country_name = data.get("country_name")
    await cq.message.answer(f"💰 Send new price for <b>{country_name}</b>:", parse_mode="HTML")
    await state.set_state(EditCountry.waiting_new_price)

@dp.message(StateFilter(EditCountry.waiting_new_price))
async def handle_new_country_price(msg: Message, state: FSMContext):
    data = await state.get_data()
    country_name = data.get("country_name")
    try:
        price = float(msg.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        return await msg.answer("❌ Invalid price format. Please send a valid number.")

    countries_col.update_one({"name": country_name}, {"$set": {"price": price}})
    await msg.answer(f"✅ Updated price for <b>{country_name}</b> to ₹{price:.2f}", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "editcountry_cancel")
async def callback_edit_cancel(cq: CallbackQuery, state: FSMContext):
    await cq.answer("❌ Cancelled")
    await state.clear()
    await cq.message.edit_text("❌ Edit cancelled.")


@dp.callback_query(F.data == "stats")
async def callback_howto(cq: CallbackQuery):
    user = users_col.find_one({"_id": cq.from_user.id})
    if not user:
        user = get_or_create_user(cq.from_user.id, cq.from_user.username)
    steps_text = (
        f"<b>◍ Account Seller Bot</b>\n––––––——–––————––––——–––•\n"
        f"<blockquote><b>👤 Name: </b>{cq.from_user.full_name}\n"
        f"<b>💻 Username: </b>@{cq.from_user.username if cq.from_user.username else 'N/A'}\n"
        f"<b>🆔 User ID:</b> {cq.from_user.id}\n"
        f"<b>💰 Balance:</b> ₹{user.get('balance', 0.0):.2f}</blockquote>\n"
        f"––––––——–––————––––——–––•\n •<b> Bot</b>: @\n• <b>Sales Log</b>: @AltSellBot"
        
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="▪️ Support", url=f"https://t.me/FreezeFund"),
        InlineKeyboardButton(text="▪️ 𝙃𝙤𝙬 𝙩𝙤 𝙪𝙨𝙚", url=f"https://t.me/tgaltlogs")
    )
    kb.row(
        InlineKeyboardButton(text="▪️ Previous", callback_data="back_main")
    )
    
    await cq.message.edit_text(steps_text, parse_mode="HTML", reply_markup=kb.as_markup())
    await cq.answer()

@dp.callback_query(F.data == "howto")
async def callback_howto(cq: CallbackQuery):
    await cq.answer() # Answer first
    steps_text = ("📚 FᴀQ & Sᴜᴘᴘᴏʀᴛ 😊\n\n🔗 𝙃𝙤𝙬 𝙩𝙤 𝙪𝙨𝙚:  👉 @AltSellBot\n💬 Oғғɪᴄɪᴀʟ Sᴜᴘᴘᴏʀᴛ:   👉 @FreezeFund\n🤖 Oғғɪᴄɪᴀʟ Bᴏᴛ:     👉 @AltSellBot\n\n🛟 Fᴇᴇʟ Fʀᴇᴇ Tᴏ Rᴇᴀᴄʜ Oᴜ𝙩 Iғ Yᴏᴜ Nᴇᴇᴅ Aɴʏ Hᴇʟᴘ!")
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📲 Support", url=f"https://t.me/FreezeFund"),
        InlineKeyboardButton(text="🔗 𝙃𝙤𝙬 𝙩𝙤 𝙪𝙨𝙚", url=f"https://t.me/tgaltlogs")
    )
    # Added back button
    kb.row(InlineKeyboardButton(text="🔙 Main Menu", callback_data="main_menu")) 
    
    await cq.message.edit_text(steps_text, parse_mode="HTML", reply_markup=kb.as_markup())


@dp.callback_query(lambda c: c.data == "refer")
async def callback_refer(cq: CallbackQuery):
    # Ensure the user exists
    user = get_or_create_user(cq.from_user.id, cq.from_user.username)

    # Create a referral link
    bot_username = (await bot.get_me()).username
    refer_link = f"https://t.me/{bot_username}?start=ref{cq.from_user.id}"

    # Message text
    text = (
        f"Invite your friends to use the bot and earn 2% of every recharge they make!\n ––––––—————–––––———–––•\n"
        f"🔗 <b>Your Referral Link:</b>\n<code>{refer_link}</code>"
    )

    # Build inline keyboard
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="📤 Share Link",
            url=f"https://t.me/share/url?url={refer_link}&text=Join%20and%20earn%20with%20this%20bot!"
        )
    )
    kb.row(
        InlineKeyboardButton(
            text="▪️ Back",
            callback_data="back_main"
        )
    )

    # Safely edit the current message
    await cq.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cq.answer()

# ================= /sales Command =================
@dp.message(Command("sales"))
async def cmd_sales(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ You are not authorized to view sales report.")
        now = datetime.utcnow()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_day = datetime(now.year, now.month, now.day)
        users_col = db["users"]
        orders_col = db["orders"]
        recharges_col = db["recharges"]  # If you track top-ups
        bot_status = "🟢 Active"
        total_users = users_col.count_documents({})
        all_orders = list(orders_col.find({"status": "purchased"}))
        total_numbers_sold = len(all_orders)
        total_earnings = sum(order.get("price", 0) for order in all_orders)
        avg_price = total_earnings / total_numbers_sold if total_numbers_sold else 0
        from collections import Counter
        country_counts = Counter(order.get("country", "Unknown") for order in all_orders)
        top_country = country_counts.most_common(1)[0][0] if country_counts else "N/A"
        total_recharge = sum(txn.get("amount", 0) for txn in recharges_col.find({}))
        
        report = (
            "📊 <b>Bot Profit Report</b>\n"
            f"<b>⚙️ Bot Status: </b>{bot_status}\n\n"
            f"<b>👥 Total Users: </b>{total_users}\n"
            f"<b>🔢 Total Numbers Sold: </b>{total_numbers_sold}\n"
            f"💰 Total Sales: ₹{total_earnings:.2f}\n"
            f"⚖️ Avg Price/Number: ₹{avg_price:.2f}\n"
            f"🌍 Top Country: {top_country}\n"
            f"💳 Total Recharge: ₹{total_recharge:.2f}\n\n"
        )
        await msg.answer(report, parse_mode="HTML")


# ================= Admin Credit/Debit Commands =================
@dp.message(Command("credit"))
async def cmd_credit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    
    await msg.answer("💰 Send user ID and amount to credit separated by a comma (e.g., 123456789,50):")
    await state.set_state("credit_waiting")

@dp.message(StateFilter("credit_waiting"))
async def handle_credit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    if "," not in msg.text:
        return await msg.answer("❌ Invalid format. Example: 123456789,50")

    user_id_str, amount_str = msg.text.split(",", 1)
    try:
        user_id = int(user_id_str.strip())
        amount = float(amount_str.strip())
    except ValueError:
        return await msg.answer("❌ Invalid user ID or amount format.")

    user = users_col.find_one({"_id": user_id})
    if not user:
        return await msg.answer(f"❌ User with ID {user_id} not found.")

    new_balance = user.get("balance", 0.0) + amount
    users_col.update_one({"_id": user_id}, {"$set": {"balance": new_balance}})
    await msg.answer(f"✅ Credited ₹{amount:.2f} to {user.get('username') or user_id}\n💰 New Balance: ₹{new_balance:.2f}")
    await state.clear()


@dp.message(Command("debit"))
async def cmd_debit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    
    await msg.answer("💸 Send user ID and amount to debit separated by a comma (e.g., 123456789,50):")
    await state.set_state("debit_waiting")

@dp.message(StateFilter("debit_waiting"))
async def handle_debit(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    if "," not in msg.text:
        return await msg.answer("❌ Invalid format. Example: 123456789,50")

    user_id_str, amount_str = msg.text.split(",", 1)
    try:
        user_id = int(user_id_str.strip())
        amount = float(amount_str.strip())
    except ValueError:
        return await msg.answer("❌ Invalid user ID or amount format.")

    user = users_col.find_one({"_id": user_id})
    if not user:
        return await msg.answer(f"❌ User with ID {user_id} not found.")

    new_balance = max(user.get("balance", 0.0) - amount, 0.0)
    users_col.update_one({"_id": user_id}, {"$set": {"balance": new_balance}})
    await msg.answer(f"✅ Debited ₹{amount:.2f} from {user.get('username') or user_id}\n💰 New Balance: ₹{new_balance:.2f}")
    await state.clear()





    # ================= MongoDB Redeem Collection =================
redeem_col = db["redeem_codes"]  # Add this at top with other collections

# ================= Redeem FSM =================
class RedeemState(StatesGroup):
    # For auto-generated redeem codes
    waiting_amount = State()          # Admin enters amount
    waiting_limit = State()           # Admin selects max users via inline numeric keypad

    # For custom redeem codes
    waiting_code = State()            # Admin enters custom code (e.g. DIWALI100)
    waiting_amount_custom = State()   # Admin enters amount for custom code
    waiting_limit_custom = State()    # Admin selects max users for custom code

class UserRedeemState(StatesGroup):
    waiting_code = State()            # User enters redeem code
    
# ================= Helper =================
import random, string
def generate_code(length=8):
    """Generate code like HEIKE938"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))



    
        # ================= Admin: Create Custom Redeem =================
@dp.message(Command("cusredeem"))
async def cmd_custom_redeem(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")
    await msg.answer("🎟️ Enter the custom redeem code (e.g. DIWALI100):")
    await state.set_state(RedeemState.waiting_code)

# ================= Admin: Handle Custom Code =================
@dp.message(StateFilter(RedeemState.waiting_code))
async def handle_custom_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    if redeem_col.find_one({"code": code}):
        return await msg.answer("⚠️ This code already exists. Try another one.")

    await state.update_data(custom_code=code)
    await msg.answer("💰 Enter the amount for this redeem code:")
    await state.set_state(RedeemState.waiting_amount_custom)

# ================= Admin: Handle Custom Amount =================
@dp.message(StateFilter(RedeemState.waiting_amount_custom))
async def handle_custom_amount(msg: Message, state: FSMContext):
    try:
        amount = float(msg.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await msg.answer("❌ Invalid amount. Send a number like 50 or 100.")

    await state.update_data(amount=amount, limit_str="")

    # Inline numeric keypad
    kb = InlineKeyboardBuilder()
    for row in (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("0", "❌", "✅")):
        kb.row(*[InlineKeyboardButton(text=btn, callback_data=f"cusredeemnum:{btn}") for btn in row])

    await msg.answer(
        "👥 Select max number of users who can claim this custom code:\n<b>0</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await state.set_state(RedeemState.waiting_limit_custom)

# ================= Admin: Handle Custom Inline Number Pad =================
@dp.callback_query(F.data.startswith("cusredeemnum:"))
async def handle_custom_redeem_number(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current = data.get("limit_str", "")
    value = cq.data.split(":")[1]

    if value == "❌":
        current = current[:-1]
    elif value == "✅":
        if not current:
            await cq.answer("❌ Please select at least one user.", show_alert=True)
            return
        try:
            limit = int(current)
        except ValueError:
            await cq.answer("❌ Invalid number.", show_alert=True)
            return

        code = data.get("custom_code")
        amount = data.get("amount")
        created_at = datetime.utcnow()

        # Insert redeem into MongoDB
        redeem_col.insert_one({
            "code": code,
            "amount": amount,
            "max_claims": limit,
            "claimed_count": 0,
            "claimed_users": [],
            "created_at": created_at
        })

        await cq.message.edit_text(
            f"✅ Custom redeem code created!\n\n"
            f"🎟️ Code: <code>{code}</code>\n"
            f"💰 Amount: ₹{amount:.2f}\n"
            f"👥 Max Claims: {limit}",
            parse_mode="HTML"
        )
        await state.clear()
        return
    else:
        current += value
        if len(current) > 6:
            current = current[:6]

    await state.update_data(limit_str=current)

    # Rebuild keypad dynamically
    kb = InlineKeyboardBuilder()
    for row in (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("0", "❌", "✅")):
        kb.row(*[InlineKeyboardButton(text=btn, callback_data=f"cusredeemnum:{btn}") for btn in row])

    await cq.message.edit_text(
        f"👥 Select max number of users who can claim this custom code:\n<b>{current or '0'}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cq.answer()
        


# ================= Admin: View Redeems =================
@dp.message(Command("redeemlist"))
async def cmd_redeem_list(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    redeems = list(redeem_col.find())
    if not redeems:
        return await msg.answer("📭 No redeem codes found.")

    text = "🎟️ <b>Active Redeem Codes:</b>\n\n"
    for r in redeems:
        text += (
            f"Code: <code>{r['code']}</code>\n"
            f"💰 Amount: ₹{r['amount']}\n"
            f"👥 {r['claimed_count']} / {r['max_claims']} claimed\n\n"
        )
    await msg.answer(text, parse_mode="HTML")

# ================= User: Redeem Code =================
@dp.callback_query(F.data == "redeem")
async def callback_user_redeem(cq: CallbackQuery, state: FSMContext):
    await cq.answer("✅ Send your redeem code now!", show_alert=False)
    await cq.message.answer("🎟️ Send your redeem code below:")
    await state.set_state(UserRedeemState.waiting_code)

# Command /redeem
@dp.message(F.text == "/redeem")
async def command_user_redeem(message: Message, state: FSMContext):
    await message.answer("✅ Send your redeem code now!")
    await message.answer("🎟️ Send your redeem code below:")
    await state.set_state(UserRedeemState.waiting_code)

@dp.message(StateFilter(UserRedeemState.waiting_code))
async def handle_user_redeem(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    redeem = redeem_col.find_one({"code": code})

    if not redeem:
        await msg.answer("❌ Invalid or expired redeem code.")
        return await state.clear()

    if redeem["claimed_count"] >= redeem["max_claims"]:
        await msg.answer("🚫 This code has reached its claim limit.")
        return await state.clear()

    user = users_col.find_one({"_id": msg.from_user.id})
    if not user:
        await msg.answer("⚠️ Please use /start first.")
        return await state.clear()

    if msg.from_user.id in redeem.get("claimed_users", []):
        await msg.answer("⚠️ You have already claimed this code.")
        return await state.clear()

    # Credit user balance
    users_col.update_one({"_id": msg.from_user.id}, {"$inc": {"balance": redeem["amount"]}})
    redeem_col.update_one(
        {"code": code},
        {"$inc": {"claimed_count": 1}, "$push": {"claimed_users": msg.from_user.id}}
    )

    await msg.answer(
        f"✅ Code <b>{code}</b> redeemed successfully!\n💰 You received ₹{redeem['amount']:.2f}",
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(Command("editsell"))
async def cmd_editsell(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    await msg.answer("📋 Send the list in format:\n\n<code>USA ₹50\nIndia ₹10\nUK ₹20</code>")

    @dp.message()  # Next message from admin
    async def handle_sell_edit(m: Message):
        sell_rates_col.delete_many({})
        for line in m.text.splitlines():
            try:
                parts = line.split("₹")
                country = parts[0].strip()
                price = float(parts[1].strip())
                code = "+1" if "USA" in country else "+91" if "India" in country else ""  # add more or editable
                sell_rates_col.insert_one({"country": country, "price": price, "code": code})
            except:
                continue
        await m.answer("✅ Sell rates updated.")
        

# ================= Admin Broadcast (Forward Version - Aiogram Fix) =================
@dp.message(Command("broadcast"))
async def cmd_broadcast(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("❌ Not authorized.")

    if not msg.reply_to_message:
        return await msg.answer("⚠️ Reply to the message you want to broadcast with /broadcast.")

    broadcast_msg = msg.reply_to_message
    users = list(users_col.find({}))

    if not users:
        return await msg.answer("⚠️ No users found to broadcast.")

    sent_count = 0
    failed_count = 0

    for user in users:
        user_id = user["_id"]
        try:
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=broadcast_msg.chat.id,
                message_id=broadcast_msg.message_id
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to send to {user_id}: {e}")

    await msg.answer(f"✅ Broadcast completed!\n\nSent: {sent_count}\nFailed: {failed_count}")
    

# ===== Register External Handlers =====
register_recharge_handlers(dp=dp, bot=bot, users_col=users_col, txns_col=db["transactions"], ADMIN_IDS=ADMIN_IDS)
register_add_session_handlers(dp=dp, bot=bot)

# ===== Bot Runner =====
async def main():
    print("Bot started.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
