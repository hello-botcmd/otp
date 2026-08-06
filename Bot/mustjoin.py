from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import MUST_JOIN_CHANNEL

# Private channel details
PRIVATE_CHANNEL_ID = -1003369972722
PRIVATE_CHANNEL_LINK = "https://t.me/TgAltSupport"

# Welcome text with HTML formatting
WELCOME_TEXT = (
    '𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝗍𝗈 ᴛɢ ᴀᴄᴄᴏᴜɴᴛ ʀᴏʙᴏᴛ'
    '<a href="https://files.catbox.moe/a3o6j9.jpg">🤖</a>\n'
    '<blockquote expandable>𝖳𝗈 𝗎𝗌𝖾 𝗈𝗎𝗋 𝖮𝖳𝖯 𝖡𝗈𝗍, 𝗒𝗈𝗎 𝗆𝗎𝗌𝗍 𝗃𝗈𝗂𝗇 𝗈𝗎𝗋 𝖢𝗁𝖺𝗇𝗇𝖾𝗅𝗌 '
    '𝖿𝗈𝗋 𝗎𝗉𝖽𝖺𝗍𝖾𝗌 𝖺𝗇𝖽 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 ❤️</blockquote>\n'
    '<blockquote>𝖠𝖿𝗍𝖾𝗋 𝖩𝗈𝗂𝗇𝗂𝗇𝗀, /start 𝗍𝗁𝖾 𝖻𝗈𝗍 🤖</blockquote>'
)


async def check_join(client, message: types.Message):
    """
    Check if the user has joined both required channels.
    If not, send the join message and return False.
    """
    try:
        # Public channel check
        member1 = await client.get_chat_member(MUST_JOIN_CHANNEL, message.from_user.id)

        # Private channel check
        member2 = await client.get_chat_member(PRIVATE_CHANNEL_ID, message.from_user.id)

        if (member1.status in ["left", "kicked"]) or (member2.status in ["left", "kicked"]):
            await send_join_message(message)
            return False

        return True
    except Exception:
        await send_join_message(message)
        return False


async def send_join_message(message: types.Message):
    """
    Send a message asking the user to join the required channels,
    with inline buttons for both channels in one row and Verify below.
    """
    kb = InlineKeyboardBuilder()

    # First row: both channels
    kb.row(
        types.InlineKeyboardButton(text="📢 𝖴𝗉𝖽𝖺𝗍𝖾𝗌", url=f"https://t.me/{MUST_JOIN_CHANNEL.replace('@', '')}"),
        types.InlineKeyboardButton(text="💌 𝖲𝗎𝗉𝗉𝗈𝗋𝗍 ", url=PRIVATE_CHANNEL_LINK)
    )

    

    await message.answer(
        WELCOME_TEXT,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
