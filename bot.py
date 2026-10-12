
import os
import re
import sqlite3
import logging
import telebot

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ==========================================
# 🎬 Movieverse W bot — SOZLAMALAR
# ==========================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = 8813436066

if not TOKEN:
    raise SystemExit(
        "❌ BOT_TOKEN topilmadi. Tokenni terminalda sozlang."
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KinoBot")

bot = telebot.TeleBot(TOKEN)
db = sqlite3.connect("kino.db", check_same_thread=False)
db_lock = __import__("threading").RLock()

# ==========================================
# 🗄️ MA'LUMOTLAR BAZASI
# ==========================================

with db_lock:
    db.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT,
            year TEXT,
            genre TEXT,
            description TEXT,
            media_type TEXT,
            media_id TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            username TEXT PRIMARY KEY
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)

    db.commit()

# Har bir foydalanuvchining vaqtinchalik jarayoni
states = {}


def query(sql, params=()):
    with db_lock:
        return db.execute(sql, params).fetchall()


def execute(sql, params=()):
    with db_lock:
        db.execute(sql, params)
        db.commit()


def is_admin(user_id):
    return user_id == ADMIN_ID


def escape_text(value):
    """HTML formatidagi xabarlarda maxsus belgilarni xavfsizlashtiradi."""
    import html
    return html.escape(str(value or ""))


# ==========================================
# 🎨 ASOSIY MENYU
# ==========================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton(
            "🎬 Kino izlash", callback_data="get_movie"
        ),
        InlineKeyboardButton(
            "🍿 Yangi kinolar", callback_data="latest"
        )
    )

    kb.add(
        InlineKeyboardButton(
            "ℹ️ Yordam", callback_data="help"
        )
    )

    return kb


def admin_menu():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton(
            "➕ Kino qo‘shish", callback_data="add_movie"
        ),
        InlineKeyboardButton(
            "🗑 Kino o‘chirish", callback_data="delete_movie"
        )
    )

    kb.add(
        InlineKeyboardButton(
            "📚 Kinolar", callback_data="movies"
        ),
        InlineKeyboardButton(
            "📢 Kanal qo‘shish", callback_data="add_channel"
        )
    )

    kb.add(
        InlineKeyboardButton(
            "➖ Kanal o‘chirish", callback_data="remove_channel"
        ),
        InlineKeyboardButton(
            "📡 Kanallar", callback_data="channels"
        )
    )

    kb.add(
        InlineKeyboardButton(
            "👥 Statistika", callback_data="users"
        )
    )

    return kb


def back_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "🏠 Bosh menyu", callback_data="home"
        )
    )
    return kb


# ==========================================
# 📢 MAJBURIY OBUNA
# ==========================================

def check_subscriptions(user_id):
    channels = query(
        "SELECT username FROM channels ORDER BY username"
    )

    for (channel,) in channels:
        try:
            member = bot.get_chat_member(channel, user_id)

            if member.status not in (
                "member", "administrator", "creator"
            ):
                return False

            if getattr(member, "is_member", True) is False:
                return False

        except Exception:
            logger.warning(
                "Kanal obunasini tekshirish amalga oshmadi: %s",
                channel
            )
            return False

    return True


def subscription_menu():
    kb = InlineKeyboardMarkup(row_width=1)

    for (channel,) in query(
        "SELECT username FROM channels ORDER BY username"
    ):
        kb.add(
            InlineKeyboardButton(
                "📢 " + channel,
                url="https://t.me/" + channel.lstrip("@")
            )
        )

    kb.add(
        InlineKeyboardButton(
            "✅ Obunani tekshirish",
            callback_data="check_sub"
        )
    )

    return kb


def ask_subscription(chat_id):
    channels = query("SELECT username FROM channels")

    if not channels:
        bot.send_message(
            chat_id,
            "⚠️ Obuna tekshiruvi hozir ishlamayapti.\n"
            "Admin kanal va bot ruxsatlarini tekshirishi kerak."
        )
        return

    bot.send_message(
        chat_id,
        "🔐 <b>KINO OLAMIGA KIRISH</b>\n\n"
        "🎬 Kinolarni ko‘rish uchun avval quyidagi "
        "kanallarga obuna bo‘ling.\n\n"
        "1️⃣ Kanalga kiring.\n"
        "2️⃣ Obuna bo‘ling.\n"
        "3️⃣ «✅ Obunani tekshirish» tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=subscription_menu()
    )


# ==========================================
# 🎬 KINO KARTASI VA QIDIRUV
# ==========================================

def send_movie(chat_id, row):
    code, title, year, genre, description, media_type, media_id = row

    caption = (
        "🎬 <b>" + escape_text(title) + "</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔢 <b>Kod:</b> " + escape_text(code) + "\n"
        "📅 <b>Yil:</b> " + escape_text(year) + "\n"
        "🎭 <b>Janr:</b> " + escape_text(genre) + "\n\n"
        "📝 <b>Kino haqida:</b>\n"
        + escape_text(description)
        + "\n\n🍿 <i>Yoqimli tomosha!</i>"
    )

    try:
        if media_type == "video" and media_id:
            bot.send_video(
                chat_id,
                media_id,
                caption=caption,
                parse_mode="HTML"
            )

        elif media_type == "photo" and media_id:
            bot.send_photo(
                chat_id,
                media_id,
                caption=caption,
                parse_mode="HTML"
            )

        else:
            bot.send_message(
                chat_id,
                caption,
                parse_mode="HTML"
            )

    except Exception:
        logger.exception("Kino yuborishda xatolik")
        bot.send_message(
            chat_id,
            "⚠️ Kinoni yuborib bo‘lmadi. Keyinroq urinib ko‘ring."
        )


def find_movie(code):
    rows = query("""
        SELECT code, title, year, genre, description,
               media_type, media_id
        FROM movies WHERE code = ?
    """, (code.strip(),))

    return rows[0] if rows else None


# ==========================================
# 🚀 START VA YORDAM
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id

    execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (uid,)
    )

    states.pop(uid, None)

    if not check_subscriptions(uid):
        ask_subscription(message.chat.id)
        return

    name = escape_text(message.from_user.first_name or "Do‘stim")

    welcome = (
        "🎬 <b>MovieverseW boy</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Assalomu alaykum, <b>{name}</b>!\n\n"
        "🍿 <b>O‘z kinoteatringizga xush kelibsiz!</b>\n\n"
        "✨ <b>BOT IMKONIYATLARI</b>\n"
        "🎥 Kino va seriallarni kod orqali topish\n"
        "📚 Yangi qo‘shilgan kinolarni ko‘rish\n"
        "📝 Kino haqida ma’lumot olish\n"
        "⚡ Qulay va tezkor qidiruv\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>Kerakli bo‘limni tanlang!</b>\n\n"
        "💫 Yoqimli tomosha!"
    )

    bot.send_message(
        message.chat.id,
        welcome,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ <b>KINOBOT YORDAM</b>\n\n"
        "🎬 Kino olish uchun kino kodini yuboring.\n"
        "🍿 Yangi kinolar tugmasidan katalogni ko‘ring.\n"
        "🏠 /start — bosh menyu.\n"
        "❌ /cancel — joriy amalni bekor qilish.\n\n"
        "👑 Admin: /admin",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["cancel"])
def cancel(message):
    states.pop(message.from_user.id, None)
    bot.reply_to(
        message,
        "❌ Joriy amal bekor qilindi.",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["myid"])
def myid(message):
    bot.reply_to(
        message,
        f"🆔 Telegram ID: {message.from_user.id}"
    )


# ==========================================
# 👑 ADMIN PANELI
# ==========================================

@bot.message_handler(commands=["admin"])
def admin(message):
    uid = message.from_user.id

    if not is_admin(uid):
        bot.reply_to(message, "⛔ Bu bo‘lim faqat admin uchun.")
        return

    states.pop(uid, None)

    bot.send_message(
        message.chat.id,
        "👑 <b>KINOBOT PRO — ADMIN PANELI</b>\n\n"
        "Kerakli boshqaruv bo‘limini tanlang. 🛠",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


def show_movies(chat_id):
    rows = query(
        "SELECT code, title, year FROM movies ORDER BY title LIMIT 100"
    )

    if not rows:
        bot.send_message(chat_id, "📭 Hozircha kino yo‘q.")
        return

    text = "📚 <b>KINOLAR RO‘YXATI</b>\n\n"

    for code, title, year in rows:
        text += (
            f"🎬 {escape_text(title)}\n"
            f"🔢 Kod: <code>{escape_text(code)}</code>"
            f" | 📅 {escape_text(year)}\n\n"
        )

    if query("SELECT COUNT(*) FROM movies")[0][0] > 100:
        text += "ℹ️ Faqat dastlabki 100 ta kino ko‘rsatildi."

    bot.send_message(
        chat_id, text, parse_mode="HTML"
    )


# ==========================================
# 🔘 TUGMALAR
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if data == "check_sub":
        if check_subscriptions(uid):
            bot.send_message(
                chat_id,
                "✅ <b>Obuna tasdiqlandi!</b>\n"
                "🎬 Endi kinolarni qidirishingiz mumkin.",
                parse_mode="HTML",
                reply_markup=main_menu()
            )
        else:
            bot.send_message(
                chat_id,
                "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
                reply_markup=subscription_menu()
            )
        return

    if data == "home":
        if not check_subscriptions(uid):
            ask_subscription(chat_id)
            return

        bot.send_message(
            chat_id,
            "🏠 <b>BOSH MENYU</b>\nBo‘limni tanlang 👇",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        return

    if data == "get_movie":
        if not check_subscriptions(uid):
            ask_subscription(chat_id)
            return

        states[uid] = {"step": "search"}
        bot.send_message(
            chat_id,
            "🔎 <b>KINO QIDIRISH</b>\n\n"
            "🎬 Kino kodini yuboring.\n"
            "❌ Bekor qilish: /cancel",
            parse_mode="HTML"
        )
        return

    if data == "latest":
        if not check_subscriptions(uid):
            ask_subscription(chat_id)
            return

        rows = query("""
            SELECT code, title, year
            FROM movies ORDER BY rowid DESC LIMIT 10
        """)

        if not rows:
            bot.send_message(
                chat_id,
                "🍿 Hozircha kino qo‘shilmagan.",
                reply_markup=main_menu()
            )
            return

        kb = InlineKeyboardMarkup(row_width=1)

        for code, title, year in rows:
            kb.add(
                InlineKeyboardButton(
                    f"🎬 {title} ({year})",
                    callback_data="movie_" + code
                )
            )

        kb.add(
            InlineKeyboardButton(
                "🏠 Bosh menyu", callback_data="home"
            )
        )

        bot.send_message(
            chat_id,
            "🍿 <b>SO‘NGGI QO‘SHILGAN KINOLAR</b>\n\n"
            "Ko‘rmoqchi bo‘lgan kinoni tanlang:",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "help":
        bot.send_message(
            chat_id,
            "ℹ️ <b>QANDAY FOYDALANILADI?</b>\n\n"
            "1️⃣ «🎬 Kino izlash» tugmasini bosing.\n"
            "2️⃣ Kino kodini yuboring.\n"
            "3️⃣ Kino ma’lumotlarini oling.\n\n"
            "💡 Kodni bilsangiz, uni oddiy xabar sifatida "
            "ham yuborishingiz mumkin.\n\n"
            "❌ /cancel — amalni bekor qilish.",
            parse_mode="HTML",
            reply_markup=back_menu()
        )
        return

    if data.startswith("movie_"):
        if not check_subscriptions(uid):
            ask_subscription(chat_id)
            return

        code = data[len("movie_"):]

        if len(code) > 100:
            return

        row = find_movie(code)

        if row:
            send_movie(chat_id, row)
        else:
            bot.send_message(chat_id, "❌ Kino topilmadi.")

        return

    # Admin funksiyalari
    if not is_admin(uid):
        bot.send_message(chat_id, "⛔ Bu amal faqat admin uchun.")
        return

    if data == "add_movie":
        states[uid] = {"step": "code"}
        bot.send_message(
            chat_id,
            "➕ <b>YANGI KINO QO‘SHISH</b>\n\n"
            "1️⃣ Kino kodini yuboring.\n"
            "❌ Bekor qilish: /cancel",
            parse_mode="HTML"
        )

    elif data == "delete_movie":
        states[uid] = {"step": "delete_code"}
        bot.send_message(
            chat_id,
            "🗑 O‘chiriladigan kino kodini yuboring.\n"
            "❌ Bekor qilish: /cancel"
        )

    elif data == "add_channel":
        states[uid] = {"step": "channel"}
        bot.send_message(
            chat_id,
            "📢 Kanal username'ini yuboring.\n"
            "Masalan: @MeningKinoKanalim\n\n"
            "⚠️ Bot kanalda administrator bo‘lishi kerak."
        )

    elif data == "remove_channel":
        channels = query(
            "SELECT username FROM channels ORDER BY username"
        )

        if not channels:
            bot.send_message(chat_id, "📭 Saqlangan kanal yo‘q.")
            return

        kb = InlineKeyboardMarkup(row_width=1)

        for (channel,) in channels:
            kb.add(
                InlineKeyboardButton(
                    "🗑 " + channel,
                    callback_data="rmch_" + channel
                )
            )

        bot.send_message(
            chat_id,
            "➖ O‘chirmoqchi bo‘lgan kanalni tanlang:",
            reply_markup=kb
        )

    elif data.startswith("rmch_"):
        channel = data[len("rmch_"):]

        if query(
            "SELECT username FROM channels WHERE username = ?",
            (channel,)
        ):
            execute(
                "DELETE FROM channels WHERE username = ?",
                (channel,)
            )
            bot.send_message(
                chat_id, f"✅ Kanal o‘chirildi: {channel}"
            )
        else:
            bot.send_message(chat_id, "❌ Kanal topilmadi.")

    elif data == "movies":
        show_movies(chat_id)

    elif data == "channels":
        channels = query(
            "SELECT username FROM channels ORDER BY username"
        )

        text = "📡 <b>KANALLAR RO‘YXATI</b>\n\n"

        if channels:
            text += "\n".join(
                "📢 " + escape_text(row[0])
                for row in channels
            )
        else:
            text += "Hozircha kanal qo‘shilmagan."

        bot.send_message(
            chat_id, text, parse_mode="HTML"
        )

    elif data == "users":
        user_count = query(
            "SELECT COUNT(*) FROM users"
        )[0][0]

        movie_count = query(
            "SELECT COUNT(*) FROM movies"
        )[0][0]

        channel_count = query(
            "SELECT COUNT(*) FROM channels"
        )[0][0]

        bot.send_message(
            chat_id,
            "📊 <b>KINOBOT STATISTIKASI</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{user_count}</b>\n"
            f"🎬 Kinolar: <b>{movie_count}</b>\n"
            f"📢 Kanallar: <b>{channel_count}</b>\n\n"
            "🚀 KinoBot PRO",
            parse_mode="HTML"
        )


# ==========================================
# ✍️ MATN, KINO VA MEDIA QABUL QILISH
# ==========================================

@bot.message_handler(
    content_types=["text", "video", "photo"]
)
def handle_message(message):
    uid = message.from_user.id
    text = (message.text or "").strip()

    if text.startswith("/"):
        return

    # Foydalanuvchi jarayonlari
    state = states.get(uid)

    if state and state.get("step") == "search":
        if not check_subscriptions(uid):
            ask_subscription(message.chat.id)
            return

        if not text:
            bot.reply_to(
                message,
                "🔢 Iltimos, kino kodini matn ko‘rinishida yuboring."
            )
            return

        row = find_movie(text)
        states.pop(uid, None)

        if row:
            send_movie(message.chat.id, row)
        else:
            bot.reply_to(
                message,
                "❌ <b>Kino topilmadi.</b>\n\n"
                "🔎 Kodni tekshiring yoki /start orqali "
                "bosh menyuga qayting.",
                parse_mode="HTML"
            )
        return

    # Adminning kino yoki kanal boshqaruvi
    if is_admin(uid) and state:
        step = state.get("step")

        if step == "channel":
            channel = text

            if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", channel):
                bot.reply_to(
                    message,
                    "❌ Username noto‘g‘ri.\n"
                    "Masalan: @MeningKinoKanalim"
                )
                return

            try:
                chat = bot.get_chat(channel)

                if chat.type != "channel":
                    bot.reply_to(
                        message,
                        "❌ Bu username Telegram kanaliga tegishli emas."
                    )
                    return

                me = bot.get_me()
                member = bot.get_chat_member(chat.id, me.id)

                if member.status not in ("administrator", "creator"):
                    bot.reply_to(
                        message,
                        "⚠️ Avval botni kanalga administrator qiling."
                    )
                    return

                execute(
                    "INSERT OR IGNORE INTO channels(username) VALUES(?)",
                    (channel,)
                )

                states.pop(uid, None)

                bot.reply_to(
                    message,
                    f"✅ Kanal muvaffaqiyatli saqlandi: {channel}\n\n"
                    "📢 Endi foydalanuvchilar obunani tekshirishi mumkin."
                )

            except Exception:
                logger.exception("Kanalni qo‘shishda xatolik")
                bot.reply_to(
                    message,
                    "❌ Kanalni tekshirib bo‘lmadi.\n"
                    "Username to‘g‘riligini va bot admin ekanini tekshiring."
                )
            return

        if step == "delete_code":
            if not text:
                bot.reply_to(message, "Kino kodini matn qilib yuboring.")
                return

            row = find_movie(text)

            if not row:
                bot.reply_to(message, "❌ Bu kodli kino topilmadi.")
                return

            execute("DELETE FROM movies WHERE code = ?", (text,))
            states.pop(uid, None)

            bot.reply_to(
                message,
                f"🗑 Kino o‘chirildi: {row[1]}\n"
                f"🔢 Kod: {text}"
            )
            return

        if step == "code":
            if not text or len(text) > 100:
                bot.reply_to(
                    message,
                    "❌ Kino kodi 1–100 belgidan iborat matn bo‘lsin."
                )
                return

            state["code"] = text
            state["step"] = "title"

            bot.reply_to(message, "🎬 Kino nomini yuboring:")
            return

        if step == "title":
            if not text or len(text) > 200:
                bot.reply_to(message, "Kino nomini to‘g‘ri yuboring.")
                return

            state["title"] = text
            state["step"] = "year"

            bot.reply_to(message, "📅 Kino yilini yuboring:")
            return

        if step == "year":
            state["year"] = text[:30] or "Noma'lum"
            state["step"] = "genre"

            bot.reply_to(message, "🎭 Kino janrini yuboring:")
            return

        if step == "genre":
            state["genre"] = text[:150] or "Noma'lum"
            state["step"] = "description"

            bot.reply_to(
                message,
                "📝 Kino haqida qisqacha ma’lumot yuboring:"
            )
            return

        if step == "description":
            if not text:
                bot.reply_to(
                    message,
                    "Iltimos, kino tavsifini matn qilib yuboring."
                )
                return

            state["description"] = text[:2500]
            state["step"] = "media"

            bot.reply_to(
                message,
                "🎥 Endi kino videosini yoki poster rasmini yuboring.\n\n"
                "⏭ Media qo‘shmaslik uchun /skip yuboring."
            )
            return

        if step == "media":
            media_type = None
            media_id = None

            if text == "/skip":
                pass
            elif message.video:
                media_type = "video"
                media_id = message.video.file_id
            elif message.photo:
                media_type = "photo"
                media_id = message.photo[-1].file_id
            else:
                bot.reply_to(
                    message,
                    "❌ Video, rasm yoki /skip yuboring."
                )
                return

            try:
                execute("""
                    INSERT OR REPLACE INTO movies
                    (code, title, year, genre, description,
                     media_type, media_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    state["code"],
                    state["title"],
                    state["year"],
                    state["genre"],
                    state["description"],
                    media_type,
                    media_id
                ))

                bot.reply_to(
                    message,
                    "🎉 <b>KINO MUVAFFAQIYATLI SAQLANDI!</b>\n\n"
                    f"🎬 Nomi: {escape_text(state['title'])}\n"
                    f"🔢 Kodi: <code>{escape_text(state['code'])}</code>\n"
                    "📚 Kino katalogga qo‘shildi.",
                    parse_mode="HTML",
                    reply_markup=admin_menu()
                )

            except Exception:
                logger.exception("Kinoni saqlashda xatolik")
                bot.reply_to(
                    message,
                    "❌ Saqlashda xatolik yuz berdi."
                )
            finally:
                states.pop(uid, None)

            return

    # Oddiy foydalanuvchining kod yuborishi
    if not check_subscriptions(uid):
        ask_subscription(message.chat.id)
        return

    if not text:
        bot.reply_to(
            message,
            "🎬 Kino topish uchun kino kodini yuboring."
        )
        return

    row = find_movie(text)

    if row:
        send_movie(message.chat.id, row)
    else:
        bot.reply_to(
            message,
            "❌ Bunday kodli kino topilmadi.\n\n"
            "💡 Kodni tekshiring yoki /start ni bosing."
        )


# ==========================================
# 🚀 ISHGA TUSHIRISH
# ==========================================

print("🎬 KinoBot PRO ishga tushmoqda...")

try:
    bot.infinity_polling(skip_pending=True)
finally:
    db.close()
