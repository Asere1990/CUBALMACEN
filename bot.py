import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Token desde variable de entorno
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Imagen y enlace del botón
IMAGE_URL = 'https://i.postimg.cc/jqBbLNMd/photo-output.jpg'
BOTON_URL = 'https://t.me/share/url?url=https://t.me/cubalmacenn'

# Crear la botonera
def crear_botonera():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("𝐄𝐍𝐓𝐑𝐀𝐑🚪", url=BOTON_URL),
        InlineKeyboardButton("¿𝐂𝐨́𝐦𝐨 𝐞𝐧𝐭𝐫𝐚𝐫?", callback_data='ayuda')
    )
    return markup

# Comando /start
@bot.message_handler(commands=['start'])
def enviar_bienvenida(message):
    bot.send_photo(
        chat_id=message.chat.id,
        photo=IMAGE_URL,
        reply_markup=crear_botonera()
    )

# Manejar el botón de ayuda (popup)
@bot.callback_query_handler(func=lambda call: call.data == 'ayuda')
def responder_callback(call):
    bot.answer_callback_query(
        callback_query_id=call.id,
        text="𝐏𝐫𝐞𝐬𝐢𝐨𝐧𝐞 𝐞𝐥 𝐛𝐨𝐭𝐨́𝐧 '𝐄𝐍𝐓𝐑𝐀𝐑' 𝐲 𝐬𝐞𝐥𝐞𝐜𝐜𝐢𝐨𝐧𝐞 𝟓 𝐠𝐫𝐚𝐧𝐝𝐞𝐬 𝐠𝐫𝐮𝐩𝐨𝐬 𝐩𝐚𝐫𝐚 𝐞𝐧𝐭𝐫𝐚𝐫 𝐞𝐥 𝐜𝐚𝐧𝐚𝐥 𝐂𝐔𝐁𝐀𝐋𝐌𝐀𝐂𝐄𝐍 𝐆𝐑𝐀𝐓𝐈𝐒.",
        show_alert=True
    )

# Mantener el bot activo
bot.infinity_polling()
