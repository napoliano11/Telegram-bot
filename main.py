import telebot
from telebot import types
import time
import os  # needed to read environment variables

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")  # reads the token from Railway variable
ADMIN_ID = 1006994687
PASSWORD = "1234"

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Example: simple polling loop
bot.infinity_polling()

# ================= DATA ===================
UNITS = ["PUA", "PUB", "PUC", "PUF", "PBF", "AHA", "AHB", "AHC"]
REQUESTS = [
    "LISTE DES INJECTABLES", "LISTE DES SOLUTIONS BUVABLES",
    "LISTE DU TRT SOMATIQUE", "LES PSYCHOTROPES D'HIER",
    "LISTE DE CONSOMMATION MENSUELLE", "NUMÉRO DE L'H24", "QUESTION"
]
NUMERO_H24_TEXT = "Call 120 for ph/h24\nCall 111 for ph/central"
PREP_ANSWER_DURATION = 24 * 3600  # 24 hours
MAX_PENDING = 20
PENDING_TIMEOUT = 3600  # 1 hour timeout for pending requests

# ================= STATE ===================
user_state = {}
user_unit = {}
pending_requests = {}  # msg_id -> {"chat_id", "timestamp", "request_type", "unit", "question"}
prepared_answers = {}  # key = unit_request, value = {"type": "text/photo", "content"/"file_id", "timestamp"}
admin_state = {}

# ================= BOT =====================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================= HELPERS =================
def cleanup_pending():
    now = time.time()
    remove = [k for k,v in pending_requests.items() if now - v["timestamp"] > PENDING_TIMEOUT]
    for k in remove: del pending_requests[k]

def cleanup_prepared():
    now = time.time()
    remove = [k for k,v in prepared_answers.items() if now - v["timestamp"] > PREP_ANSWER_DURATION]
    for k in remove: del prepared_answers[k]

def unit_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("PUA","PUB","PUC")
    kb.row("PUF","PBF","AHA")
    kb.row("AHB","AHC")
    kb.row("⬅️ BACK")
    return kb

def request_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("LISTE DES INJECTABLES","LISTE DES SOLUTIONS BUVABLES")
    kb.row("LISTE DU TRT SOMATIQUE","LES PSYCHOTROPES D'HIER")
    kb.row("LISTE DE CONSOMMATION MENSUELLE","NUMÉRO DE L'H24")
    kb.row("QUESTION","⬅️ BACK")
    return kb

def remove_keyboard():
    return types.ReplyKeyboardRemove()

def admin_main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Préparer une réponse","Voir les réponses préparées")
    kb.row("Voir demandes par unité")
    kb.row("End session")
    return kb

def admin_welcome_message():
    return """🔧 <b>Menu Admin</b>

<b>Commandes disponibles:</b>
/admin - Ouvrir le menu admin
/done - Terminer la session

<b>Options du menu:</b>
• Préparer une réponse - Préparer des réponses automatiques
• Voir les réponses préparées - Gérer les réponses existantes
• Voir demandes par unité - Voir toutes les demandes en attente par unité
• End session - Terminer la session admin

<b>Pour répondre à une demande:</b>
Répondez directement au message de demande (reply)"""

def show_prepared_list():
    text = ""
    for idx, key in enumerate(prepared_answers,1):
        unit, req = key.split("_",1)
        text += f"{idx}️⃣ {unit} - {req}\n"
    if not text: text = "⚠️ Aucune réponse préparée pour le moment."
    return text

def get_prepared_by_number(number):
    keys = list(prepared_answers.keys())
    if number-1 < len(keys):
        return keys[number-1]
    return None

def get_requests_by_unit(unit):
    cleanup_pending()
    requests_list = []
    for msg_id, data in pending_requests.items():
        if data["unit"] == unit:
            requests_list.append((msg_id, data))
    return requests_list

def show_unit_requests(unit):
    requests = get_requests_by_unit(unit)
    if not requests:
        return f"📭 Aucune demande en attente pour <b>{unit}</b>."
    
    text = f"📋 <b>Demandes en attente pour {unit}:</b>\n\n"
    for idx, (msg_id, data) in enumerate(requests, 1):
        req_type = data["request_type"]
        question = data.get("question", "")
        elapsed = int(time.time() - data["timestamp"])
        mins = elapsed // 60
        
        if question:
            text += f"{idx}. {req_type}\n   📝 {question}\n   ⏱️ Il y a {mins} min\n\n"
        else:
            text += f"{idx}. {req_type}\n   ⏱️ Il y a {mins} min\n\n"
    
    text += "\n💡 Pour répondre, utilisez reply sur le message de notification original."
    return text

# ================= USER FLOW =================
@bot.message_handler(commands=["start"])
def start(msg):
    if msg.chat.id == ADMIN_ID:
        admin_state[msg.chat.id] = "MAIN"
        bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
        return
    user_state.pop(msg.chat.id,None)
    bot.send_message(msg.chat.id,"👋 Bienvenue! Tapez /go pour commencer.",reply_markup=remove_keyboard())

@bot.message_handler(commands=["go"])
def go(msg):
    if msg.chat.id == ADMIN_ID:
        admin_state[msg.chat.id] = "MAIN"
        bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
        return
    user_state[msg.chat.id] = "CHOOSE_UNIT"
    bot.send_message(msg.chat.id,"🏥 Choisissez votre unité:",reply_markup=unit_keyboard())

@bot.message_handler(func=lambda m:user_state.get(m.chat.id)=="CHOOSE_UNIT" and m.chat.id!=ADMIN_ID)
def choose_unit(msg):
    if msg.text=="⬅️ BACK":
        user_state.pop(msg.chat.id,None)
        bot.send_message(msg.chat.id,"Tapez /go pour recommencer.",reply_markup=remove_keyboard())
        return
    if msg.text not in UNITS: return
    user_unit[msg.chat.id] = msg.text
    user_state[msg.chat.id] = "PASSWORD"
    bot.send_message(msg.chat.id,f"🔐 Entrez le mot de passe pour {msg.text}:",reply_markup=remove_keyboard())

@bot.message_handler(func=lambda m:user_state.get(m.chat.id)=="PASSWORD" and m.chat.id!=ADMIN_ID)
def password(msg):
    if msg.text != PASSWORD:
        user_state.pop(msg.chat.id,None)
        user_unit.pop(msg.chat.id,None)
        bot.send_message(msg.chat.id,"❌ Mot de passe incorrect. Tapez /go pour recommencer.",reply_markup=remove_keyboard())
        return
    user_state[msg.chat.id] = "REQUEST"
    bot.send_message(msg.chat.id,"✅ Mot de passe correct!\n📋 Choisissez une demande:",reply_markup=request_keyboard())

@bot.message_handler(func=lambda m:user_state.get(m.chat.id)=="REQUEST" and m.chat.id!=ADMIN_ID)
def request_handler(msg):
    cleanup_prepared()
    cleanup_pending()
    if msg.text=="⬅️ BACK":
        user_state[msg.chat.id] = "CHOOSE_UNIT"
        bot.send_message(msg.chat.id,"🏥 Choisissez votre unité:",reply_markup=unit_keyboard())
        return
    if msg.text not in REQUESTS: return
    unit = user_unit.get(msg.chat.id,"?")
    request_type = msg.text
    key = f"{unit}_{request_type}"

    if request_type=="NUMÉRO DE L'H24":
        bot.send_message(msg.chat.id,NUMERO_H24_TEXT,reply_markup=request_keyboard())
        return

    pa = prepared_answers.get(key)
    if pa and time.time()-pa["timestamp"]<PREP_ANSWER_DURATION:
        if pa["type"]=="text":
            bot.send_message(msg.chat.id,pa["content"],reply_markup=request_keyboard())
        elif pa["type"]=="photo":
            bot.send_photo(msg.chat.id,pa["file_id"],caption=pa.get("caption",""),parse_mode="HTML")
        return

    if request_type=="QUESTION":
        user_state[msg.chat.id]="ASK_QUESTION"
        bot.send_message(msg.chat.id,"❓ Écrivez votre question:",reply_markup=remove_keyboard())
        return

    if len(pending_requests)>=MAX_PENDING:
        bot.send_message(msg.chat.id,"⚠️ Trop de demandes en attente, réessayez plus tard.")
        return
    admin_msg = bot.send_message(ADMIN_ID,
        f"📩 <b>Nouvelle demande</b>\n👤 Utilisateur: {msg.chat.id}\n🏥 Unité: {unit}\n📋 Demande: {request_type}\n\n💡 Répondez à ce message pour envoyer une réponse.")
    pending_requests[admin_msg.message_id] = {
        "chat_id": msg.chat.id,
        "timestamp": time.time(),
        "request_type": request_type,
        "unit": unit,
        "question": ""
    }
    bot.send_message(msg.chat.id,"✅ Demande envoyée! Vous recevrez une réponse bientôt.",reply_markup=request_keyboard())

@bot.message_handler(func=lambda m:user_state.get(m.chat.id)=="ASK_QUESTION" and m.chat.id!=ADMIN_ID)
def ask_question(msg):
    cleanup_pending()
    if len(pending_requests)>=MAX_PENDING:
        bot.send_message(msg.chat.id,"⚠️ Trop de demandes en attente, réessayez plus tard.",reply_markup=request_keyboard())
        user_state[msg.chat.id]="REQUEST"
        return
    unit = user_unit.get(msg.chat.id,"?")
    admin_msg = bot.send_message(ADMIN_ID,
        f"❓ <b>Nouvelle question</b>\n👤 Utilisateur: {msg.chat.id}\n🏥 Unité: {unit}\n📝 Question: {msg.text}\n\n💡 Répondez à ce message pour envoyer une réponse.")
    pending_requests[admin_msg.message_id] = {
        "chat_id": msg.chat.id,
        "timestamp": time.time(),
        "request_type": "QUESTION",
        "unit": unit,
        "question": msg.text
    }
    user_state[msg.chat.id]="REQUEST"
    bot.send_message(msg.chat.id,"✅ Question envoyée! Vous recevrez une réponse bientôt.",reply_markup=request_keyboard())

@bot.message_handler(commands=["done"])
def done(msg):
    if msg.chat.id==ADMIN_ID:
        admin_state.pop(msg.chat.id,None)
        bot.send_message(msg.chat.id,"🔧 Session admin terminée.",reply_markup=admin_main_keyboard())
    else:
        user_state.pop(msg.chat.id,None)
        user_unit.pop(msg.chat.id,None)
        bot.send_message(msg.chat.id,"👋 Session terminée. Tapez /go pour recommencer.",reply_markup=remove_keyboard())

# ================= ADMIN REPLY TO PENDING =================
@bot.message_handler(func=lambda m:m.chat.id==ADMIN_ID and m.reply_to_message is not None, content_types=['text', 'photo'])
def admin_reply_pending(msg):
    reply_id = msg.reply_to_message.message_id
    if reply_id in pending_requests:
        data = pending_requests.pop(reply_id)
        user_chat_id = data["chat_id"]
        req_type = data["request_type"]
        unit = data["unit"]
        
        try:
            if msg.content_type=="text":
                bot.send_message(user_chat_id,f"📬 Réponse à votre demande ({req_type}):\n{msg.text}")
            elif msg.content_type=="photo":
                caption = f"📬 Réponse à votre demande ({req_type}):\n{msg.caption}" if msg.caption else f"📬 Réponse à votre demande ({req_type}):"
                bot.send_photo(user_chat_id,msg.photo[-1].file_id,caption=caption,parse_mode="HTML")
            
            bot.send_message(ADMIN_ID,f"✅ <b>Réponse envoyée avec succès!</b>\n\n📋 Demande: {req_type}\n🏥 Unité: {unit}\n👤 Utilisateur: {user_chat_id}")
        except Exception as e:
            bot.send_message(ADMIN_ID,f"❌ Erreur lors de l'envoi de la réponse: {str(e)}")
            pending_requests[reply_id] = data
    else:
        bot.send_message(msg.chat.id,"⚠️ Cette demande n'existe plus ou a expiré.",reply_markup=admin_main_keyboard())

# ================= ADMIN FLOW =================
@bot.message_handler(commands=["admin"])
def admin(msg):
    if msg.chat.id!=ADMIN_ID: return
    admin_state[msg.chat.id]="MAIN"
    bot.send_message(msg.chat.id,admin_welcome_message(),reply_markup=admin_main_keyboard())

@bot.message_handler(func=lambda m:m.chat.id==ADMIN_ID and m.reply_to_message is None, content_types=['text', 'photo'])
def admin_handler(msg):
    cleanup_prepared()
    cleanup_pending()
    state = admin_state.get(msg.chat.id,"MAIN")
    text = msg.text if msg.text else ""

    if msg.content_type == "photo":
        if state.startswith("WRITE_") or state.startswith("EDIT_"):
            key = state.replace("WRITE_","").replace("EDIT_","")
            prepared_answers[key]={"type":"photo","file_id":msg.photo[-1].file_id,"caption":msg.caption if msg.caption else "","timestamp":time.time()}
            admin_state[msg.chat.id]="VIEW_PREP"
            bot.send_message(msg.chat.id,"✅ Réponse enregistrée.",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Add","Back"))
            return
        else:
            bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
            return

    if state=="MAIN":
        if text=="Préparer une réponse":
            admin_state[msg.chat.id]="CHOOSE_UNIT_PREP"
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for u in UNITS: kb.add(u)
            kb.add("⬅️ BACK")
            bot.send_message(msg.chat.id,"🏥 Choisissez une unité pour préparer une réponse:",reply_markup=kb)
            return
        elif text=="Voir les réponses préparées":
            admin_state[msg.chat.id]="VIEW_PREP"
            bot.send_message(msg.chat.id,show_prepared_list(),reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Add","Back"))
            return
        elif text=="Voir demandes par unité":
            admin_state[msg.chat.id]="CHOOSE_UNIT_VIEW"
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("PUA","PUB","PUC")
            kb.row("PUF","PBF","AHA")
            kb.row("AHB","AHC")
            kb.row("Toutes les unités")
            kb.row("⬅️ BACK")
            bot.send_message(msg.chat.id,"🏥 Choisissez une unité pour voir les demandes:",reply_markup=kb)
            return
        elif text=="End session":
            admin_state.pop(msg.chat.id,None)
            bot.send_message(msg.chat.id,"🔧 Session terminée.",reply_markup=admin_main_keyboard())
            return
        else:
            bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
            return

    if state=="CHOOSE_UNIT_VIEW":
        if text=="⬅️ BACK":
            admin_state[msg.chat.id]="MAIN"
            bot.send_message(msg.chat.id,admin_welcome_message(),reply_markup=admin_main_keyboard())
            return
        elif text=="Toutes les unités":
            cleanup_pending()
            if not pending_requests:
                bot.send_message(msg.chat.id,"📭 Aucune demande en attente.",reply_markup=admin_main_keyboard())
                admin_state[msg.chat.id]="MAIN"
                return
            
            all_text = "📋 <b>Toutes les demandes en attente:</b>\n\n"
            for unit in UNITS:
                requests = get_requests_by_unit(unit)
                if requests:
                    all_text += f"<b>{unit}:</b> {len(requests)} demande(s)\n"
                    for msg_id, data in requests:
                        req_type = data["request_type"]
                        question = data.get("question", "")
                        if question:
                            all_text += f"  • {req_type}: {question[:50]}...\n" if len(question) > 50 else f"  • {req_type}: {question}\n"
                        else:
                            all_text += f"  • {req_type}\n"
                    all_text += "\n"
            
            all_text += "💡 Pour répondre, utilisez reply sur le message de notification original."
            bot.send_message(msg.chat.id, all_text, reply_markup=admin_main_keyboard())
            admin_state[msg.chat.id]="MAIN"
            return
        elif text in UNITS:
            result = show_unit_requests(text)
            bot.send_message(msg.chat.id, result)
            return
        else:
            bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
            admin_state[msg.chat.id]="MAIN"
            return

    if state=="VIEW_PREP":
        if text.lower().startswith("edit"):
            try:
                number = int(text.split()[1])
                key = get_prepared_by_number(number)
                if not key: raise ValueError
                admin_state[msg.chat.id]=f"EDIT_{key}"
                pa = prepared_answers[key]
                if pa["type"]=="text":
                    bot.send_message(msg.chat.id,f"📋 Actuelle réponse:\n{pa['content']}\nEnvoyez le nouveau texte ou photo:",reply_markup=remove_keyboard())
                else:
                    bot.send_photo(msg.chat.id,pa["file_id"],caption=pa.get("caption","Envoyez nouvelle réponse"),parse_mode="HTML")
            except:
                bot.send_message(msg.chat.id,"⚠️ Numéro invalide.")
            return
        elif text.lower().startswith("delete"):
            try:
                number = int(text.split()[1])
                key = get_prepared_by_number(number)
                if not key: raise ValueError
                prepared_answers.pop(key,None)
                bot.send_message(msg.chat.id,"✅ Réponse supprimée.",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Add","Back"))
            except:
                bot.send_message(msg.chat.id,"⚠️ Numéro invalide.")
            return
        elif text=="Add":
            admin_state[msg.chat.id]="CHOOSE_UNIT_PREP"
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for u in UNITS: kb.add(u)
            kb.add("⬅️ BACK")
            bot.send_message(msg.chat.id,"🏥 Choisissez une unité pour ajouter une nouvelle réponse:",reply_markup=kb)
            return
        elif text=="Back":
            admin_state[msg.chat.id]="MAIN"
            bot.send_message(msg.chat.id,admin_welcome_message(),reply_markup=admin_main_keyboard())
            return
        else:
            bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
            admin_state[msg.chat.id]="MAIN"
            return

    if state=="CHOOSE_UNIT_PREP":
        if text=="⬅️ BACK":
            admin_state[msg.chat.id]="MAIN"
            bot.send_message(msg.chat.id,admin_welcome_message(),reply_markup=admin_main_keyboard())
            return
        if text not in UNITS:
            bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
            admin_state[msg.chat.id]="MAIN"
            return
        admin_state[msg.chat.id]=f"UNIT_{text}"
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for r in REQUESTS: kb.add(r)
        kb.add("⬅️ BACK")
        bot.send_message(msg.chat.id,f"📋 Choisissez le type de demande pour {text}:",reply_markup=kb)
        return

    if state.startswith("UNIT_"):
        unit = state.replace("UNIT_","")
        if text=="⬅️ BACK":
            admin_state[msg.chat.id]="CHOOSE_UNIT_PREP"
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for u in UNITS: kb.add(u)
            kb.add("⬅️ BACK")
            bot.send_message(msg.chat.id,"🏥 Choisissez une unité:",reply_markup=kb)
            return
        if text not in REQUESTS:
            bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
            admin_state[msg.chat.id]="MAIN"
            return
        admin_state[msg.chat.id]=f"WRITE_{unit}_{text}"
        bot.send_message(msg.chat.id,f"📝 Envoyez la réponse pour {unit} - {text} (texte ou photo):",reply_markup=remove_keyboard())
        return

    if state.startswith("WRITE_") or state.startswith("EDIT_"):
        key = state.replace("WRITE_","").replace("EDIT_","")
        if msg.content_type=="text":
            prepared_answers[key]={"type":"text","content":msg.text,"timestamp":time.time()}
        admin_state[msg.chat.id]="VIEW_PREP"
        bot.send_message(msg.chat.id,"✅ Réponse enregistrée.",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Add","Back"))
        return

    admin_state[msg.chat.id]="MAIN"
    bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())

# ================= CATCH ALL =================
@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'document', 'video', 'audio', 'voice', 'sticker'])
def catch_all(msg):
    if msg.chat.id==ADMIN_ID:
        admin_state[msg.chat.id]="MAIN"
        bot.send_message(msg.chat.id, admin_welcome_message(), reply_markup=admin_main_keyboard())
    else:
        bot.send_message(msg.chat.id,"⚠️ Tapez /go pour commencer.",reply_markup=remove_keyboard())

# ================= MAIN =================
i
