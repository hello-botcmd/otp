import os
import io
import zipfile
import asyncio
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pymongo import MongoClient
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import BOT_TOKEN, ADMIN_IDS, API_ID, API_HASH

MONGO_URI = os.getenv("MONGO_URI") or "mongodb+srv://accountBot:Stalker123@accountbot.ba4pyd0.mongodb.net/?appName=AccountBot"
client = MongoClient(MONGO_URI)
db = client["QuickCodes"]
countries_col = db["countries"]
numbers_col = db["numbers"]


class AddSessionStates(StatesGroup):
    waiting_country = State()
    waiting_price = State()
    waiting_input_type = State()
    waiting_session_strings = State()
    waiting_session_file = State()
    waiting_zip_file = State()
    waiting_number_input = State()


def register_add_session_handlers(dp: Dispatcher, bot: Bot):
    def is_admin(user_id: int) -> bool:
        return user_id in ADMIN_IDS

    @dp.message(Command("addsession"))
    async def cmd_add_session(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Not authorized")
        
        countries = list(countries_col.find({}))
        if not countries:
            return await msg.answer("No countries available. Use /addcountry first.")
        
        kb = InlineKeyboardBuilder()
        for c in countries:
            kb.button(text=c["name"], callback_data=f"sess_country:{c['name']}")
        kb.adjust(2)
        kb.row(InlineKeyboardButton(text="+ Add New Country", callback_data="sess_new_country"))
        
        await state.set_state(AddSessionStates.waiting_country)
        await msg.answer("Select country for adding sessions:", reply_markup=kb.as_markup())

    @dp.callback_query(F.data.startswith("sess_country:"), AddSessionStates.waiting_country)
    async def select_country(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        _, country_name = cq.data.split(":", 1)
        
        country = countries_col.find_one({"name": country_name})
        if country:
            await state.update_data(country=country_name, price=country.get("price", 0))
            await show_input_options(cq.message, state, country_name, country.get("price", 0), is_callback=True)
        else:
            await state.update_data(country=country_name)
            await state.set_state(AddSessionStates.waiting_price)
            await cq.message.edit_text(f"Enter price for {country_name} accounts (in Rs):")

    @dp.callback_query(F.data == "sess_new_country", AddSessionStates.waiting_country)
    async def new_country(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await cq.message.edit_text("Enter new country name:")
        await state.set_state(AddSessionStates.waiting_country)
        await state.update_data(new_country=True)

    @dp.message(AddSessionStates.waiting_country)
    async def receive_new_country(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return
        
        country_name = msg.text.strip()
        await state.update_data(country=country_name, new_country=True)
        await state.set_state(AddSessionStates.waiting_price)
        await msg.answer(f"Enter price for {country_name} accounts (in Rs):")

    @dp.message(AddSessionStates.waiting_price)
    async def receive_price(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return
        
        try:
            price = float(msg.text.strip())
        except ValueError:
            return await msg.answer("Invalid price. Please enter a number:")
        
        data = await state.get_data()
        country_name = data["country"]
        
        existing = countries_col.find_one({"name": country_name})
        if not existing:
            countries_col.insert_one({"name": country_name, "price": price, "stock": 0})
        else:
            countries_col.update_one({"name": country_name}, {"$set": {"price": price}})
        
        await state.update_data(price=price)
        await show_input_options(msg, state, country_name, price)

    async def show_input_options(msg_or_cq, state: FSMContext, country: str, price: float, is_callback: bool = False):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Session Strings (comma-separated)", callback_data="input_strings")],
            [InlineKeyboardButton(text="Upload .session File", callback_data="input_session_file")],
            [InlineKeyboardButton(text="Upload .zip with Sessions", callback_data="input_zip")],
            [InlineKeyboardButton(text="Add by Number (manual)", callback_data="input_number")],
            [InlineKeyboardButton(text="Cancel", callback_data="cancel_add_session")]
        ])
        
        text = (
            f"<b>Adding accounts to:</b>\n"
            f"Country: {country}\n"
            f"Price: Rs {price}\n\n"
            f"Choose input method:"
        )
        
        await state.set_state(AddSessionStates.waiting_input_type)
        
        if is_callback:
            await msg_or_cq.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await msg_or_cq.answer(text, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query(F.data == "input_strings", AddSessionStates.waiting_input_type)
    async def choose_strings(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await state.set_state(AddSessionStates.waiting_session_strings)
        await cq.message.edit_text(
            "Send session strings.\n\n"
            "Format: string1, string2, string3\n"
            "OR send each on a new line.\n\n"
            "You can also include numbers like:\n"
            "number1:session1, number2:session2"
        )

    @dp.callback_query(F.data == "input_session_file", AddSessionStates.waiting_input_type)
    async def choose_session_file(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await state.set_state(AddSessionStates.waiting_session_file)
        await cq.message.edit_text("Send a .session file (one at a time).\nYou can send multiple files one by one.")

    @dp.callback_query(F.data == "input_zip", AddSessionStates.waiting_input_type)
    async def choose_zip(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await state.set_state(AddSessionStates.waiting_zip_file)
        await cq.message.edit_text("Send a .zip file containing .session files.\nAll sessions in the zip will be added.")

    @dp.callback_query(F.data == "input_number", AddSessionStates.waiting_input_type)
    async def choose_number(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await state.set_state(AddSessionStates.waiting_number_input)
        await cq.message.edit_text(
            "Send number and session string.\n\n"
            "Format: +1234567890 session_string_here\n\n"
            "Or just the number to generate session via OTP flow."
        )

    @dp.callback_query(F.data == "cancel_add_session")
    async def cancel_add(cq: CallbackQuery, state: FSMContext):
        await cq.answer("Cancelled")
        await state.clear()
        await cq.message.edit_text("Session adding cancelled.")

    @dp.message(AddSessionStates.waiting_session_strings)
    async def receive_session_strings(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return
        
        data = await state.get_data()
        country = data["country"]
        price = data["price"]
        
        text = msg.text.strip()
        entries = []
        
        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
        else:
            parts = [p.strip() for p in text.split("\n") if p.strip()]
        
        added = 0
        errors = []
        
        for part in parts:
            try:
                if ":" in part:
                    number, session = part.split(":", 1)
                    number = number.strip()
                    session = session.strip()
                else:
                    session = part.strip()
                    number = await extract_number_from_session(session)
                
                if not session:
                    continue
                
                existing = numbers_col.find_one({"string_session": session})
                if existing:
                    errors.append(f"Session already exists for {existing.get('number', 'unknown')}")
                    continue
                
                if number:
                    existing_num = numbers_col.find_one({"number": number})
                    if existing_num:
                        numbers_col.update_one(
                            {"number": number},
                            {"$set": {"string_session": session, "country": country, "price": price, "used": False}}
                        )
                        added += 1
                        continue
                
                numbers_col.insert_one({
                    "country": country,
                    "number": number or f"unknown_{datetime.now(timezone.utc).timestamp()}",
                    "string_session": session,
                    "price": price,
                    "used": False,
                    "added_at": datetime.now(timezone.utc)
                })
                added += 1
                
            except Exception as e:
                errors.append(str(e))
        
        countries_col.update_one({"name": country}, {"$inc": {"stock": added}})
        
        result_text = f"Added {added} session(s) to {country}"
        if errors:
            result_text += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                result_text += f"\n...and {len(errors) - 5} more"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Add More", callback_data="add_more_sessions")],
            [InlineKeyboardButton(text="Done", callback_data="done_adding")]
        ])
        
        await msg.answer(result_text, reply_markup=kb)

    @dp.message(AddSessionStates.waiting_session_file, F.document)
    async def receive_session_file(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return
        
        doc = msg.document
        if not doc.file_name.endswith(".session"):
            return await msg.answer("Please send a .session file")
        
        data = await state.get_data()
        country = data["country"]
        price = data["price"]
        
        try:
            file = await bot.get_file(doc.file_id)
            file_data = await bot.download_file(file.file_path)
            
            session_content = file_data.read()
            
            number = doc.file_name.replace(".session", "").strip()
            if not number.startswith("+"):
                number = "+" + number
            
            session_string = await convert_session_file_to_string(session_content, number)
            
            if session_string:
                existing = numbers_col.find_one({"number": number})
                if existing:
                    numbers_col.update_one(
                        {"number": number},
                        {"$set": {"string_session": session_string, "country": country, "price": price, "used": False}}
                    )
                else:
                    numbers_col.insert_one({
                        "country": country,
                        "number": number,
                        "string_session": session_string,
                        "price": price,
                        "used": False,
                        "added_at": datetime.now(timezone.utc)
                    })
                    countries_col.update_one({"name": country}, {"$inc": {"stock": 1}})
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Send Another File", callback_data="send_another_file")],
                    [InlineKeyboardButton(text="Done", callback_data="done_adding")]
                ])
                await msg.answer(f"Added session for {number} to {country}", reply_markup=kb)
            else:
                temp_path = f"/tmp/{doc.file_name}"
                with open(temp_path, "wb") as f:
                    f.write(session_content)
                
                existing = numbers_col.find_one({"number": number})
                if existing:
                    numbers_col.update_one(
                        {"number": number},
                        {"$set": {"session_file": temp_path, "country": country, "price": price, "used": False}}
                    )
                else:
                    numbers_col.insert_one({
                        "country": country,
                        "number": number,
                        "session_file": temp_path,
                        "price": price,
                        "used": False,
                        "added_at": datetime.now(timezone.utc)
                    })
                    countries_col.update_one({"name": country}, {"$inc": {"stock": 1}})
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Send Another File", callback_data="send_another_file")],
                    [InlineKeyboardButton(text="Done", callback_data="done_adding")]
                ])
                await msg.answer(f"Added session file for {number} to {country}", reply_markup=kb)
                
        except Exception as e:
            await msg.answer(f"Error processing file: {e}")

    @dp.message(AddSessionStates.waiting_zip_file, F.document)
    async def receive_zip_file(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return
        
        doc = msg.document
        if not doc.file_name.endswith(".zip"):
            return await msg.answer("Please send a .zip file")
        
        data = await state.get_data()
        country = data["country"]
        price = data["price"]
        
        try:
            file = await bot.get_file(doc.file_id)
            file_data = await bot.download_file(file.file_path)
            
            zip_bytes = io.BytesIO(file_data.read())
            
            added = 0
            errors = []
            
            with zipfile.ZipFile(zip_bytes, 'r') as zf:
                session_files = [f for f in zf.namelist() if f.endswith(".session")]
                
                await msg.answer(f"Found {len(session_files)} session file(s) in zip. Processing...")
                
                for filename in session_files:
                    try:
                        session_content = zf.read(filename)
                        
                        number = os.path.basename(filename).replace(".session", "").strip()
                        if not number.startswith("+"):
                            number = "+" + number
                        
                        session_string = await convert_session_file_to_string(session_content, number)
                        
                        existing = numbers_col.find_one({"number": number})
                        
                        if session_string:
                            if existing:
                                numbers_col.update_one(
                                    {"number": number},
                                    {"$set": {"string_session": session_string, "country": country, "price": price, "used": False}}
                                )
                            else:
                                numbers_col.insert_one({
                                    "country": country,
                                    "number": number,
                                    "string_session": session_string,
                                    "price": price,
                                    "used": False,
                                    "added_at": datetime.now(timezone.utc)
                                })
                            added += 1
                        else:
                            temp_path = f"/tmp/{os.path.basename(filename)}"
                            with open(temp_path, "wb") as f:
                                f.write(session_content)
                            
                            if existing:
                                numbers_col.update_one(
                                    {"number": number},
                                    {"$set": {"session_file": temp_path, "country": country, "price": price, "used": False}}
                                )
                            else:
                                numbers_col.insert_one({
                                    "country": country,
                                    "number": number,
                                    "session_file": temp_path,
                                    "price": price,
                                    "used": False,
                                    "added_at": datetime.now(timezone.utc)
                                })
                            added += 1
                            
                    except Exception as e:
                        errors.append(f"{filename}: {str(e)}")
            
            countries_col.update_one({"name": country}, {"$inc": {"stock": added}})
            
            result_text = f"Added {added} session(s) from zip to {country}"
            if errors:
                result_text += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    result_text += f"\n...and {len(errors) - 5} more"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Add More", callback_data="add_more_sessions")],
                [InlineKeyboardButton(text="Done", callback_data="done_adding")]
            ])
            
            await msg.answer(result_text, reply_markup=kb)
            
        except Exception as e:
            await msg.answer(f"Error processing zip: {e}")

    @dp.message(AddSessionStates.waiting_number_input)
    async def receive_number_input(msg: Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            return
        
        data = await state.get_data()
        country = data["country"]
        price = data["price"]
        
        text = msg.text.strip()
        parts = text.split(maxsplit=1)
        
        if len(parts) == 2:
            number, session = parts
            number = number.strip()
            session = session.strip()
            
            existing = numbers_col.find_one({"number": number})
            if existing:
                numbers_col.update_one(
                    {"number": number},
                    {"$set": {"string_session": session, "country": country, "price": price, "used": False}}
                )
                await msg.answer(f"Updated session for {number}")
            else:
                numbers_col.insert_one({
                    "country": country,
                    "number": number,
                    "string_session": session,
                    "price": price,
                    "used": False,
                    "added_at": datetime.now(timezone.utc)
                })
                countries_col.update_one({"name": country}, {"$inc": {"stock": 1}})
                await msg.answer(f"Added {number} to {country}")
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Add Another", callback_data="input_number_again")],
                [InlineKeyboardButton(text="Done", callback_data="done_adding")]
            ])
            await msg.answer("What next?", reply_markup=kb)
        else:
            await msg.answer("Format: +1234567890 session_string_here")

    @dp.callback_query(F.data == "add_more_sessions")
    async def add_more(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        data = await state.get_data()
        await show_input_options(cq.message, state, data["country"], data["price"], is_callback=True)

    @dp.callback_query(F.data == "send_another_file")
    async def send_another(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await state.set_state(AddSessionStates.waiting_session_file)
        await cq.message.edit_text("Send another .session file:")

    @dp.callback_query(F.data == "input_number_again")
    async def input_number_again(cq: CallbackQuery, state: FSMContext):
        await cq.answer()
        await state.set_state(AddSessionStates.waiting_number_input)
        await cq.message.edit_text("Send number and session string:\nFormat: +1234567890 session_string")

    @dp.callback_query(F.data == "done_adding")
    async def done_adding(cq: CallbackQuery, state: FSMContext):
        await cq.answer("Done!")
        await state.clear()
        await cq.message.edit_text("Session adding completed.")


async def extract_number_from_session(session_string: str) -> str:
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            await client.disconnect()
            return me.phone if me.phone else ""
        await client.disconnect()
    except:
        pass
    return ""


async def convert_session_file_to_string(session_content: bytes, phone: str) -> str:
    try:
        temp_path = f"/tmp/temp_session_{phone.replace('+', '')}"
        with open(temp_path + ".session", "wb") as f:
            f.write(session_content)
        
        client = TelegramClient(temp_path, API_ID, API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            string_session = client.session.save()
            await client.disconnect()
            
            try:
                os.remove(temp_path + ".session")
            except:
                pass
            
            return string_session
        
        await client.disconnect()
    except Exception as e:
        print(f"Error converting session: {e}")
    
    return ""
