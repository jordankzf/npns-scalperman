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
import requests

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

if len(config.WEBHOOK) > 0:
    def print(message):
        r = requests.post(config.WEBHOOK, data={"content": message})

class Klines(object):
    base_df = None
    with_indicators_df = None

    def get_formatted_klines(self):
        klines = client.get_historical_klines(TRADE_SYMBOL, Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC")
        np_klines = np.array(klines)
        klines = np_klines[:,:6]
        Klines.base_df = pd.DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        Klines.base_df = Klines.base_df.astype(float)
        Klines.base_df.set_index('Time', inplace=True)
        Klines.base_df.index = pd.to_datetime(Klines.base_df.index, unit='ms')

        # Save/load processed klines data as CSV file (for debugging purposes)
        # Klines.base_df.to_csv('base_bars3.csv')
        # Klines.base_df = pd.read_csv('base_bars3.csv', index_col=0)

    def candle_listener(candle_tick):
        candle = candle_tick['k']

        candle['t'] = pd.to_datetime(candle['t'], unit='ms')

        Klines.base_df.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']), float(candle['c']), float(candle['v'])]

        # Trim to latest 120 rows
        Klines.base_df = Klines.base_df.tail(120)

        # print (Klines.base_df)
        # Klines.base_df = Klines.base_df.append(new_row, ignore_index=False)

        # Clone dataframe
        Klines.with_indicators_df = Klines.base_df.copy()

        # Calculate TA indicators
        stoch_indicator = StochasticOscillator(close=Klines.with_indicators_df['Close'], high=Klines.with_indicators_df['High'], low=Klines.with_indicators_df['Low'])
        # force_index_indicator = ForceIndexIndicator(close=Klines.with_indicators_df['Close'], volume=Klines.with_indicators_df['Volume'])
        # vwap_indicator = VolumeWeightedAveragePrice(close=Klines.with_indicators_df['Close'], high=Klines.with_indicators_df['High'], low=Klines.with_indicators_df['Low'], volume=Klines.with_indicators_df['Volume'])

        # Add TA indicators as columns to cloned dataframe
        Klines.with_indicators_df['Stoch K'] = stoch_indicator.stoch()
        # Klines.with_indicators_df['Force Index'] = force_index_indicator.force_index()
        # Klines.with_indicators_df['VWAP'] = vwap_indicator.volume_weighted_average_price()

        # Grab latest tick indicator values
        current_stochK = Klines.with_indicators_df.tail(1)['Stoch K'].values[0]
        # current_FI = Klines.with_indicators_df.tail(1)['Force Index'].values[0]
        # current_VWAP = Klines.with_indicators_df.tail(1)['VWAP'].values[0]
        # currentClose = Klines.with_indicators_df.tail(1)['Close'].values[0]

        # Grab average indicator value
        # average_FI = Klines.with_indicators_df.tail(60)['Force Index'].mean()

        # print("StochK is {:.2f}".format(current_stochK))
        # print("Force Index is {:.2f}".format(current_FI))
        # print("VWAP is {:.2f}".format(current_VWAP))
        # print("Current Price is {:.2f}".format(currentClose))

        # if current_FI <= -500 and current_stochK <= 20 and not Trail.have_open_position:
        if current_stochK <= 8 and not Trail.have_open_position and not Trail.hunting:
            print("I see a dip. Hold my beer, I'm going in!")
            Trail.order_type = "b"
            Trail.hunting = True

class Trail(object):
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

    def buy(self):
        if Trail.open_positions_count == 0:
            Trail.current_purchase_size = INITIAL_PURCHASE_SIZE
        else:
            Trail.current_purchase_size *= 2

        quote_amount = Trail.current_purchase_size

        rounded_amount = round_step_size(quote_amount, QUOTE_PRECISION)
        
        if quote_amount <= Wallet.quote_balance:
            order = client.order_market_buy(
                symbol=TRADE_SYMBOL,
                quoteOrderQty=rounded_amount)

            print(f"Buy Order Response {order}")

            Wallet.quote_balance -= float(order['cummulativeQuoteQty'])
            Wallet.quote_spent += float(order['cummulativeQuoteQty'])
            Wallet.base_balance += float(order['executedQty'])
            Trail.open_positions_count += 1

        Trail.buy_orders_count += 1

        print(
            f"Wallet after buying {Wallet.print()}\n"
            f"Target sell price is {Wallet.calc_cost_basis() * TAKE_PROFIT}"
        )

    def sell(self):
        rounded_amount = round_step_size(Wallet.base_balance, BASE_PRECISION)

        try:
            order = client.order_market_sell(
            symbol=TRADE_SYMBOL,
            quantity=rounded_amount)
        except Exception as e:
            print(f"an exception occured - {e}")
        else:
            print(f"Sell Order Response {order}")
            
            Wallet.quote_balance += float(order['cummulativeQuoteQty'])
            real_cost = float(order['cummulativeQuoteQty']) / float(order['executedQty'])
            this_profit = (real_cost / Wallet.calc_cost_basis() * Wallet.quote_spent) - Wallet.quote_spent
            Wallet.profit += this_profit
            
            print(
                f"Profit! I bestow upon you: {this_profit}\n"
                f"So far, I have earned you {Wallet.profit} this session."
            )

            Wallet.base_balance = 0
            Wallet.quote_spent = 0
            
            Trail.open_positions_count = 0
            Trail.sell_orders_count += 1

            Trail.hunting = False
            Trail.have_open_position = False
            Trail.trailing_order_first_run = True

            print(f"Wallet after selling {Wallet.print()}")

    def book_ticker_listener(book_tick):
        best_ask = float(book_tick["a"])
        best_bid = float(book_tick["b"])

        if Trail.have_open_position:
            # If I'm at profit
            if best_bid > Wallet.calc_cost_basis() * TAKE_PROFIT:
                Trail.order_type = "s"
                Trail.hunting = True
            # If price dropped further
            if best_ask < (Trail.last_buy_price * DOUBLE_DOWN_TARGET):
                Trail.order_type = "b"
                Trail.hunting = True
        if Trail.hunting:
            if Trail.order_type == "b":
                if Trail.trailing_order_first_run:
                    Trail.previous_price = best_ask
                    Trail.stop_price = Trail.previous_price * BUY_SLIPPAGE
                    print(
                        f"Initial buy price is {Trail.previous_price}\n"
                        f"Initial Trailing Stop Buy Price set to {Trail.stop_price}"
                    )
                    Trail.trailing_order_first_run = False
                else:
                    Trail.current_price = best_ask
                    # if Trail.current_price == Trail.previous_price:
                    #     print("The price has stayed the same")
                    if Trail.current_price < Trail.previous_price:
                        # print("Current price is " + str(Trail.current_price))
                        Trail.new_stop_price = Trail.current_price * BUY_SLIPPAGE

                        if Trail.new_stop_price < Trail.stop_price:
                            Trail.stop_price = Trail.new_stop_price
                            print(f"Trailing Stop Buy Price updated to {Trail.stop_price}")
                        
                    if Trail.current_price >= Trail.stop_price:
                        print(f"Trying to buy at {Trail.current_price}")
                        Trail.buy()
                        Trail.last_buy_price = Trail.current_price
                        Trail.hunting = False
                        Trail.have_open_position = True
                        Trail.trailing_order_first_run = True

                    Trail.previous_price = Trail.current_price
                
        elif Trail.order_type == "s":
            if Trail.trailing_order_first_run:
                Trail.previous_price = best_bid
                Trail.stop_price = Trail.previous_price - Trail.previous_price * SELL_SLIPPAGE
                print(
                    f"Initial sell price is {Trail.previous_price}\n"
                    f"Initial Trailing Stop Sell Price set to {Trail.stop_price}"
                )
                Trail.trailing_order_first_run = False
            else:
                Trail.current_price = best_bid
                # if Trail.current_price == Trail.previous_price:
                #     print("The price has stayed the same")
                if Trail.current_price > Trail.previous_price:
                    # print("Current price is " + str(Trail.current_price))
                    Trail.new_stop_price = Trail.current_price - Trail.current_price * SELL_SLIPPAGE

                    if Trail.new_stop_price > Trail.stop_price:
                        Trail.stop_price = Trail.new_stop_price
                        print(f"Trailing Stop Sell updated to {Trail.stop_price}")
                    
                if Trail.current_price <= Trail.stop_price and Trail.current_price:
                    print(f"Trying to sell at {Trail.current_price}")
                    Trail.sell()

                Trail.previous_price = Trail.current_price

class Wallet(object):
    # Wallet variables
    quote_balance = 0
    base_balance = 0
    quote_spent = 0
    profit = 0

    def print(self):
        print(
            f"Quote_balance: {Wallet.quote_balance}\n"
            f"Quote_spent: {Wallet.quote_spent}\n"
            f"Base_balance: {Wallet.base_balance}"
        )

    def calc_cost_basis(self):
        average_price = Wallet.quote_spent / Wallet.base_balance
        return average_price / (1 - COMMISSION * 2)

    def update_balance(self):
        Wallet.quote_balance = float(client.get_asset_balance(asset=FIAT_COIN)['free'])
        # Wallet.base_balance = float(client.get_asset_balance(asset='BTC')['free'])
    
class Binance_Bot:
    def __init__ (self):
        print("I have awoken Mr. Scalperman. I hope he had a good rest.")

    def start(self):
        global client
        client = Client(config.API_KEY, config.API_SECRET, testnet=False)
        client.API_URL = 'https://api2.binance.com/api'

        self.Klines = Klines()
        self.Wallet = Wallet()
        self.Trail = Trail()

        self.Klines.get_formatted_klines()

        self.Wallet.update_balance()

        self.Wallet.print()

        self.twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
        # start is required to initialise its internal loop
        self.twm.start()

        self.twm.start_kline_socket(callback=Klines.candle_listener, symbol=TRADE_SYMBOL)

        self.twm.start_symbol_book_ticker_socket(callback=Trail.book_ticker_listener, symbol=TRADE_SYMBOL)

    def stop(self):
        print("Mr. Scalperman has returned to his slumber. Do not disturb him.")
        self.twm.stop()

    def wallet(self):
        return self.Wallet

if __name__ == "__main__":
   binance_bot = Binance_Bot()
   binance_bot.start()