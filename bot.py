import os
import csv
import html
import logging
import re
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
COMPANY = os.getenv("COMPANY_NAME", "EstateFlow AI").strip() or "EstateFlow AI"
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
DB = os.getenv("DB_PATH", "estateflow.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("estateflow")

TYPE, BUDGET, DISTRICT, ROOMS, TIMELINE, PHONE, CONFIRM = range(7)

TEXT = {
    "ru": {
        "welcome": "Здравствуйте! 👋\nЯ <b>EstateFlow AI</b> — помогу быстро подобрать недвижимость в Ташкенте.",
        "language": "Выберите язык:",
        "type": "🏠 <b>Что вы ищете?</b>",
        "budget": "💰 <b>Какой максимальный бюджет?</b>\n\nНапишите сумму, например: <code>120000</code>, <code>120 000</code> или <code>$120,000</code>.",
        "district": "📍 <b>Какой район предпочитаете?</b>",
        "rooms": "🚪 <b>Сколько комнат нужно?</b>",
        "timeline": "📅 <b>Когда планируете покупку?</b>",
        "summary": "📋 <b>Проверьте заявку</b>\n\n🏠 {property_type}\n💰 ${budget}\n📍 {district}\n🚪 {rooms}\n📅 {timeline}\n\nВсё верно?",
        "phone": "📞 <b>Оставьте номер телефона</b>\n\nМенеджер получит заявку и свяжется с вами с подходящими вариантами.",
        "done": "Спасибо! ✅\n\n<b>Заявка принята.</b> Менеджер свяжется с вами в ближайшее время.",
        "cancel": "Заявка отменена. Нажмите /start, чтобы начать заново.",
        "invalid_budget": "⚠️ Не удалось распознать бюджет.\nВведите только сумму, например <code>120000</code>.",
        "invalid_phone": "⚠️ Пожалуйста, используйте кнопку отправки номера или формат <code>+998901234567</code>.",
        "help": "Я помогу подобрать недвижимость, соберу ваши требования и передам заявку менеджеру.\n\n/start — новая заявка\n/myid — ваш Telegram ID",
        "cancel_button": "❌ Отмена",
        "back_button": "⬅️ Назад",
        "confirm": "✅ Всё верно",
        "edit": "✏️ Изменить",
        "share_phone": "📞 Поделиться номером",
        "types": [["🏢 Квартира", "🏡 Дом"], ["🏬 Коммерция", "🌳 Участок"]],
        "rooms": [["1", "2", "3"], ["4", "5+"], ["Не важно"]],
        "timeline": [["🔥 Срочно", "1–3 месяца"], ["3–6 месяцев", "Пока смотрю"]],
        "districts": [["Мирабад", "Юнусабад"], ["Яккасарай", "Шайхантахур"], ["Чиланзар", "Мирзо-Улугбек"], ["Другой район"]],
    },
    "uz": {
        "welcome": "Assalomu alaykum! 👋\nMen <b>EstateFlow AI</b> — Toshkentdagi ko‘chmas mulkni tez topishga yordam beraman.",
        "language": "Tilni tanlang:",
        "type": "🏠 <b>Nima qidiryapsiz?</b>",
        "budget": "💰 <b>Maksimal byudjetingiz qancha?</b>\n\nMasalan: <code>120000</code> yoki <code>120 000</code>.",
        "district": "📍 <b>Qaysi tumanni afzal ko‘rasiz?</b>",
        "rooms": "🚪 <b>Nechta xona kerak?</b>",
        "timeline": "📅 <b>Qachon xarid qilishni rejalashtiryapsiz?</b>",
        "summary": "📋 <b>So‘rovingizni tekshiring</b>\n\n🏠 {property_type}\n💰 ${budget}\n📍 {district}\n🚪 {rooms}\n📅 {timeline}\n\nHammasi to‘g‘rimi?",
        "phone": "📞 <b>Telefon raqamingizni qoldiring</b>\n\nMenejer so‘rovingizni olib, mos variantlar bilan bog‘lanadi.",
        "done": "Rahmat! ✅\n\n<b>So‘rovingiz qabul qilindi.</b> Menejer tez orada bog‘lanadi.",
        "cancel": "So‘rov bekor qilindi. Qayta boshlash uchun /start bosing.",
        "invalid_budget": "⚠️ Byudjetni aniqlab bo‘lmadi.\nMasalan <code>120000</code> kiriting.",
        "invalid_phone": "⚠️ Raqamni tugma orqali yuboring yoki <code>+998901234567</code> formatidan foydalaning.",
        "help": "Men ko‘chmas mulk talablarini yig‘ib, menejerga yuboraman.\n\n/start — yangi so‘rov\n/myid — Telegram ID",
        "cancel_button": "❌ Bekor qilish",
        "back_button": "⬅️ Orqaga",
        "confirm": "✅ Hammasi to‘g‘ri",
        "edit": "✏️ O‘zgartirish",
        "share_phone": "📞 Raqamni yuborish",
        "types": [["🏢 Kvartira", "🏡 Uy"], ["🏬 Tijorat", "🌳 Yer"]],
        "rooms": [["1", "2", "3"], ["4", "5+"], ["Farqi yo‘q"]],
        "timeline": [["🔥 Shoshilinch", "1–3 oy"], ["3–6 oy", "Hozircha ko‘ryapman"]],
        "districts": [["Mirobod", "Yunusobod"], ["Yakkasaroy", "Shayxontohur"], ["Chilonzor", "Mirzo Ulug‘bek"], ["Boshqa tuman"]],
    },
    "en": {
        "welcome": "Hello! 👋\nI'm <b>EstateFlow AI</b> — I'll help you find property in Tashkent quickly.",
        "language": "Choose your language:",
        "type": "🏠 <b>What are you looking for?</b>",
        "budget": "💰 <b>What is your maximum budget?</b>\n\nExample: <code>120000</code>, <code>120 000</code> or <code>$120,000</code>.",
        "district": "📍 <b>Which district do you prefer?</b>",
        "rooms": "🚪 <b>How many rooms do you need?</b>",
        "timeline": "📅 <b>When are you planning to buy?</b>",
        "summary": "📋 <b>Check your request</b>\n\n🏠 {property_type}\n💰 ${budget}\n📍 {district}\n🚪 {rooms}\n📅 {timeline}\n\nIs everything correct?",
        "phone": "📞 <b>Share your phone number</b>\n\nA manager will receive your request and contact you with matching options.",
        "done": "Thank you! ✅\n\n<b>Your request has been received.</b> A manager will contact you shortly.",
        "cancel": "Request cancelled. Press /start to begin again.",
        "invalid_budget": "⚠️ I couldn't read the budget.\nEnter an amount such as <code>120000</code>.",
        "invalid_phone": "⚠️ Share your phone with the button or use <code>+998901234567</code>.",
        "help": "I collect property requirements and send the lead to a manager.\n\n/start — new request\n/myid — Telegram ID",
        "cancel_button": "❌ Cancel",
        "back_button": "⬅️ Back",
        "confirm": "✅ Looks good",
        "edit": "✏️ Change",
        "share_phone": "📞 Share phone number",
        "types": [["🏢 Apartment", "🏡 House"], ["🏬 Commercial", "🌳 Land"]],
        "rooms": [["1", "2", "3"], ["4", "5+"], ["Any"]],
        "timeline": [["🔥 Urgent", "1–3 months"], ["3–6 months", "Just browsing"]],
        "districts": [["Mirabad", "Yunusabad"], ["Yakkasaray", "Shaykhantahur"], ["Chilanzar", "Mirzo Ulugbek"], ["Other district"]],
    },
}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS leads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, telegram_id INTEGER, username TEXT, name TEXT,
        language TEXT, property_type TEXT, budget_usd INTEGER,
        district TEXT, rooms TEXT, timeline TEXT, phone TEXT, score TEXT
        )"""
    )
    con.commit()
    return con


def kb(rows, cancel_text=None):
    keyboard = [list(row) for row in rows]
    if cancel_text:
        keyboard.append([cancel_text])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def phone_kb(text, cancel_text):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text, request_contact=True)], [cancel_text]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇺🇿 O‘zbek", callback_data="lang:uz"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
    ]])


def lang(context):
    return context.user_data.get("lang", "ru")


def t(context, key):
    return TEXT[lang(context)][key]


def esc(value):
    return html.escape(str(value or "—"))


def money(value):
    return f"{int(value):,}".replace(",", " ")


def parse_budget(s):
    # Accept 120000, 120 000, 120.000, $120,000, 120k/120K.
    raw = s.strip().lower().replace("$", "").replace("usd", "")
    if re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*k\s*", raw):
        try:
            return int(float(re.sub(r"[^0-9.,]", "", raw).replace(",", ".")) * 1000)
        except ValueError:
            return None
    nums = re.sub(r"[^\d]", "", raw)
    if not nums:
        return None
    try:
        value = int(nums)
    except ValueError:
        return None
    return value if 1 <= value <= 100_000_000 else None


def normalize_phone(s):
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("998"):
        s = "+" + s
    return s


def is_cancel(value, context):
    return value.strip().lower() in {"/cancel", TEXT[lang(context)]["cancel_button"].lower()}


def score_lead(data):
    score = 0
    budget = int(data.get("budget_usd", 0) or 0)
    if budget >= 100_000:
        score += 3
    elif budget >= 50_000:
        score += 2
    else:
        score += 1
    timeline = data.get("timeline", "")
    if any(x in timeline for x in ["Срочно", "Shoshilinch", "Urgent"]):
        score += 3
    elif any(x in timeline for x in ["1–3", "1-3"]):
        score += 2
    if data.get("phone"):
        score += 2
    return "HOT" if score >= 7 else "WARM" if score >= 5 else "COLD"


def summary_markup(context):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context, "confirm"), callback_data="summary:confirm")],
        [InlineKeyboardButton(t(context, "edit"), callback_data="summary:edit")],
        [InlineKeyboardButton(t(context, "cancel_button"), callback_data="summary:cancel")],
    ])


def summary_text(context):
    d = context.user_data
    return t(context, "summary").format(
        property_type=esc(d.get("property_type")),
        budget=money(d.get("budget_usd", 0)),
        district=esc(d.get("district")),
        rooms=esc(d.get("rooms")),
        timeline=esc(d.get("timeline")),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        TEXT["ru"]["language"], reply_markup=lang_kb()
    )


async def lang_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = q.data.split(":", 1)[1]
    context.user_data.clear()
    context.user_data.update({"lang": code, "state": TYPE})
    await q.edit_message_text(TEXT[code]["welcome"].format(company=COMPANY), parse_mode=ParseMode.HTML)
    await q.message.reply_text(
        TEXT[code]["type"],
        parse_mode=ParseMode.HTML,
        reply_markup=kb(TEXT[code]["types"], TEXT[code]["cancel_button"]),
    )


async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    u = update.effective_user
    l = lang(context)
    current = context.user_data.get("state", TYPE)
    value = (update.message.text or "").strip()

    if value and is_cancel(value, context):
        await update.message.reply_text(TEXT[l]["cancel"], reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return

    if current == TYPE:
        allowed = {x for row in TEXT[l]["types"] for x in row}
        if value not in allowed:
            await update.message.reply_text("Выберите вариант кнопкой ниже." if l == "ru" else "Please choose an option using the buttons below.", reply_markup=kb(TEXT[l]["types"], TEXT[l]["cancel_button"]))
            return
        context.user_data["property_type"] = value
        context.user_data["state"] = BUDGET
        await update.message.reply_text(TEXT[l]["budget"], parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
        return

    if current == BUDGET:
        budget = parse_budget(value)
        if not budget:
            await update.message.reply_text(TEXT[l]["invalid_budget"], parse_mode=ParseMode.HTML)
            return
        context.user_data["budget_usd"] = budget
        context.user_data["state"] = DISTRICT
        await update.message.reply_text(TEXT[l]["district"], parse_mode=ParseMode.HTML, reply_markup=kb(TEXT[l]["districts"], TEXT[l]["cancel_button"]))
        return

    if current == DISTRICT:
        allowed = {x for row in TEXT[l]["districts"] for x in row}
        if value not in allowed:
            await update.message.reply_text("Выберите район кнопкой ниже." if l == "ru" else "Please choose a district using the buttons below.", reply_markup=kb(TEXT[l]["districts"], TEXT[l]["cancel_button"]))
            return
        context.user_data["district"] = value
        context.user_data["state"] = ROOMS
        await update.message.reply_text(TEXT[l]["rooms"], parse_mode=ParseMode.HTML, reply_markup=kb(TEXT[l]["rooms"], TEXT[l]["cancel_button"]))
        return

    if current == ROOMS:
        allowed = {x for row in TEXT[l]["rooms"] for x in row}
        if value not in allowed:
            await update.message.reply_text("Выберите количество комнат кнопкой ниже." if l == "ru" else "Please choose a room count using the buttons below.", reply_markup=kb(TEXT[l]["rooms"], TEXT[l]["cancel_button"]))
            return
        context.user_data["rooms"] = value
        context.user_data["state"] = TIMELINE
        await update.message.reply_text(TEXT[l]["timeline"], parse_mode=ParseMode.HTML, reply_markup=kb(TEXT[l]["timeline"], TEXT[l]["cancel_button"]))
        return

    if current == TIMELINE:
        allowed = {x for row in TEXT[l]["timeline"] for x in row}
        if value not in allowed:
            await update.message.reply_text("Выберите вариант кнопкой ниже." if l == "ru" else "Please choose an option using the buttons below.", reply_markup=kb(TEXT[l]["timeline"], TEXT[l]["cancel_button"]))
            return
        context.user_data["timeline"] = value
        context.user_data["state"] = CONFIRM
        await update.message.reply_text(summary_text(context), parse_mode=ParseMode.HTML, reply_markup=summary_markup(context))
        return

    if current == PHONE:
        phone = update.message.contact.phone_number if update.message.contact else normalize_phone(value)
        if not re.fullmatch(r"\+?\d{9,15}", phone):
            await update.message.reply_text(TEXT[l]["invalid_phone"], parse_mode=ParseMode.HTML)
            return
        context.user_data["phone"] = phone
        await save_lead(update, context)


async def summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":", 1)[1]
    l = lang(context)
    if action == "confirm":
        context.user_data["state"] = PHONE
        await q.edit_message_text(summary_text(context), parse_mode=ParseMode.HTML)
        await q.message.reply_text(TEXT[l]["phone"], parse_mode=ParseMode.HTML, reply_markup=phone_kb(TEXT[l]["share_phone"], TEXT[l]["cancel_button"]))
    elif action == "edit":
        context.user_data["state"] = TYPE
        await q.edit_message_text(TEXT[l]["type"], parse_mode=ParseMode.HTML)
        await q.message.reply_text(TEXT[l]["type"], parse_mode=ParseMode.HTML, reply_markup=kb(TEXT[l]["types"], TEXT[l]["cancel_button"]))
    else:
        context.user_data.clear()
        await q.edit_message_text(TEXT[l]["cancel"], parse_mode=ParseMode.HTML)


async def save_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    l = lang(context)
    d = context.user_data
    score = score_lead(d)
    con = db()
    cur = con.execute(
        """INSERT INTO leads
        (created_at,telegram_id,username,name,language,property_type,budget_usd,district,rooms,timeline,phone,score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now(timezone.utc).isoformat(), u.id, u.username or "", u.full_name, l,
            d.get("property_type", ""), d.get("budget_usd", 0), d.get("district", ""),
            d.get("rooms", ""), d.get("timeline", ""), d.get("phone", ""), score,
        ),
    )
    lead_id = cur.lastrowid
    con.commit()
    con.close()

    msg = (
        f"<b>NEW LEAD #{lead_id} — {score}</b>\n"
        f"👤 {esc(u.full_name)} (@{esc(u.username or 'no_username')})\n"
        f"🏠 {esc(d.get('property_type'))}\n"
        f"💰 ${money(d.get('budget_usd', 0))}\n"
        f"📍 {esc(d.get('district'))}\n"
        f"🚪 {esc(d.get('rooms'))}\n"
        f"📅 {esc(d.get('timeline'))}\n"
        f"📞 {esc(d.get('phone'))}\n"
        f"🌐 {l}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            log.warning("Cannot notify admin %s: %s", admin_id, e)

    await update.message.reply_text(TEXT[l]["done"], parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID: {update.effective_user.id}")


def admin_only(update):
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text(
        "Admin panel:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Last 10 leads", callback_data="admin:leads")],
            [InlineKeyboardButton("📊 Stats", callback_data="admin:stats")],
            [InlineKeyboardButton("⬇️ Export CSV", callback_data="admin:export")],
        ]),
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in ADMIN_IDS:
        return
    action = q.data.split(":", 1)[1]
    con = db()
    try:
        if action == "leads":
            rows = con.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 10").fetchall()
            if not rows:
                await q.message.reply_text("No leads yet.")
                return
            out = [
                f"#{r['id']} {r['score']} | {r['name']} | ${money(r['budget_usd'])} | {r['district']} | {r['phone']}"
                for r in rows
            ]
            await q.message.reply_text("\n".join(out))
        elif action == "stats":
            total = con.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
            hot = con.execute("SELECT COUNT(*) c FROM leads WHERE score='HOT'").fetchone()["c"]
            warm = con.execute("SELECT COUNT(*) c FROM leads WHERE score='WARM'").fetchone()["c"]
            cold = con.execute("SELECT COUNT(*) c FROM leads WHERE score='COLD'").fetchone()["c"]
            await q.message.reply_text(f"📊 Leads: {total}\n🔥 HOT: {hot}\n🟡 WARM: {warm}\n⚪ COLD: {cold}")
        elif action == "export":
            rows = con.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
            path = "leads.csv"
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(rows[0].keys() if rows else ["id"])
                for r in rows:
                    w.writerow(list(r))
            with open(path, "rb") as f:
                await q.message.reply_document(f, filename="estateflow-leads.csv")
    finally:
        con.close()


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(context, "help"), parse_mode=ParseMode.HTML)


def main():
    if not TOKEN or TOKEN.startswith("PASTE_"):
        raise SystemExit("Set BOT_TOKEN in Railway Variables")
    db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(lang_select, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(summary_callback, pattern=r"^summary:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(MessageHandler(filters.TEXT | filters.CONTACT, collect))
    log.info("EstateFlow AI is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
