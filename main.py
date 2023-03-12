from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest
from telegram.constants import ChatAction
from urllib.parse import quote_plus
from replit import db
import requests
import os
# gpt3.py
from gpt3 import gpt3

def build_chat(user_id: int) -> str:
    chat = db[str(user_id)]
    res = ''
    for msg in chat:
        res += f'{msg["sender"]}: {msg["text"]}'
    return res

async def send_typing(update_, context_):
    await context_.bot.send_chat_action(chat_id=update_.effective_message.chat_id, action=ChatAction.TYPING)

def get_weather(location: str) -> str:
    """Example location: Tampa,FL"""
    loc = quote_plus(location)
    weather_info = requests.get(f'https://wttr.in/{loc}?format=3').text
    return {
        'image_url': f'https://wttr.in/{loc}.png',
        'text': weather_info
    }

# only stats gathered
def usage_statistics():
    chats = len(db.keys())
    return {'chats': chats}

#TODO
def scrape_website(url: str):
    r = requests.get(f'https://extractorapi.com/api/v1/extractor/?apikey={os.getenv("EXTRACTOR")}&url={url}')
    res = r.json()
    meta = {k: v for k, v in res.items() if not k in ['html', 'images', 'videos']}
    return meta

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db[str(user.id)] = []
    await update.effective_chat.send_message('[*] New conversation started')

async def read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_typing(update, context)
    user = update.effective_user
    url = context.args[0]
    res = scrape_website(url)
    # add request and result to chatlog
    db[str(user.id)] = [*db[str(user.id)], {'sender': 'user', 'text': f'read {url} for me'}, {'sender': 'chatgpt', 'text': res}] 
    try:
        await update.effective_chat.send_message(res['text']) 
    except BadRequest:
        await update.effective_chat.send_message('[*] processed website - too long to emit text content')

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_typing(update, context)
    user = update.effective_user
    location = context.args[0]
    w = get_weather(location)
    db[str(user.id)] = [*db[str(user.id)], {'sender': 'user', 'text': f'whats the weather in {location}'}, {'sender': 'chatgpt', 'text': w['text']}]
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=w['image_url'])
    await update.effective_chat.send_message(w['text'])

async def save_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    slot = context.args[0]
    if not slot in ('1', '2', '3'):
        await update.effective_chat.send_message('[!] Sorry, you must specify a save slot from 1-3 inclusive.')
        return
    db[f'{str(user.id)}:{slot}'] = db[str(user.id)]
    await update.effective_chat.send_message(f'[+] Saved chat. To resume, use /load {slot}')

async def load_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    slot = context.args[0]
    if not slot in ('1', '2', '3'):
        await update.effective_chat.send_message('[!] Sorry, you must specify a save slot from 1-3 inclusive.')
        return
    db[str(user.id)] = db.get(f'{str(user.id)}:{slot}', [])
    await update.effective_chat.send_message('[+] Chat resumed')

async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message('''[*] Commands
    /start - start a new chat
    /read {url} - scrape and process website link
    /save {1,2,3} - save current chat to slot 1, 2, or 3
    /load {1,2,3} - load chat from previous save
    /summary - summarize previous chat logs
    /usage - view usage statistics (number of conversations)
    /wipe - delete *ALL your CHATS* from system
    /weather {location} - get the current weather (location e.g. Tampa,FL)''')

async def wipe_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_typing(update, context)
    user_id = str(update.effective_user.id)
    for k in [user_id, *[f'{user_id}:{i}' for i in range(1,4)]]:
        try:
            del db[k]
            await update.effective_chat.send_message(f'[-] Cleared chat {k}')
        except:
            pass # lol whatchu gonna do about it
    await update.effective_chat.send_message('[*] Finished. Chats listed above were deleted.')

async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_typing(update, context)
    user_id = str(update.effective_user.id)
    chatlogs = build_chat(user_id)
    if chatlogs:
        resp = gpt3.gpt3(f'Summarize the events from the following chat logs: {chatlogs}')
        await update.effective_chat.send_message(resp)
    else:
        await update.effective_chat.send_message("[!] Empty chat. Can't build summary.")

async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(f'[*] Usage statistics: {usage_statistics()}')

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_typing(update, context)
    user = update.effective_user
    text = update.message.text
    resp = gpt3.gpt3(build_chat(user.id) + f'\n{user.first_name} [datetime: {update.message.date}]: {text}\nchatgpt: ')
    db[str(user.id)] = [*db[str(user.id)], {'sender': 'user', 'text': text}, {'sender': 'chatgpt', 'text': resp}]
    await update.effective_chat.send_message(resp)

def main():
    application = Application.builder().token(os.getenv('TELEGRAM')).build()
    application.add_handler(CommandHandler('restart', new_chat))
    application.add_handler(CommandHandler('start', new_chat))

    application.add_handler(CommandHandler('read', read))
    application.add_handler(CommandHandler('weather', weather))

    application.add_handler(CommandHandler('help', get_help))
    application.add_handler(CommandHandler('usage', usage))
    application.add_handler(CommandHandler('wipe', wipe_chats))

    application.add_handler(CommandHandler('save', save_chat))
    application.add_handler(CommandHandler('load', load_chat))

    application.add_handler(CommandHandler('summary', summarize))

    # catch all
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    print('we up')
    main()