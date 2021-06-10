from binance import Client, ThreadedWebsocketManager
from binance.enums import *
from binance.helpers import round_step_size
import config
import pandas as pd
import numpy as np
from ta.momentum import StochasticOscillator
# from ta.volume import ForceIndexIndicator, VolumeWeightedAveragePrice
from signal import signal, SIGINT
from sys import exit

# Constants
TRADE_SYMBOL = 'THETAUSDT'
FIAT_COIN = 'USDT'
BASE_PRECISION = 0.001
QUOTE_PRECISION = 0.000001
COMMISSION = 0.0006
TAKE_PROFIT = 1.003
BUY_SLIPPAGE = 1.003
SELL_SLIPPAGE = 0.002
DOUBLE_DOWN_TARGET = 0.994
INITIAL_PURCHASE_SIZE = 20

class Klines_VO(object):
    base_df = None
    with_indicators_df = None

class Trail_VO(object):
    # Ordering variables
    previous_price = None
    current_price = None
    stop_price = None
    new_stop_price = None
    last_buy_price = None
    order_type = 'b'
    trailing_order_first_run = True
    hunting = False
    have_open_position = False
    open_positions_count = 0
    current_purchase_size = None
    buy_orders_count = 0
    sell_orders_count = 0

class Wallet_VO(object):
    # Wallet_VO variables
    quote_balance = 0
    base_balance = 0
    quote_spent = 0
    profit = 0

def get_formatted_klines():
    # Initialize Binance client

    # Grab latest candlesticks from 1 hour ago till now (total of 60)
    klines = client.get_historical_klines(TRADE_SYMBOL, Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC")

    # Convert klines to numpy array to truncate unimportant columns
    np_klines = np.array(klines)
    klines = np_klines[:,:6]

    # Convert numpy array to Pandas dataframe and name each column
    Klines_VO.base_df = pd.DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

    # Convert API string values to float
    Klines_VO.base_df = Klines_VO.base_df.astype(float)

    # Convert unix timestamp to human readable datetime
    Klines_VO.base_df.set_index('Time', inplace=True)
    Klines_VO.base_df.index = pd.to_datetime(Klines_VO.base_df.index, unit='ms')

    # Save/load processed klines data as CSV file (for debugging purposes)
    # Klines_VO.base_df.to_csv('base_bars3.csv')
    # Klines_VO.base_df = pd.read_csv('base_bars3.csv', index_col=0)

def update_balance():
    Wallet_VO.quote_balance = float(client.get_asset_balance(asset=FIAT_COIN)['free'])
    # Wallet_VO.base_balance = float(client.get_asset_balance(asset='BTC')['free'])

def print_balance():
    print("quote_balance is {:.2f}".format(Wallet_VO.quote_balance))
    print("quote_spent is {:.2f}".format(Wallet_VO.quote_spent))
    print("base_balance is {:.2f}".format(Wallet_VO.base_balance))
    
def calc_cost_basis():
    average_price = Wallet_VO.quote_spent / Wallet_VO.base_balance
    return average_price / (1 - COMMISSION * 2)

def candle_listener(candle_tick):
    candle = candle_tick['k']

    candle['t'] = pd.to_datetime(candle['t'], unit='ms')

    Klines_VO.base_df.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']), float(candle['c']), float(candle['v'])]

    # Trim to latest 120 rows
    Klines_VO.base_df = Klines_VO.base_df.tail(120)

    # print (Klines_VO.base_df)
    # Klines_VO.base_df = Klines_VO.base_df.append(new_row, ignore_index=False)

    # Clone dataframe
    Klines_VO.with_indicators_df = Klines_VO.base_df.copy()

    # Calculate TA indicators
    stoch_indicator = StochasticOscillator(close=Klines_VO.with_indicators_df['Close'], high=Klines_VO.with_indicators_df['High'], low=Klines_VO.with_indicators_df['Low'])
    # force_index_indicator = ForceIndexIndicator(close=Klines_VO.with_indicators_df['Close'], volume=Klines_VO.with_indicators_df['Volume'])
    # vwap_indicator = VolumeWeightedAveragePrice(close=Klines_VO.with_indicators_df['Close'], high=Klines_VO.with_indicators_df['High'], low=Klines_VO.with_indicators_df['Low'], volume=Klines_VO.with_indicators_df['Volume'])

    # Add TA indicators as columns to cloned dataframe
    Klines_VO.with_indicators_df['Stoch K'] = stoch_indicator.stoch()
    # Klines_VO.with_indicators_df['Force Index'] = force_index_indicator.force_index()
    # Klines_VO.with_indicators_df['VWAP'] = vwap_indicator.volume_weighted_average_price()

    # Grab latest tick indicator values
    current_stochK = Klines_VO.with_indicators_df.tail(1)['Stoch K'].values[0]
    # current_FI = Klines_VO.with_indicators_df.tail(1)['Force Index'].values[0]
    # current_VWAP = Klines_VO.with_indicators_df.tail(1)['VWAP'].values[0]
    # currentClose = Klines_VO.with_indicators_df.tail(1)['Close'].values[0]

    # Grab average indicator value
    # average_FI = Klines_VO.with_indicators_df.tail(60)['Force Index'].mean()

    # print("StochK is {:.2f}".format(current_stochK))
    # print("Force Index is {:.2f}".format(current_FI))
    # print("VWAP is {:.2f}".format(current_VWAP))
    # print("Current Price is {:.2f}".format(currentClose))

    # if current_FI <= -500 and current_stochK <= 20 and not Trail_VO.have_open_position:
    if current_stochK <= 8 and not Trail_VO.have_open_position:
        Trail_VO.order_type = "b"
        Trail_VO.hunting = True

def book_ticker_listener(book_tick):
    best_ask = float(book_tick["a"])
    best_bid = float(book_tick["b"])

    if Trail_VO.have_open_position:
        # If I'm at profit
        if best_bid > calc_cost_basis() * TAKE_PROFIT:
            Trail_VO.order_type = "s"
            Trail_VO.hunting = True
        # If price dropped further
        if best_ask < (Trail_VO.last_buy_price * DOUBLE_DOWN_TARGET):
            Trail_VO.order_type = "b"
            Trail_VO.hunting = True
    if Trail_VO.hunting:
        if Trail_VO.order_type == "b":
            if Trail_VO.trailing_order_first_run:
                Trail_VO.previous_price = best_ask
                print("Initial price is " + str(Trail_VO.previous_price))
                Trail_VO.stop_price = Trail_VO.previous_price * BUY_SLIPPAGE
                print("Initial Trailing Stop Buy Price set to {:.4f}".format(Trail_VO.stop_price))
                Trail_VO.trailing_order_first_run = False
            else:
                Trail_VO.current_price = best_ask
                # if Trail_VO.current_price == Trail_VO.previous_price:
                #     print("The price has stayed the same")
                if Trail_VO.current_price < Trail_VO.previous_price:
                    # print("Current price is " + str(Trail_VO.current_price))
                    Trail_VO.new_stop_price = Trail_VO.current_price * BUY_SLIPPAGE

                    if Trail_VO.new_stop_price < Trail_VO.stop_price:
                        Trail_VO.stop_price = Trail_VO.new_stop_price
                        print("Trailing Stop Buy Price updated to {:.4f}".format(Trail_VO.stop_price))
                    
                if Trail_VO.current_price >= Trail_VO.stop_price:
                    print("Bought at " + str(Trail_VO.current_price))
                    buy()
                    Trail_VO.last_buy_price = Trail_VO.current_price
                    Trail_VO.hunting = False
                    Trail_VO.have_open_position = True
                    Trail_VO.trailing_order_first_run = True

                Trail_VO.previous_price = Trail_VO.current_price
                
        elif Trail_VO.order_type == "s":
            if Trail_VO.trailing_order_first_run:
                Trail_VO.previous_price = best_bid
                print("Initial price is " + str(Trail_VO.previous_price))
                stop_price = Trail_VO.previous_price - Trail_VO.previous_price * SELL_SLIPPAGE
                print("Initial Trailing Stop Sell Price set to {:.4f}".format(stop_price))
                Trail_VO.trailing_order_first_run = False
            else:
                Trail_VO.current_price = best_bid
                # if Trail_VO.current_price == Trail_VO.previous_price:
                #     print("The price has stayed the same")
                if Trail_VO.current_price > Trail_VO.previous_price:
                    # print("Current price is " + str(Trail_VO.current_price))
                    Trail_VO.new_stop_price = Trail_VO.current_price - Trail_VO.current_price * SELL_SLIPPAGE

                    if Trail_VO.new_stop_price > Trail_VO.stop_price:
                        Trail_VO.stop_price = Trail_VO.new_stop_price
                        print("Trailing Stop Sell updated to {:.4f}".format(Trail_VO.stop_price))
                    
                if Trail_VO.current_price <= Trail_VO.stop_price and Trail_VO.current_price:
                    print("Sold at " + str(Trail_VO.current_price))
                    sell()

                Trail_VO.previous_price = Trail_VO.current_price

def buy():
    print("before buy")
    print_balance()

    if Trail_VO.open_positions_count == 0:
        Trail_VO.current_purchase_size = INITIAL_PURCHASE_SIZE
    else:
        Trail_VO.current_purchase_size *= 2

    quote_amount = Trail_VO.current_purchase_size

    rounded_amount = round_step_size(quote_amount, QUOTE_PRECISION)
    
    if quote_amount <= Wallet_VO.quote_balance:
        order = client.order_market_buy(
            symbol=TRADE_SYMBOL,
            quoteOrderQty=rounded_amount)

        print("buy")
        print(order)

        Wallet_VO.quote_balance -= float(order['cummulativeQuoteQty'])
        Wallet_VO.quote_spent += float(order['cummulativeQuoteQty'])
        Wallet_VO.base_balance += float(order['executedQty'])
        Trail_VO.open_positions_count += 1

    Trail_VO.buy_orders_count += 1

    print("after buy")
    print_balance()

    print("Target Profit")
    print(calc_cost_basis() * TAKE_PROFIT)

def sell():
    print("before sell")
    print_balance()

    rounded_amount = round_step_size(Wallet_VO.base_balance, BASE_PRECISION)

    try:
        order = client.order_market_sell(
        symbol=TRADE_SYMBOL,
        quantity=rounded_amount)
    except Exception as e:
        print("an exception occured - {}".format(e))
    else:
        print("sell")
        print(order)
        
        Wallet_VO.quote_balance += float(order['cummulativeQuoteQty'])
        real_cost = float(order['cummulativeQuoteQty']) / float(order['executedQty'])
        Wallet_VO.profit += (real_cost / calc_cost_basis() * Wallet_VO.quote_spent) - Wallet_VO.quote_spent
        
        print("Profit: {:.4f}".format(Wallet_VO.profit))
        Wallet_VO.base_balance = 0
        Wallet_VO.quote_spent = 0
        
        Trail_VO.open_positions_count = 0
        Trail_VO.sell_orders_count += 1

        Trail_VO.hunting = False
        Trail_VO.have_open_position = False
        Trail_VO.trailing_order_first_run = True

        print("after sell")
        print_balance()

def signal_handler(signal_received, frame):
    print('SIGINT or CTRL-C detected. Exiting gracefully')
    twm.stop()
    exit(0)

if __name__ == '__main__':
    # Tell Python to run the handler() function when SIGINT is recieved
    signal(SIGINT, signal_handler)

    client = Client(config.API_KEY, config.API_SECRET, testnet=False)
    client.API_URL = 'https://api2.binance.com/api'

    get_formatted_klines()

    update_balance()

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