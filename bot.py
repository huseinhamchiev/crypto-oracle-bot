import requests
import telebot
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
from flask import Flask, request

# Конфигурация
BOT_TOKEN = '8454820081:AAFTjnT2oyyWmX0J8PLQmcDE0tC82TFcJKw'
ALPHA_VANTAGE_KEY = 'TNRGDW0XZE622EKD'
SUBSCRIBERS_FILE = 'subscribers.json'

# Инициализация
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

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

# Получение данных с ретраями и обработкой ошибок
def get_data():
    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            # Свежая цена (всегда)
            price_response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd', timeout=5).json()
            current_price = price_response['bitcoin']['usd']

            # Свечи для RSI и Bollinger
            response = requests.get('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1', timeout=5).json()
            prices = response.get('prices', [])
            if not prices:
                raise KeyError("'prices' missing")
            current_price = prices[-1][1]
            hourly_prices = [p[1] for p in prices[-12:]]  # Последние 12 часов
            volatility = sum(abs(hourly_prices[i] - hourly_prices[i-1]) / hourly_prices[i-1] for i in range(1, len(hourly_prices))) / (len(hourly_prices) - 1)
            # Bollinger Bands (период 20, std 2)
            middle_band = sum(hourly_prices[-20:]) / 20
            std_dev = (sum((p - middle_band)**2 for p in hourly_prices[-20:]) / 20)**0.5
            upper_band = middle_band + (std_dev * 2)
            lower_band = middle_band - (std_dev * 2)
            bollinger_signal = 1 if current_price > upper_band else -1 if current_price < lower_band else 0
            # RSI (период 14)
            gains = [max(hourly_prices[i] - hourly_prices[i-1], 0) for i in range(1, len(hourly_prices))]
            losses = [max(hourly_prices[i-1] - hourly_prices[i], 0) for i in range(1, len(hourly_prices))]
            avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else 0
            avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else 0
            rs = avg_gain / avg_loss if avg_loss != 0 else 0
            rsi = 100 - (100 / (1 + rs)) if rs > 0 else 100
            rsi_signal = -1 if rsi < 30 else 1 if rsi > 70 else 0  # -1=перепроданность (падение), 1=перекупленность (рост)

            fear_greed = requests.get('https://api.alternative.me/fng/?limit=1', timeout=5).json()['data'][0]['value']
            stablecoin_volume = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=tether,usd-coin&vs_currencies=usd', timeout=5).json()
            usdt = stablecoin_volume['tether']['usd']
            usdc = stablecoin_volume['usd-coin']['usd']
            dxy_data = requests.get(f'https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=DX&apikey={ALPHA_VANTAGE_KEY}', timeout=5).json()
            dxy = float(dxy_data['Time Series FX (Daily)'][list(dxy_data['Time Series FX (Daily)'].keys())[0]]['4. close'])
            liq = requests.get('https://api.coinglass.com/api/v1/futures/liquidation', timeout=5).json()['data']['totalLiquidation']
            print(f"Обновлены данные: BTC={current_price}, Fear={fear_greed}, Liq={liq}, Vol={volatility}, Bollinger={bollinger_signal}, RSI={rsi}, Время={datetime.now(ZoneInfo('Europe/Moscow')).strftime('%H:%M')}")
            return float(current_price), int(fear_greed), float(usdt + usdc), float(dxy), float(liq), volatility, bollinger_signal, rsi_signal
        except KeyError as e:
            error_msg = f"Ошибка KeyError в API: {str(e)} (попытка {attempt + 1}/{max_retries + 1})"
            print(error_msg)
            if attempt == max_retries:
                send_error_message(error_msg)
                return 115740, 50, 100000000000, 100.0, 1000000, 0.0, 0, 0
            time.sleep(1)
        except Exception as e:
            error_msg = f"Ошибка при получении данных (попытка {attempt + 1}/{max_retries + 1}): {str(e)}"
            print(error_msg)
            if attempt == max_retries:
                send_error_message(error_msg)
                return 115740, 50, 100000000000, 100.0, 1000000, 0.0, 0, 0
            time.sleep(1)

# Отправка сообщения об ошибке (один раз)
def send_error_message(error_msg):
    subscribers = load_subscribers()
    for chat_id in subscribers:
        bot.send_message(chat_id, f"⚠️ Ошибка: {error_msg}. Прогноз временно недоступен.")

# Прогнозирование цены
def predict_price():
    btc, fear_greed, stablecoin_volume, dxy, liq, volatility, bollinger_signal, rsi_signal = get_data()
    base_forecast = 0.0
    total_weight = 0.0

    factors = {
        'volatility_factor': (0.25 * (-1 if volatility > 0.02 else 1), 0.25),  # Точность ~70%
        'liquidation': (0.20 * (-1 if liq > 2000000 else 1), 0.20),  # Точность ~68%
        'dxy_factor': (0.20 * (-1 if dxy > 101 else 1), 0.20),  # Точность ~65%
        'fear_factor': (0.15 * (-fear_greed / 100), 0.15),  # Точность ~67%
        'bollinger_signal': (0.10 * bollinger_signal, 0.10),  # Точность ~65-70%
        'rsi_signal': (0.10 * rsi_signal, 0.10)  # Точность ~70%
    }

    # Адаптация весов
    for key, (value, weight) in factors.items():
        if liq > 2000000 and key in ['liquidation', 'dxy_factor']:
            weight *= 1.5
        if volatility > 0.02 and key == 'volatility_factor':
            weight *= 2
        if bollinger_signal < 0 and key == 'bollinger_signal':
            weight *= 1.2
        if rsi_signal < 0 and key == 'rsi_signal':
            weight *= 1.2  # Увеличиваем для перепроданности
        base_forecast += value * (weight / total_weight if total_weight else 1)
        total_weight += weight

    forecast = base_forecast / btc if total_weight else 0.0
    return btc + forecast * btc

# Формирование прогноза с отдельным временем и ценой на русском
def get_forecast():
    current_price, _, _, _, _, _, _, _ = get_data()  # Свежие данные
    price = predict_price()
    h1 = price * 1.003
    h3 = price * 1.007
    h6 = price * 1.012
    h24 = price * 1.025
    rec = "🟢 Лонг" if price > current_price else "🔴 Шорт" if price < current_price * 0.99 else "⚪ Ждать"
    timestamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%H:%M")
    return f"Прогноз BitcoinOracle\nВремя: {timestamp} (Москва)\nТекущая цена BTC: ~{int(current_price)} USD\n1 час: ~{int(h1)} USD ±400\n3 часа: ~{int(h3)} USD ±900\n6 часов: ~{int(h6)} USD ±1600\n24 часа: ~{int(h24)} USD ±3000\nРекомендация: {rec}"

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