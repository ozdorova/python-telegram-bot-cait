import logging
import telebot
import os
import openai
import json
import time
import multiprocessing
import json
import redis

from threading import Thread
from telebot.apihelper import ApiTelegramException


TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN')
TG_BOT_CHATS = os.environ.get('TG_BOT_CHATS').lower().split(',')
PROXY_API_KEY = os.environ.get('PROXY_API_KEY')
REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = os.environ.get('REDIS_PORT')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')


r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=0,
)


logger = telebot.logger
telebot.logger.setLevel(logging.INFO)


bot = telebot.TeleBot(TG_BOT_TOKEN, threaded=True)

client = openai.Client(
    api_key=PROXY_API_KEY,
    base_url='https://api.proxyapi.ru/openai/v1',
)


def typing(chat_id):
    while True:
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(5)


def check_user(message):
    return message.from_user.username.lower() in TG_BOT_CHATS


@bot.message_handler(func=lambda message: not check_user(message), commands=['start', 'help', 'new'])
def send_restricted(message):
    bot.reply_to(
        message,
        ('Извините, бот не доступен для вас'),
    )


@bot.message_handler(func=lambda message: check_user(message), commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(
        message,
        ('Привет! Я CaiT, ChatGPT бот. Спроси меня что-нибудь!'),
    )


@bot.message_handler(func=lambda message: check_user(message), commands=['new'])
def clear_history(message):
    r.delete('chat_history')
    bot.reply_to(message, 'История чата очищена!')


@bot.message_handler(func=lambda message: check_user(message), content_types=['text'])
def echo_message(message):
    Thread(target=get_ai_responce, args=(message,), daemon=True).start()


def get_ai_responce(message):
    typing_process = multiprocessing.Process(
        target=typing, args=(message.chat.id,), daemon=True)
    typing_process.start()

    try:
        text = message.text
        ai_response = process_text_message(text, message.chat.id)
    except Exception as e:
        bot.reply_to(message, f'Произошла ошибка, попробуйте позже! {e}')
        return

    try:
        bot.reply_to(message, ai_response, parse_mode='Markdown')
    except ApiTelegramException:
        bot.reply_to(message, ai_response)
    finally:
        typing_process.terminate()


def process_text_message(text, chat_id) -> str:
    model = 'gpt-3.5-turbo'

    r.rpush('chat_history', json.dumps({'role': 'user', 'content': text}))
    r.expire('chat_history', 600)

    history = [json.loads(string)
               for string in r.lrange('chat_history', 0, -1)]
    try:

        chat_completion = client.chat.completions.create(
            model=model, messages=history
        )
    except Exception as e:
        if type(e).__name__ == 'BadRequestError':
            return process_text_message(text, chat_id)
        else:
            raise e

    ai_response = chat_completion.choices[0].message.content
    r.rpush('chat_history', json.dumps(
        {'role': 'assistant', 'content': ai_response}))

    return ai_response


Thread(target=bot.infinity_polling).start()
