import requests
import telebot
import time
from datetime import datetime
import json
import os
from flask import Flask, request

# Конфигурация
BOT_TOKEN = '8454820081:AAFTjnT2oyyWmX0J8PLQmcDE0tC82TFcJKw'
ALPHA_VANTAGE_KEY = 'TNRGDW0XZE622EKD'
SUBSCRIBERS_FILE = 'subscribers.json'
CACHE_TIME = 300  # 5 минут кэширования

# Инициализация
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Глобальные переменные для кэша
last_data = None
last_update = 0

# Webhook для Telegram
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'ok'

# Проверка активности для UptimeRobot
@app.route('/', methods=['GET'])
def health_check():
    send_forecast()
    return 'OK'

# Загрузка и сохранение подписчиков
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

# Получение данных с кэшированием
def get_data():
    global last_data, last_update
    current_time = time.time()
    if last_data and (current_time - last_update) < CACHE_TIME:
        print(f"Using cached data: {last_data}")
        return last_data
    try:
        response = requests.get('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1').json()
        prices = response['prices']
        current_price = prices[-1][1]
        hourly_prices = [p[1] for p in prices[-12:]]  # Последние 12 часов
        volatility = sum(abs(hourly_prices[i] - hourly_prices[i-1]) / hourly_prices[i-1] for i in range(1, len(hourly_prices))) / (len(hourly_prices) - 1)
        fear_greed = requests.get('https://api.alternative.me/fng/?limit=1').json()['data'][0]['value']
        stablecoin_volume = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=tether,usd-coin&vs_currencies=usd').json()
        usdt = stablecoin_volume['tether']['usd']
        usdc = stablecoin_volume['usd-coin']['usd']
        dxy_data = requests.get(f'https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=DX&apikey={ALPHA_VANTAGE_KEY}').json()
        dxy = float(dxy_data['Time Series FX (Daily)'][list(dxy_data['Time Series FX (Daily)'].keys())[0]]['4. close'])
        liq = requests.get('https://api.coinglass.com/api/v1/futures/liquidation').json()['data']['totalLiquidation']
        last_data = (float(current_price), int(fear_greed), float(usdt + usdc), float(dxy), float(liq), volatility)
        last_update = current_time
        print(f"Updated data: BTC={current_price}, Fear={fear_greed}, Liq={liq}, Vol={volatility}")
        return last_data
    except Exception as e:
        print(f"Error in get_data: {e}")
        return 115740, 50, 100000000000, 100.0, 1000000, 0.0

# Прогнозирование цены
def predict_price():
    btc, fear_greed, stablecoin_volume, dxy, liq, volatility = get_data()
    macd = 0.31 * (btc * 0.001)
    trend_striker = 0.23 * (btc * 0.0005)
    fractal = 0.14 * (btc * 0.0008)
    entropy = 0.08 * (1 if btc > 116000 else -1)
    liquidation = 0.06 * (-1 if liq > 2000000 else 1)
    lunar = 0.05 * (1 if btc > 115000 else -1)
    dxy_factor = 0.04 * (-1 if dxy > 101 else 1)
    fear_factor = 0.04 * (-fear_greed / 100)  # Градация от 0 до 100
    stablecoin_factor = 0.04 * (1 if stablecoin_volume > 100000000000 else -1)
    hashrate = 0.03 * (1 if btc > 116500 else -1)
    oi = 0.03 * (-1 if btc > 118000 else 1)
    trends = 0.02 * (-1 if btc > 119000 else 1)
    wintermute = 0.02 * (-1 if liq > 5000 else 1)
    day_factor = 0.02 * (1 if datetime.now().weekday() == 2 else -0.01 if datetime.now().weekday() == 5 else 0)
    volatility_factor = 0.05 * (-1 if volatility > 0.02 else 1)  # Реакция на волатильность

    # Адаптивная корректировка
    if liq > 2000000:
        liquidation *= 1.5
    if volatility > 0.02:
        volatility_factor *= 2

    forecast = (macd + trend_striker + fractal + entropy + liquidation + lunar + dxy_factor + fear_factor + stablecoin_factor + hashrate + oi + trends + wintermute + day_factor + volatility_factor) / btc
    return btc + forecast * btc

# Формирование прогноза с временем
def get_forecast():
    price = predict_price()
    h1 = price * 1.003
    h3 = price * 1.007
    h6 = price * 1.012
    h24 = price * 1.025
    rec = "🟢 Лонг" if price > get_data()[0] else "🔴 Шорт" if price < get_data()[0] * 0.99 else "⚪ Ждать"
    timestamp = datetime.now().strftime("%H:%M")
    return f"Прогноз BitcoinOracle ({timestamp}):\n1ч: ~{int(h1)} USD ±400\n3ч: ~{int(h3)} USD ±900\n6ч: ~{int(h6)} USD ±1600\n24ч: ~{int(h24)} USD ±3000\n{rec}"

# Отправка прогноза
def send_forecast():
    subscribers = load_subscribers()
    forecast = get_forecast()
    for chat_id in subscribers:
        bot.send_message(chat_id, forecast)

# Обработка команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = str(message.chat.id)
    subscribers = load_subscribers()
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
    bot.reply_to(message, "Подписка на BitcoinOracle оформлена! Прогнозы каждые 14 минут при активности.")

# Запуск приложения
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))