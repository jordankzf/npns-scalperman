from binance import Client, ThreadedWebsocketManager
from binance.enums import *
from binance.helpers import round_step_size
import config
import pandas as pd
import numpy as np
from ta.momentum import StochasticOscillator
from ta.volume import ForceIndexIndicator, VolumeWeightedAveragePrice
from signal import signal, SIGINT
from sys import exit

# Constants
TRADE_SYMBOL = 'THETAUSDT'
FIAT_COIN = 'USDT'
BASE_PRECISION = 0.001
QUOTE_PRECISION = 0.000001
COMMISSION = 1.0006
BUY_SLIPPAGE = 0.997
SELL_SLIPPAGE = 0.998
DOUBLE_DOWN_TARGET = 0.994
INITIAL_PURCHASE_SIZE = 10

# Ordering variables
previous_price = 99999.0
current_price = 99999.0
stop_price = 99999.0
new_stop_price = 99999.0
last_buy_price = 99999.0
order_type = 'b'
trailing_order_first_run = True
attempt_order = False
have_open_position = False
open_positions_count = 0
current_purchase_size = 10
buy_orders_count = 0
sell_orders_count = 0

# Wallet variables
quote_balance = 0
base_balance = 0
quote_spent = 0
profit = 0

# Initialize Binance client
client = Client(config.API_KEY, config.API_SECRET, testnet=False)
client.API_URL = 'https://api2.binance.com/api'

# Grab latest candlesticks from 1 hour ago till now (total of 60)
klines = client.get_historical_klines(TRADE_SYMBOL, Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC")

# Convert klines to numpy array to truncate unimportant columns
np_klines = np.array(klines)
klines = np_klines[:,:6]

# Convert numpy array to Pandas dataframe and name each column
base_df = pd.DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

# Convert API string values to float
base_df = base_df.astype(float)

# Convert unix timestamp to human readable datetime
base_df.set_index('Time', inplace=True)
base_df.index = pd.to_datetime(base_df.index, unit='ms')

# Save/load processed klines data as CSV file (for debugging purposes)
# base_df.to_csv('base_bars3.csv')
# base_df = pd.read_csv('base_bars3.csv', index_col=0)

def updateBalance():
    global quote_balance, base_balance
    quote_balance = float(client.get_asset_balance(asset=FIAT_COIN)['free'])
    # base_balance = float(client.get_asset_balance(asset='BTC')['free'])

def printBalance():
    global quote_balance, base_balance, quote_spent
    print("quote_balance is {:.2f}".format(quote_balance))
    print("quote_spent is {:.2f}".format(quote_spent))
    print("base_balance is {:.2f}".format(base_balance))
    

def candle_listener(message):
    global base_df, attempt_order, have_open_position, order_type
    candle = message['k']

    candle['t'] = pd.to_datetime(candle['t'], unit='ms')

    base_df.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']), float(candle['c']), float(candle['v'])]

    # Trim to latest 120 rows
    base_df = base_df.tail(120)

    # print (base_df)
    # base_df = base_df.append(new_row, ignore_index=False)

    # Clone dataframe
    withIndicators_df = base_df.copy()

    # Calculate TA indicators
    stoch_indicator = StochasticOscillator(close=withIndicators_df['Close'], high=withIndicators_df['High'], low=withIndicators_df['Low'])
    # force_index_indicator = ForceIndexIndicator(close=withIndicators_df['Close'], volume=withIndicators_df['Volume'])
    # vwap_indicator = VolumeWeightedAveragePrice(close=withIndicators_df['Close'], high=withIndicators_df['High'], low=withIndicators_df['Low'], volume=withIndicators_df['Volume'])

    # Add TA indicators as columns to cloned dataframe
    withIndicators_df['Stoch K'] = stoch_indicator.stoch()
    # withIndicators_df['Force Index'] = force_index_indicator.force_index()
    # withIndicators_df['VWAP'] = vwap_indicator.volume_weighted_average_price()

    # Grab latest tick indicator values
    current_stochK = withIndicators_df.tail(1)['Stoch K'].values[0]
    # current_FI = withIndicators_df.tail(1)['Force Index'].values[0]
    # current_VWAP = withIndicators_df.tail(1)['VWAP'].values[0]
    # currentClose = withIndicators_df.tail(1)['Close'].values[0]

    # Grab average indicator value
    # average_FI = withIndicators_df.tail(60)['Force Index'].mean()

    # print("StochK is {:.2f}".format(current_stochK))
    # print("Force Index is {:.2f}".format(current_FI))
    # print("VWAP is {:.2f}".format(current_VWAP))
    # print("Current Price is {:.2f}".format(currentClose))

    # if current_FI <= -500 and current_stochK <= 20 and not have_open_position:
    if current_stochK <= 8 and not have_open_position:
        order_type = "b"
        attempt_order = True

def calc_cost_basis():
    global quote_spent, base_balance
    return quote_spent / base_balance * COMMISSION * COMMISSION

def calc_take_profit():
    return calc_cost_basis() * 1.003

def book_ticker_listener(msg):
    global trailing_order_first_run, previous_price, stop_price, new_stop_price, attempt_order, have_open_position, order_type, last_buy_price, BUY_SLIPPAGE, SELL_SLIPPAGE
    if have_open_position:
        # If I'm at profit
        if float(msg["b"]) > calc_take_profit():
            order_type = "s"
            attempt_order = True
        # If price dropped further
        if float(msg["a"]) < (last_buy_price * DOUBLE_DOWN_TARGET):
            order_type = "b"
            attempt_order = True
    if attempt_order:
        if order_type == "b":
            if trailing_order_first_run:
                previous_price = float(msg["a"])
                print("Initial price is " + str(previous_price))
                stop_price = previous_price / BUY_SLIPPAGE
                print("Initial Trailing Stop Buy Price set to {:.4f}".format(stop_price))
                trailing_order_first_run = False
            else:
                current_price = float(msg["a"])
                # if current_price == previous_price:
                #     print("The price has stayed the same")
                if current_price < previous_price:
                    # print("Current price is " + str(current_price))
                    new_stop_price = current_price / BUY_SLIPPAGE

                    if new_stop_price < stop_price:
                        stop_price = new_stop_price
                        print("Trailing Stop Buy Price updated to {:.4f}".format(stop_price))
                    
                if current_price >= stop_price:
                    print("Bought at " + str(current_price))
                    buy(current_price)
                    last_buy_price = current_price
                    attempt_order = False
                    have_open_position = True
                    trailing_order_first_run = True

                previous_price = current_price
                
        elif order_type == "s":
            if trailing_order_first_run:
                previous_price = float(msg["b"])
                print("Initial price is " + str(previous_price))
                stop_price = previous_price * SELL_SLIPPAGE
                print("Initial Trailing Stop Sell Price set to {:.4f}".format(stop_price))
                trailing_order_first_run = False
            else:
                current_price = float(msg["b"])
                # if current_price == previous_price:
                #     print("The price has stayed the same")
                if current_price > previous_price:
                    # print("Current price is " + str(current_price))
                    new_stop_price = current_price * SELL_SLIPPAGE

                    if new_stop_price > stop_price:
                        stop_price = new_stop_price
                        print("Trailing Stop Sell updated to {:.4f}".format(stop_price))
                    
                if current_price <= stop_price and current_price:
                    print("Sold at " + str(current_price))
                    sell(current_price)

                previous_price = current_price

def buy(base_price):
    global quote_balance, base_balance, quote_spent, open_positions_count, INITIAL_PURCHASE_SIZE, current_purchase_size, buy_orders_count, previous_price
    print("before buy")
    printBalance()

    if open_positions_count == 0:
        current_purchase_size = INITIAL_PURCHASE_SIZE
    else:
        current_purchase_size *= 2

    quote_amount = current_purchase_size

    rounded_amount = round_step_size(quote_amount, QUOTE_PRECISION)
    
    if quote_amount <= quote_balance:
        order = client.order_market_buy(
            symbol=TRADE_SYMBOL,
            quoteOrderQty=rounded_amount)

        print("buy")
        print(order)

        quote_balance -= float(order['cummulativeQuoteQty'])
        quote_spent += float(order['cummulativeQuoteQty'])
        base_balance += float(order['executedQty'])
        open_positions_count += 1

    buy_orders_count += 1

    print("after buy")
    printBalance()

def sell(base_price):
    global quote_balance, base_balance, quote_spent, open_positions_count, sell_orders_count, profit, attempt_order, have_open_position, trailing_order_first_run, previous_price
    print("before sell")
    printBalance()

    rounded_amount = round_step_size(base_balance, BASE_PRECISION)

    try:
        order = client.order_market_sell(
        symbol=TRADE_SYMBOL,
        quantity=rounded_amount)
    except Exception as e:
        print("an exception occured - {}".format(e))
    else:
        print("sell")
        print(order)
        
        quote_balance += float(order['cummulativeQuoteQty'])
        profit += (float(order['cummulativeQuoteQty']) - quote_spent) / COMMISSION / COMMISSION
        print("Profit: {:.4f}".format(profit))
        base_balance = 0
        quote_spent = 0
        
        open_positions_count = 0
        sell_orders_count += 1

        attempt_order = False
        have_open_position = False
        trailing_order_first_run = True

        print("after sell")
        printBalance()

def handler(signal_received, frame):
    print('SIGINT or CTRL-C detected. Exiting gracefully')
    twm.stop()
    client.close_connection()
    exit(0)

if __name__ == '__main__':
    # Tell Python to run the handler() function when SIGINT is recieved
    signal(SIGINT, handler)

    updateBalance()

    twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
    # start is required to initialise its internal loop
    twm.start()

    twm.start_kline_socket(callback=candle_listener, symbol=TRADE_SYMBOL)

    twm.start_symbol_book_ticker_socket(callback=book_ticker_listener, symbol=TRADE_SYMBOL)

    twm.join()

    print('Running. Press CTRL-C to exit.')
    while True:
        # Do nothing and hog CPU forever until SIGINT received.
        pass