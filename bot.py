from binance import Client, ThreadedWebsocketManager
from binance.enums import *
from binance.helpers import round_step_size
import config_testnet as config
import pandas as pd
import numpy as np
from ta.momentum import StochasticOscillator
from ta.volume import ForceIndexIndicator, VolumeWeightedAveragePrice
import winsound

# Set variables
TRADE_SYMBOL = "BTCUSDT"
tick_size = 0.000001

commission = 1.0006
slippage = 0.999

previousPrice = 99999.0
currentPrice = 99999.0
stopPrice = 99999.0
newStopPrice = 99999.0
firstRun = True
attemptPurchase = False
activeOrder = False
orderType = "b"
lastPurchasePriceAt = 99999.0
noOfOrders = 0

USDT_balance = 5000
BTC_balance = 0
USDT_spent = 0
purchase_size = 100

buy_orders = 0
sell_orders = 0

# Initialize Binance client
client = Client(config.API_KEY, config.API_SECRET, testnet=True)

# Grab latest candlesticks from 1 hour ago till now (total of 60)
klines = client.get_historical_klines(TRADE_SYMBOL, Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC")

# Convert klines to numpy array to truncate unimportant columns
npKlines = np.array(klines)
klines = npKlines[:,:6]

# Convert numpy array to Pandas dataframe and name each column
btc_df = pd.DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

# Convert API string values to float
btc_df = btc_df.astype(float)

# Convert unix timestamp to human readable datetime
btc_df.set_index('Time', inplace=True)
btc_df.index = pd.to_datetime(btc_df.index, unit='ms')

# Save/load processed klines data as CSV file (for debugging purposes)
# btc_df.to_csv('btc_bars3.csv')
# btc_df = pd.read_csv('btc_bars3.csv', index_col=0)

def updateBalance():
    global USDT_balance, BTC_balance
    USDT_balance = float(client.get_asset_balance(asset='USDT')['free'])
    # BTC_balance = float(client.get_asset_balance(asset='BTC')['free'])

def calcIndicators(btc_df):
    global attemptPurchase, activeOrder, orderType
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

    # if current_FI <= -500 and current_stochK <= 20 and not activeOrder:
    if not activeOrder:
        orderType = "b"
        attemptPurchase = True

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

def calcCostBasis():
    global USDT_spent, BTC_balance
    return USDT_spent / BTC_balance * commission * commission

def calcProfitTarget():
    return calcCostBasis() * 1.003

def handle_socket_order(msg):
    global firstRun, previousPrice, stopPrice, newStopPrice, attemptPurchase, activeOrder, orderType, lastPurchasePriceAt, slippage
    if BTC_balance > 0:
        # If I'm at profit
        if float(msg["a"]) > calcProfitTarget():
            orderType = "s"
            attemptPurchase = True
        # If price dropped further
        if float(msg["a"]) < (lastPurchasePriceAt * 0.996):
            orderType = "b"
            attemptPurchase = True
    if attemptPurchase:
        if orderType == "b":
            if firstRun:
                previousPrice = float(msg["a"])
                # print("Initial price is " + str(previousPrice))
                stopPrice = previousPrice / slippage
                # print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
                firstRun = False
            else:
                currentPrice = float(msg["a"])
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice < previousPrice:
                    # print("Current price is " + str(currentPrice))
                    newStopPrice = currentPrice / slippage

                    if newStopPrice < stopPrice:
                        stopPrice = newStopPrice
                        # print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                if currentPrice >= stopPrice:
                    # print("Bought at " + str(currentPrice))
                    buy(currentPrice)
                    lastPurchasePriceAt = currentPrice
                    attemptPurchase = False
                    activeOrder = True
                    firstRun = True
        elif orderType == "s":
            if firstRun:
                previousPrice = float(msg["a"])
                # print("Initial price is " + str(previousPrice))
                stopPrice = previousPrice * slippage
                # print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
                firstRun = False
            else:
                currentPrice = float(msg["a"])
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice > previousPrice:
                    # print("Current price is " + str(currentPrice))
                    newStopPrice = currentPrice * slippage

                    if newStopPrice > stopPrice:
                        stopPrice = newStopPrice
                        # print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                if currentPrice <= stopPrice:
                    # print("Sold at " + str(currentPrice))
                    sell(currentPrice)
                    attemptPurchase = False
                    activeOrder = False
                    firstRun = True

                    previousPrice = currentPrice

def buy(BTC_price):
    global USDT_balance, BTC_balance, USDT_spent, noOfOrders, purchase_size, buy_orders, previousPrice

    # BTC_price = BTC_price * commission

    if noOfOrders == 0:
        purchase_size = 100
    else:
        purchase_size = purchase_size * 2

    USDT_amount = purchase_size
    
    if USDT_amount <= USDT_balance:
        order = client.order_market_buy(
            symbol=TRADE_SYMBOL,
            quoteOrderQty=USDT_amount)

        previousPrice = BTC_price

        print("buy")
        print(order)

        USDT_balance -= float(order['cummulativeQuoteQty'])
        USDT_spent += float(order['cummulativeQuoteQty'])
        BTC_balance += float(order['executedQty'])
        noOfOrders += 1

    buy_orders += 1

def sell(BTC_price):
    global USDT_balance, BTC_balance, USDT_spent, noOfOrders, sell_orders

    # BTC_price = BTC_price / commission

    rounded_amount = round_step_size(BTC_balance, tick_size)

    order = client.order_market_sell(
        symbol=TRADE_SYMBOL,
        quantity=rounded_amount)

    print("sell")
    print(order)
    
    USDT_balance += float(order['cummulativeQuoteQty'])
    BTC_balance -= float(order['executedQty'])
    USDT_spent -= float(order['cummulativeQuoteQty'])
    noOfOrders = 0

    sell_orders += 1

updateBalance()

twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
# start is required to initialise its internal loop
twm.start()

twm.start_kline_socket(callback=handle_socket_candle, symbol=TRADE_SYMBOL)

twm.start_symbol_book_ticker_socket(callback=handle_socket_order, symbol=TRADE_SYMBOL)

twm.join()

