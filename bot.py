import requests
import telebot
import schedule
import time
from datetime import datetime
import json
import os

BOT_TOKEN = '8454820081:AAFTjnT2oyyWmX0J8PLQmcDE0tC82TFcJKw'
ALPHA_VANTAGE_KEY = 'TNRGDW0XZE622EKD'
SUBSCRIBERS_FILE = 'subscribers.json'

bot = telebot.TeleBot(BOT_TOKEN)

def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, 'r') as f:
                return json.load(f)
        return ['453666647']  # Твой chat ID
    except:
        return ['453666647']

def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, 'w') as f:
        json.dump(subscribers, f)

def get_data():
    try:
        btc_price = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd').json()['bitcoin']['usd']
        vix = requests.get(f'https://www.alphavantage.co/query?function=VIX&interval=60min&apikey={ALPHA_VANTAGE_KEY}').json()['data'][-1]['value']
        dxy_data = requests.get(f'https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=DX&apikey={ALPHA_VANTAGE_KEY}').json()
        dxy = dxy_data['Time Series FX (Daily)'][list(dxy_data['Time Series FX (Daily)'].keys())[0]]['4. close']
        liq = requests.get('https://api.coinglass.com/api/v1/futures/liquidation').json()['data']['totalLiquidation']
        return float(btc_price), float(vix), float(dxy), float(liq)
    except:
        return 117000, 15.0, 100.0, 1000000

def predict_price():
    btc, vix, dxy, liq = get_data()
    macd = 0.31 * (btc * 0.01)
    trend_striker = 0.23 * (btc * 0.005)
    fractal = 0.14 * (btc * 0.008)
    entropy = 0.08 * (1 if btc > 116000 else -1)
    liquidation = 0.06 * (-1 if liq > 2000000 else 1)
    lunar = 0.05 * (1 if btc > 115000 else -1)
    dxy_factor = 0.04 * (-1 if dxy > 101 else 1)
    vix_factor = 0.04 * (-1 if vix > 20 else 1)
    m2 = 0.04 * (1 if btc > 117000 else -1)
    hashrate = 0.03 * (1 if btc > 116500 else -1)
    oi = 0.03 * (-1 if btc > 118000 else 1)
    trends = 0.02 * (-1 if btc > 119000 else 1)
    wintermute = 0.02 * (-1 if liq > 5000 else 1)
    day_factor = 0.02 * (1 if datetime.now().weekday() == 2 else -0.01 if datetime.now().weekday() == 5 else 0)
    forecast = (macd + trend_striker + fractal + entropy + liquidation + lunar + dxy_factor + vix_factor + m2 + hashrate + oi + trends + wintermute + day_factor)
    return btc + forecast * btc

def get_forecast():
    price = predict_price()
    h1 = price * 1.003
    h3 = price * 1.007
    h6 = price * 1.012
    h24 = price * 1.025
    rec = "🟢 Лонг" if price > get_data()[0] else "🔴 Шорт" if price < get_data()[0] * 0.99 else "⚪ Ждать"
    return f"Прогноз @CryptoOracle:\n1ч: ~{int(h1)} ±400\n3ч: ~{int(h3)} ±900\n6ч: ~{int(h6)} ±1600\n24ч: ~{int(h24)} ±3000\n{rec}"

def send_forecast():
    subscribers = load_subscribers()
    forecast = get_forecast()
    for chat_id in subscribers:
        bot.send_message(chat_id, forecast)

# Планирование каждые 15 минут
schedule.every(15).minutes.do(send_forecast)

# Обработка команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = str(message.chat.id)
    subscribers = load_subscribers()
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
    bot.reply_to(message, "Подписка на @CryptoOracle оформлена! Прогнозы каждые 15 минут.")

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)