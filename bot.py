import os
import csv
import sqlite3
import logging
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
COMPANY = os.getenv("COMPANY_NAME", "EstateFlow AI")
MANAGER = os.getenv("MANAGER_NAME", "EstateFlow Manager")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DB = "estateflow.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("estateflow")

TYPE, BUDGET, DISTRICT, ROOMS, TIMELINE, PHONE = range(6)

TEXT = {
    "ru": {
        "welcome": "Здравствуйте! 👋 Я AI-ассистент {company}. Помогу подобрать недвижимость в Ташкенте.",
        "language": "Выберите язык:",
        "type": "Что вы ищете?",
        "budget": "Какой максимальный бюджет? Например: 120000 или $120,000",
        "district": "Какой район предпочитаете?",
        "rooms": "Сколько комнат нужно?",
        "timeline": "Когда планируете покупку?",
        "phone": "Оставьте номер телефона, чтобы менеджер отправил подходящие варианты.",
        "done": "Спасибо! ✅ Заявка принята. Менеджер свяжется с вами в ближайшее время.",
        "cancel": "Заявка отменена. Нажмите /start, чтобы начать снова.",
        "invalid_budget": "Введите сумму цифрами, например 120000.",
        "invalid_phone": "Пожалуйста, отправьте номер кнопкой ниже или в формате +998901234567.",
        "help": "Я могу собрать параметры недвижимости и передать заявку менеджеру. Нажмите /start.",
        "types": [["Квартира","Дом"],["Коммерция","Участок"]],
        "rooms": [["1","2","3"],["4","5+"],["Не важно"]],
        "timeline": [["Срочно","1–3 месяца"],["3–6 месяцев","Пока смотрю"]],
        "districts": [["Мирабад","Юнусабад"],["Яккасарай","Шайхантахур"],["Чиланзар","Мирзо-Улугбек"],["Другой район"]],
    },
    "uz": {
        "welcome": "Assalomu alaykum! 👋 Men {company} AI yordamchisiman. Toshkentdagi ko'chmas mulkni tanlashga yordam beraman.",
        "language": "Tilni tanlang:",
        "type": "Nima qidiryapsiz?",
        "budget": "Maksimal byudjetingiz qancha? Masalan: 120000",
        "district": "Qaysi tumanni afzal ko'rasiz?",
        "rooms": "Nechta xona kerak?",
        "timeline": "Qachon xarid qilishni rejalashtiryapsiz?",
        "phone": "Mos variantlarni yuborish uchun telefon raqamingizni qoldiring.",
        "done": "Rahmat! ✅ So'rovingiz qabul qilindi. Menejer tez orada bog'lanadi.",
        "cancel": "So'rov bekor qilindi. Qayta boshlash uchun /start bosing.",
        "invalid_budget": "Summani raqam bilan kiriting, masalan 120000.",
        "invalid_phone": "Telefon raqamingizni tugma orqali yuboring yoki +998901234567 formatida kiriting.",
        "help": "Men ko'chmas mulk parametrlarini yig'ib, menejerga yuboraman. /start ni bosing.",
        "types": [["Kvartira","Uy"],["Tijorat","Yer uchastkasi"]],
        "rooms": [["1","2","3"],["4","5+"],["Farqi yo'q"]],
        "timeline": [["Shoshilinch","1–3 oy"],["3–6 oy","Hozircha ko'ryapman"]],
        "districts": [["Mirobod","Yunusobod"],["Yakkasaroy","Shayxontohur"],["Chilonzor","Mirzo Ulug'bek"],["Boshqa tuman"]],
    },
    "en": {
        "welcome": "Hello! 👋 I'm the {company} AI assistant. I'll help you find property in Tashkent.",
        "language": "Choose your language:",
        "type": "What are you looking for?",
        "budget": "What is your maximum budget? Example: 120000",
        "district": "Which district do you prefer?",
        "rooms": "How many rooms do you need?",
        "timeline": "When are you planning to buy?",
        "phone": "Share your phone number so a manager can send matching options.",
        "done": "Thank you! ✅ Your request is received. A manager will contact you shortly.",
        "cancel": "Request cancelled. Press /start to begin again.",
        "invalid_budget": "Enter the amount using digits, e.g. 120000.",
        "invalid_phone": "Send your phone using the button or format +998901234567.",
        "help": "I collect property requirements and send the lead to a manager. Press /start.",
        "types": [["Apartment","House"],["Commercial","Land"]],
        "rooms": [["1","2","3"],["4","5+"],["Any"]],
        "timeline": [["Urgent","1–3 months"],["3–6 months","Just browsing"]],
        "districts": [["Mirabad","Yunusabad"],["Yakkasaray","Shaykhantahur"],["Chilanzar","Mirzo Ulugbek"],["Other district"]],
    }
}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS leads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, telegram_id INTEGER, username TEXT, name TEXT,
        language TEXT, property_type TEXT, budget_usd INTEGER,
        district TEXT, rooms TEXT, timeline TEXT, phone TEXT, score TEXT
    )""")
    con.commit()
    return con

def kb(rows, resize=True):
    return ReplyKeyboardMarkup(rows, resize_keyboard=resize, one_time_keyboard=True)

def lang_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
         InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang:uz"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")]
    ])

def lang(context):
    return context.user_data.get("lang", "ru")

def t(context, key):
    return TEXT[lang(context)][key]

def score_lead(data):
    score = 0
    if data.get("budget_usd", 0) >= 100000: score += 3
    elif data.get("budget_usd", 0) >= 50000: score += 2
    else: score += 1
    if data.get("timeline") in ["Срочно","Shoshilinch","Urgent"]: score += 3
    elif "1–3" in data.get("timeline",""): score += 2
    if data.get("phone"): score += 2
    if score >= 7: return "HOT"
    if score >= 5: return "WARM"
    return "COLD"

def parse_budget(s):
    nums = re.sub(r"[^\d]", "", s)
    return int(nums) if nums else None

def normalize_phone(s):
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("998"): s = "+" + s
    return s

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Welcome / Добро пожаловать / Xush kelibsiz!\n\n" + TEXT["ru"]["language"],
        reply_markup=lang_kb()
    )

async def lang_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = q.data.split(":")[1]
    context.user_data["lang"] = code
    await q.edit_message_text(TEXT[code]["welcome"].format(company=COMPANY))
    await q.message.reply_text(TEXT[code]["type"], reply_markup=kb(TEXT[code]["types"]))

    # move conversation forward by returning state is not supported through callback handler;
    # set a flag and the global callback will start collection.
    context.user_data["state"] = TYPE

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    l = lang(context)
    current = context.user_data.get("state", TYPE)
    value = update.message.text.strip()

    if value == "/cancel":
        await update.message.reply_text(TEXT[l]["cancel"], reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    if current == TYPE:
        context.user_data["property_type"] = value
        context.user_data["state"] = BUDGET
        await update.message.reply_text(TEXT[l]["budget"], reply_markup=ReplyKeyboardRemove())
        return BUDGET

    if current == BUDGET:
        budget = parse_budget(value)
        if not budget:
            await update.message.reply_text(TEXT[l]["invalid_budget"])
            return BUDGET
        context.user_data["budget_usd"] = budget
        context.user_data["state"] = DISTRICT
        await update.message.reply_text(TEXT[l]["district"], reply_markup=kb(TEXT[l]["districts"]))
        return DISTRICT

    if current == DISTRICT:
        context.user_data["district"] = value
        context.user_data["state"] = ROOMS
        await update.message.reply_text(TEXT[l]["rooms"], reply_markup=kb(TEXT[l]["rooms"]))
        return ROOMS

    if current == ROOMS:
        context.user_data["rooms"] = value
        context.user_data["state"] = TIMELINE
        await update.message.reply_text(TEXT[l]["timeline"], reply_markup=kb(TEXT[l]["timeline"]))
        return TIMELINE

    if current == TIMELINE:
        context.user_data["timeline"] = value
        context.user_data["state"] = PHONE
        await update.message.reply_text(
            TEXT[l]["phone"],
            reply_markup=kb([[KeyboardButton("📞 Share phone number", request_contact=True)]])
        )
        return PHONE

    if current == PHONE:
        phone = update.message.contact.phone_number if update.message.contact else normalize_phone(value)
        if not re.fullmatch(r"\+?\d{9,15}", phone):
            await update.message.reply_text(TEXT[l]["invalid_phone"])
            return PHONE
        context.user_data["phone"] = phone
        score = score_lead(context.user_data)

        con = db()
        con.execute("""INSERT INTO leads
        (created_at,telegram_id,username,name,language,property_type,budget_usd,district,rooms,timeline,phone,score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            datetime.now(timezone.utc).isoformat(), u.id, u.username or "",
            u.full_name, l, context.user_data.get("property_type",""),
            context.user_data.get("budget_usd",0), context.user_data.get("district",""),
            context.user_data.get("rooms",""), context.user_data.get("timeline",""), phone, score
        ))
        lead_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit(); con.close()

        msg = (f"🔥 <b>NEW LEAD #{lead_id} — {score}</b>\n"
               f"👤 {u.full_name} (@{u.username or 'no_username'})\n"
               f"🏠 {context.user_data.get('property_type')}\n"
               f"💰 ${context.user_data.get('budget_usd'):,}\n"
               f"📍 {context.user_data.get('district')}\n"
               f"🚪 {context.user_data.get('rooms')}\n"
               f"⏱ {context.user_data.get('timeline')}\n"
               f"📞 {phone}\n"
               f"🌐 {l}")
        for admin in ADMIN_IDS:
            try:
                await context.bot.send_message(admin, msg, parse_mode=ParseMode.HTML)
            except Exception as e:
                log.warning("Cannot notify admin %s: %s", admin, e)

        await update.message.reply_text(TEXT[l]["done"], reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    return current

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID: {update.effective_user.id}")

def admin_only(update):
    return update.effective_user and update.effective_user.id in ADMIN_IDS

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("Admin panel:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Last 10 leads", callback_data="admin:leads")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin:stats")],
        [InlineKeyboardButton("⬇️ Export CSV", callback_data="admin:export")]
    ]))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.from_user.id not in ADMIN_IDS:
        return
    action=q.data.split(":")[1]
    con=db()
    if action=="leads":
        rows=con.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 10").fetchall()
        if not rows: await q.message.reply_text("No leads yet."); return
        out=[]
        for r in rows:
            out.append(f"#{r['id']} {r['score']} | {r['name']} | ${r['budget_usd']:,} | {r['district']} | {r['phone']}")
        await q.message.reply_text("\n".join(out))
    elif action=="stats":
        total=con.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
        hot=con.execute("SELECT COUNT(*) c FROM leads WHERE score='HOT'").fetchone()["c"]
        warm=con.execute("SELECT COUNT(*) c FROM leads WHERE score='WARM'").fetchone()["c"]
        await q.message.reply_text(f"📊 Leads: {total}\n🔥 HOT: {hot}\n🟡 WARM: {warm}")
    elif action=="export":
        rows=con.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
        path="leads.csv"
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(rows[0].keys() if rows else ["id"])
            for r in rows: w.writerow(list(r))
        with open(path,"rb") as f: await q.message.reply_document(f, filename="estateflow-leads.csv")
    con.close()

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(context,"help"))

def main():
    if not TOKEN or TOKEN.startswith("PASTE_"):
        raise SystemExit("Set BOT_TOKEN in .env")
    db()
    app=Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(lang_select, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(MessageHandler(filters.TEXT | filters.CONTACT, collect))

    log.info("EstateFlow AI is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
