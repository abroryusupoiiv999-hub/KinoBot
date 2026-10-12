
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8730455671:AAEBfgAWkkRmz_jIQasn0wNxC7wHEezYwXg"
ADMIN_ID = 123456789  # O'zingning Telegram ID raqaming

bot = telebot.TeleBot(TOKEN)
db = sqlite3.connect("kino.db", check_same_thread=False)
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

states = {}


def is_admin(user_id):
    return user_id == ADMIN_ID


def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        "🎬 Kino kodini kiritish", callback_data="get_movie"))
    return kb


def admin_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Kino qo'shish", callback_data="add_movie"),
        InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_channel"),
        InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="movies"),
        InlineKeyboardButton("📡 Kanallar ro'yxati", callback_data="channels"),
        InlineKeyboardButton("👥 Foydalanuvchilar soni", callback_data="users")
    )
    return kb


def check_subscriptions(user_id):
    rows = db.execute("SELECT username FROM channels").fetchall()
    for (channel,) in rows:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            return False
    return True


def subscription_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    rows = db.execute("SELECT username FROM channels").fetchall()
    for (channel,) in rows:
        kb.add(InlineKeyboardButton(
            "📢 " + channel,
            url="https://t.me/" + channel.lstrip("@")
        ))
    kb.add(InlineKeyboardButton(
        "✅ Obunani tekshirish", callback_data="check_sub"))
    return kb


def ask_subscription(message):
    bot.send_message(
        message.chat.id,
        "🎬 Botdan foydalanish uchun avval quyidagi "
        "kanallarga obuna bo'ling:",
        reply_markup=subscription_menu()
    )


@bot.message_handler(commands=["myid"])
def myid(message):
    bot.reply_to(message, f"Telegram ID raqamingiz: {message.from_user.id}")


@bot.message_handler(commands=["start"])
def start(message):
    db.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )
    db.commit()

    if not check_subscriptions(message.from_user.id):
        ask_subscription(message)
        return

    bot.send_message(
        message.chat.id,
        "🎬 Kino botiga xush kelibsiz!\n\n"
        "Kerakli kino kodini yuboring.",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["admin"])
def admin(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Siz admin emassiz.")
        return
    states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id, "👑 Admin boshqaruv paneli:",
        reply_markup=admin_menu()
    )


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    data = call.data

    if data == "check_sub":
        if check_subscriptions(uid):
            bot.answer_callback_query(call.id, "Obuna tasdiqlandi!")
            bot.send_message(
                call.message.chat.id,
                "✅ Rahmat! Endi kino kodini yuboring."
            )
        else:
            bot.answer_callback_query(
                call.id, "Hali barcha kanallarga obuna bo'lmagansiz.",
                show_alert=True
            )
        return

    if data == "get_movie":
        if not check_subscriptions(uid):
            ask_subscription(call.message)
            bot.answer_callback_query(call.id)
            return
        bot.send_message(call.message.chat.id, "🔢 Kino kodini yuboring:")
        bot.answer_callback_query(call.id)
        return

    if not is_admin(uid):
        bot.answer_callback_query(call.id, "Bu bo'lim faqat admin uchun.")
        return

    if data == "add_movie":
        states[uid] = {"step": "code"}
        bot.send_message(call.message.chat.id, "Kino kodini yuboring:")
    elif data == "add_channel":
        states[uid] = {"step": "channel"}
        bot.send_message(
            call.message.chat.id,
            "Kanal username'ini yuboring. Masalan: @MeningKanalim\n"
            "Bot ushbu kanalga admin qilib qo'shilgan bo'lishi kerak."
        )
    elif data == "movies":
        rows = db.execute(
            "SELECT code, title FROM movies ORDER BY code"
        ).fetchall()
        if not rows:
            text = "Hozircha kino qo'shilmagan."
        else:
            text = "🎬 Kinolar:\n" + "\n".join(
                f"{code} — {title}" for code, title in rows
            )
        bot.send_message(call.message.chat.id, text)
    elif data == "channels":
        rows = db.execute(
            "SELECT username FROM channels ORDER BY username"
        ).fetchall()
        text = "📡 Kanallar:\n" + (
            "\n".join(row[0] for row in rows)
            if rows else "Hozircha kanal yo'q."
        )
        bot.send_message(call.message.chat.id, text)
    elif data == "users":
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(
            call.message.chat.id,
            f"👥 Bot foydalanuvchilari: {count}"
        )

    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=["text", "video", "photo"])
def handle_message(message):
    uid = message.from_user.id
    text = (message.text or "").strip()

    if text.startswith("/"):
        return

    # Adminning kino yoki kanal qo'shish jarayoni
    if is_admin(uid) and uid in states:
        state = states[uid]
        step = state["step"]

        if step == "channel":
            channel = text
            if not channel.startswith("@") or len(channel) < 2:
                bot.reply_to(
                    message, "Username @ bilan boshlansin. Masalan: @KinoKanal"
                )
                return

            try:
                bot.get_chat(channel)
                db.execute(
                    "INSERT OR IGNORE INTO channels(username) VALUES(?)",
                    (channel,)
                )
                db.commit()
                states.pop(uid, None)
                bot.reply_to(
                    message,
                    f"✅ Kanal saqlandi: {channel}\n"
                    "Botni kanalga admin qilib qo'ying va /admin ni bosing."
                )
            except Exception:
                bot.reply_to(
                    message,
                    "Kanal topilmadi. Username'ni tekshiring va botni "
                    "kanalga admin qilib qo'ying."
                )
            return

        if step == "code":
            if not text:
                bot.reply_to(message, "Kino kodi matn bo'lishi kerak.")
                return
            state["code"] = text
            state["step"] = "title"
            bot.reply_to(message, "Kino nomini yuboring:")
            return

        if step == "title":
            state["title"] = text
            state["step"] = "year"
            bot.reply_to(message, "Kino yilini yuboring:")
            return

        if step == "year":
            state["year"] = text
            state["step"] = "genre"
            bot.reply_to(message, "Kino janrini yuboring:")
            return

        if step == "genre":
            state["genre"] = text
            state["step"] = "description"
            bot.reply_to(message, "Kino haqida qisqacha ma'lumot yuboring:")
            return

        if step == "description":
            state["description"] = text
            state["step"] = "media"
            bot.reply_to(
                message,
                "Endi kino videosini yoki poster rasmini yuboring.\n"
                "Media qo'shmaslik uchun /skip yuboring."
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
                    message, "Video, rasm yoki /skip yuboring."
                )
                return

            try:
                db.execute("""
                    INSERT OR REPLACE INTO movies
                    (code, title, year, genre, description, media_type, media_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    state["code"], state["title"], state["year"],
                    state["genre"], state["description"],
                    media_type, media_id
                ))
                db.commit()
                bot.reply_to(
                    message,
                    f"✅ Kino saqlandi!\n"
                    f"Kod: {state['code']}\n"
                    f"Nomi: {state['title']}"
                )
            except Exception as e:
                bot.reply_to(message, f"Saqlashda xatolik: {e}")
            finally:
                states.pop(uid, None)
            return

    # Foydalanuvchilar uchun kino qidiruvi
    if not check_subscriptions(uid):
        ask_subscription(message)
        return

    if not text:
        bot.reply_to(message, "Kino topish uchun uning kodini yozing.")
        return

    row = db.execute("""
        SELECT code, title, year, genre, description, media_type, media_id
        FROM movies WHERE code = ?
    """, (text,)).fetchone()

    if not row:
        bot.reply_to(
            message,
            "❌ Bunday kodli kino topilmadi. Kodni qayta tekshiring."
        )
        return

    code, title, year, genre, description, media_type, media_id = row
    caption = (
        f"🎬 {title}\n"
        f"🔢 Kod: {code}\n"
        f"📅 Yil: {year}\n"
        f"🎭 Janr: {genre}\n\n"
        f"📝 {description}"
    )

    if media_type == "video" and media_id:
        bot.send_video(message.chat.id, media_id, caption=caption)
    elif media_type == "photo" and media_id:
        bot.send_photo(message.chat.id, media_id, caption=caption)
    else:
        bot.send_message(message.chat.id, caption)


print("🎬 Kino bot ishga tushdi!")
bot.infinity_polling(skip_pending=True)
