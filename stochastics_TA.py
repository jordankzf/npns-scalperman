from binance import Client, ThreadedWebsocketManager
import btalib
import config
import pandas as pd
import json
from ta.momentum import StochasticOscillator

TRADE_SYMBOL = "BTCUSDT"

client = Client(config.API_KEY, config.API_SECRET)

klines = client.get_historical_klines(TRADE_SYMBOL, Client.KLINE_INTERVAL_1MINUTE, "1 hour ago UTC")

for line in klines:
    del line[5:]

btc_df = pd.DataFrame(klines, columns=['Date', 'Open', 'High', 'Low', 'Close'])
btc_df.set_index('Date', inplace=True)

# btc_df.to_csv('btc_bars3.csv')

# btc_df = pd.read_csv('btc_bars3.csv', index_col=0)
btc_df.index = pd.to_datetime(btc_df.index, unit='ms')

btc_df = btc_df.astype(float)

# stoch_indicator = StochasticOscillator(btc_df['Close'], btc_df['High'], btc_df['Low'])

# btc_df['stoch'] = stoch_indicator.stoch()

# print(btc_df[-1:])

# print(btc_df)

# stoch = btalib.stoch(btc_df)

# print(stoch.df.k[-1])

twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
# start is required to initialise its internal loop
twm.start()

def getLatestStoch(btc_df):
    stoch_indicator = StochasticOscillator(close=btc_df['Close'], high=btc_df['High'], low=btc_df['Low'])

    btc_df['stoch'] = stoch_indicator.stoch()

    latest_stoch = btc_df[-1:].values[0][5]

    print(latest_stoch)

    if (latest_stoch < 20):
        print("BUY! BUY! BUY!")
    else:
        print("patience young one")
    # print(btc_df['stoch'].values[0]

def appendRow(candle):
    global btc_df
    candle['t'] = pd.to_datetime(candle['t'], unit='ms')
    new_row = {'Date':candle['t'], 'Open':float(candle['o']), 'High':float(candle['h']), 'Low':float(candle['l']), 'Close':float(candle['c'])}
    btc_df = btc_df.append(new_row, ignore_index=True)

    getLatestStoch(btc_df)

    # stoch = btalib.stoch(btc_df)
    # print(stoch.df.k[-1])


def handle_socket_message(message):
    json_message = json.loads(json.dumps(message))
    candle = json_message['k']

    is_candle_closed = candle['x']
    
    if is_candle_closed:
        appendRow(candle)

twm.start_kline_socket(callback=handle_socket_message, symbol=TRADE_SYMBOL)

twm.join()

