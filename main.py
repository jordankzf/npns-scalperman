from binance import Client, ThreadedWebsocketManager
from binance.enums import *
import config
import pandas as pd
import numpy as np
from ta.momentum import StochasticOscillator
from ta.volume import ForceIndexIndicator, VolumeWeightedAveragePrice
import winsound

# Set variables
TRADE_SYMBOL = "BTCUSDT"
SLIPPAGE = 0.999

# Initialize Binance client
client = Client(config.API_KEY, config.API_SECRET)

# Grab latest candlesticks from 1 hour ago till now (total of 60)
klines = client.get_historical_klines(TRADE_SYMBOL, Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC")

# Convert klines to numpy array to truncate unimportant columns
npKlines = np.array(klines)
klines = npKlines[:,:6]

# Convert numpy array to Pandas dataframe and name each column
btc_df = pd.DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

# Convert API string values to float
btc_df = btc_df.astype(float)

# Save/load processed klines data as CSV file (for debugging purposes)
# btc_df.to_csv('btc_bars3.csv')
# btc_df = pd.read_csv('btc_bars3.csv', index_col=0)

# Convert unix timestamp to human readable datetime
btc_df.set_index('Time', inplace=True)
btc_df.index = pd.to_datetime(btc_df.index, unit='ms')

twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
# start is required to initialise its internal loop
twm.start()

def calcIndicators(btc_df):
    global attemptPurchase, activeOrder
    # Clone dataframe
    withIndicators_df = btc_df.copy()

    # Calculate TA indicators
    stoch_indicator = StochasticOscillator(close=withIndicators_df['Close'], high=withIndicators_df['High'], low=withIndicators_df['Low'])
    force_index_indicator = ForceIndexIndicator(close=withIndicators_df['Close'], volume=withIndicators_df['Volume'])
    vwap_indicator = VolumeWeightedAveragePrice(close=withIndicators_df['Close'], high=withIndicators_df['High'], low=withIndicators_df['Low'], volume=withIndicators_df['Volume'])

    # Add TA indicators as columns to cloned dataframe
    withIndicators_df['Stoch K'] = stoch_indicator.stoch()
    withIndicators_df['Force Index'] = force_index_indicator.force_index()
    withIndicators_df['VWAP'] = vwap_indicator.volume_weighted_average_price()

    # Grab latest tick indicator values
    current_stochK = withIndicators_df.tail(1)['Stoch K'].values[0]
    current_FI = withIndicators_df.tail(1)['Force Index'].values[0]
    current_VWAP = withIndicators_df.tail(1)['VWAP'].values[0]
    currentClose = withIndicators_df.tail(1)['Close'].values[0]

    # Grab average indicator value
    # average_FI = withIndicators_df.tail(60)['Force Index'].mean()

    # print("StochK is {:.2f}".format(current_stochK))
    # print("Force Index is {:.2f}".format(current_FI))
    # print("VWAP is {:.2f}".format(current_VWAP))
    # print("Current Price is {:.2f}".format(currentClose))

    if current_stochK <= 20 and current_FI <= -2000 and currentClose < current_VWAP:
        print("Time to buy!")
        # winsound.Beep(440, 5000)
        if not activeOrder:
            orderType = "b"
            attemptPurchase = True
    # latest_stoch = withIndicators_df[-1:].values[0][5]

    # print(latest_stoch)

def appendRow(candle):
    global btc_df
    candle['t'] = pd.to_datetime(candle['t'], unit='ms')

    btc_df.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']), float(candle['c']), float(candle['v'])]

    # Trim to latest 120 rows
    btc_df = btc_df.tail(120)

    # print (btc_df)
    # btc_df = btc_df.append(new_row, ignore_index=False)

    calcIndicators(btc_df)

def handle_socket_candle(message):
    candle = message['k']

    # is_candle_closed = candle['x']
    appendRow(candle)

previousPrice = 99999.0
currentPrice = 99999.0
stopPrice = 99999.0
newStopPrice = 99999.0
firstRun = True
attemptPurchase = False
activeOrder = False
orderType = "b"
orderAmountUSDT = 10

def handle_socket_order(msg):
    global firstRun, previousPrice, stopPrice, newStopPrice, attemptPurchase, activeOrder, orderType, orderAmountUSDT
    if attemptPurchase:
        if orderType == "b":
            if firstRun:
                previousPrice = float(msg["a"])
                print("Initial price is " + str(previousPrice))
                stopPrice = previousPrice / 0.999
                print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
                firstRun = False
            else:
                currentPrice = float(msg["a"])
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice < previousPrice:
                    # print("Current price is " + str(currentPrice))
                    newStopPrice = currentPrice / 0.999

                    if newStopPrice < stopPrice:
                        stopPrice = newStopPrice
                        print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                if currentPrice >= stopPrice:
                    print("Bought at " + str(currentPrice))
                    order = client.order_market_buy(
                        symbol=TRADE_SYMBOL,
                        quoteOrderQty=orderAmountUSDT)

                    print(order)

                    attemptPurchase = False
                    activeOrder = True
                    firstRun = True

                    previousPrice = currentPrice
        elif orderType == "s":
            if firstRun:
                previousPrice = float(msg["a"])
                print("Initial price is " + str(previousPrice))
                stopPrice = previousPrice * 0.999
                print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
                firstRun = False
            else:
                currentPrice = float(msg["a"])
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice > previousPrice:
                    # print("Current price is " + str(currentPrice))
                    newStopPrice = currentPrice * 0.999

                    if newStopPrice > stopPrice:
                        stopPrice = newStopPrice
                        print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                if currentPrice <= stopPrice:
                    print("Sold at " + str(currentPrice))
                    attemptPurchase = False
                    activeOrder = True
                    firstRun = True

                    previousPrice = currentPrice

twm.start_kline_socket(callback=handle_socket_candle, symbol=TRADE_SYMBOL)

twm.start_symbol_book_ticker_socket(callback=handle_socket_order, symbol=TRADE_SYMBOL)

twm.join()

