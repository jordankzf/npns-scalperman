# import threading
from binance import Client, ThreadedWebsocketManager
# from binance.enums import *
from binance.helpers import round_step_size
from numpy import array
from pandas import to_datetime, DataFrame
from ta.momentum import StochasticOscillator
from ta.volume import ForceIndexIndicator

import config as config

# from signal import signal, SIGINT
# from sys import exit
# from requests import post

# Constants
TRADE_SYMBOL = 'THETAUSDT'
FIAT_COIN = 'USDT'
BASE_PRECISION = 0.001
QUOTE_PRECISION = 0.000001
COMMISSION = 0.0006


# if config.WEBHOOK:
#     def print(message):
#         threading.Thread(target=post, args=(config.WEBHOOK, ({"content": message}),)).start()

class Strategy(object):
    take_profit = 1.003
    buy_slippage = 0.002
    sell_slippage = 0.002
    initial_double_down_target_percent = 0.001
    R_ddt = 1.7
    initial_purchase_size = 10
    R_ips = 1.808
    total_bullets = 10

    # def calc_R_ddt(self):
    #     total = (Strategy.initial_purchase_size * (1 - Strategy.R_ddt ** Strategy.total_bullets)) / (1 - Strategy.R_ddt)


class Klines(object):
    base_df = None
    with_indicators_df = None

    def get_formatted_klines(self):
        klines = client.get_historical_klines(TRADE_SYMBOL, "1m", "2 hours ago UTC")
        np_klines = array(klines)
        klines = np_klines[:, :6]
        Klines.base_df = DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        Klines.base_df = Klines.base_df.astype(float)
        Klines.base_df.set_index('Time', inplace=True)
        Klines.base_df.index = to_datetime(Klines.base_df.index, unit='ms')

        # Save/load processed klines data as CSV file (for debugging purposes)
        # Klines.base_df.to_csv('base_bars3.csv')
        # Klines.base_df = pd.read_csv('base_bars3.csv', index_col=0)

    def candle_listener(self, candle_tick):
        candle = candle_tick['k']

        candle['t'] = to_datetime(candle['t'], unit='ms')

        Klines.base_df.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']),
                                           float(candle['c']), float(candle['v'])]

        # Trim to latest 120 rows
        Klines.base_df = Klines.base_df.tail(120)

        # print (Klines.base_df)
        # Klines.base_df = Klines.base_df.append(new_row, ignore_index=False)

        # Clone dataframe
        Klines.with_indicators_df = Klines.base_df.copy()

        # Calculate TA indicators
        stoch_indicator = StochasticOscillator(close=Klines.with_indicators_df['Close'],
                                               high=Klines.with_indicators_df['High'],
                                               low=Klines.with_indicators_df['Low'])
        force_index_indicator = ForceIndexIndicator(close=Klines.with_indicators_df['Close'],
                                                    volume=Klines.with_indicators_df['Volume'])
        # vwap_indicator = VolumeWeightedAveragePrice(close=Klines.with_indicators_df['Close'], high=Klines.with_indicators_df['High'], low=Klines.with_indicators_df['Low'], volume=Klines.with_indicators_df['Volume'])

        # Add TA indicators as columns to cloned dataframe
        Klines.with_indicators_df['Stoch K'] = stoch_indicator.stoch()
        Klines.with_indicators_df['Force Index'] = force_index_indicator.force_index()
        # Klines.with_indicators_df['VWAP'] = vwap_indicator.volume_weighted_average_price()

        # Grab latest tick indicator values
        current_stochK = Klines.with_indicators_df.tail(1)['Stoch K'].values[0]
        current_FI = Klines.with_indicators_df.tail(1)['Force Index'].values[0]
        # current_VWAP = Klines.with_indicators_df.tail(1)['VWAP'].values[0]
        # currentClose = Klines.with_indicators_df.tail(1)['Close'].values[0]

        # Grab average indicator value
        # average_FI = Klines.with_indicators_df.tail(60)['Force Index'].mean()

        # print("StochK is {:.2f}".format(current_stochK))
        # print("Force Index is {:.2f}".format(current_FI))
        # print("VWAP is {:.2f}".format(current_VWAP))
        # print("Current Price is {:.2f}".format(currentClose))

        # if current_FI <= -500 and current_stochK <= 20 and not Trail.have_open_position:
        if current_stochK <= 8 and current_FI <= -50 and not Trail.have_open_position and not Trail.hunting:
            # Strategy.initial_purchase_size = current_FI / -50 * 10
            # Strategy.take_profit = 1 + (current_FI / -50 * 0.003)
            # Strategy.double_down_target = max((1 + (current_FI / -25 * 0.994)), 0.994)
            print("I see a dip. Hold my beer, I'm going in!")
            Trail.buy(self)
            # Trail.order_type = "b"
            # Trail.hunting = True


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
    # current_purchase_size = None
    # current_target_double_down_absolute = None
    buy_orders_count = 0
    sell_orders_count = 0
    stop_slippage_absolute = None

    def buy(self):
        quote_amount = Trail.calc_purchase_size(self)

        if quote_amount <= Wallet.quote_balance:
            rounded_amount = round_step_size(quote_amount, QUOTE_PRECISION)
            try:
                order = client.order_market_buy(
                    symbol=TRADE_SYMBOL,
                    quoteOrderQty=rounded_amount)
            except Exception as e:
                print(f"an exception occured - {e}")
            else:
                print(f"Buy Order Response {order}")

                # Wallet.quote_balance -= float(order['cummulativeQuoteQty'])
                # Wallet.quote_spent += float(order['cummulativeQuoteQty'])
                # Wallet.base_balance += float(order['executedQty'])
                cummulativeQuoteQty = float(order['cummulativeQuoteQty'])
                executedQty = float(order['executedQty'])
                Wallet.quote_balance -= cummulativeQuoteQty
                Wallet.quote_spent += cummulativeQuoteQty
                Wallet.base_balance += executedQty
                Trail.open_positions_count += 1
                real_cost = cummulativeQuoteQty / executedQty

                Trail.buy_orders_count += 1

                Trail.last_buy_price = real_cost
                Trail.hunting = False
                Trail.have_open_position = True
                Trail.trailing_order_first_run = True

                Wallet.print(self)

                print(
                    f"Wallet after buying\n"
                    f"Target sell price is {Wallet.calc_cost_basis(self) * Strategy.take_profit}\n"
                    f"Will double down is price drops to {Trail.calc_double_down_target_absolute(self)}"
                )
        else:
            print("Not enough quote asset to buy.")

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

            # Wallet.quote_balance += float(order['cummulativeQuoteQty'])
            # real_cost = float(order['cummulativeQuoteQty']) / float(order['executedQty'])
            cummulativeQuoteQty = float(order['cummulativeQuoteQty'])
            executedQty = float(order['executedQty'])
            Wallet.quote_balance += cummulativeQuoteQty
            real_cost = cummulativeQuoteQty / executedQty

            this_profit = (real_cost / Wallet.calc_cost_basis(self) * Wallet.quote_spent) - Wallet.quote_spent
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

            print(f"Wallet after selling")
            Wallet.print(self)

    def calc_purchase_size(self):
        if not Trail.have_open_position:
            return Strategy.initial_purchase_size
        return Strategy.initial_purchase_size * Strategy.R_ips ** Trail.open_positions_count

    def calc_double_down_target_absolute(self):
        percentage = Strategy.initial_double_down_target_percent * Strategy.R_ddt ** (Trail.open_positions_count - 1)
        return Trail.last_buy_price * (1 - percentage)

    def book_ticker_listener(self, book_tick):
        best_ask = float(book_tick["a"])
        best_bid = float(book_tick["b"])

        if Trail.have_open_position:
            # If I'm at profit
            if best_bid > Wallet.calc_cost_basis(self) * Strategy.take_profit:
                Trail.sell(self)
                # Trail.order_type = "s"
                # Trail.hunting = True
            # If price dropped further
            if best_ask < Trail.calc_double_down_target_absolute(self):
                Trail.buy(self)
                # Trail.order_type = "b"
                # Trail.hunting = True

        # if Trail.hunting:
        #     if Trail.order_type == "b":
        #         if Trail.trailing_order_first_run:
        #             Trail.previous_price = best_ask
        #             Trail.stop_slippage_absolute = best_ask * Strategy.buy_slippage
        #             Trail.stop_price = Trail.previous_price + Trail.stop_slippage_absolute
        #             print(
        #                 f"Initial buy price is {Trail.previous_price}\n"
        #                 f"Initial Trailing Stop Buy Price set to {Trail.stop_price}"
        #             )
        #             Trail.trailing_order_first_run = False
        #         else:
        #             Trail.current_price = best_ask
        #             # if Trail.current_price == Trail.previous_price:
        #             #     print("The price has stayed the same")
        #             if Trail.current_price < Trail.previous_price:
        #                 # print("Current price is " + str(Trail.current_price))
        #                 Trail.new_stop_price = Trail.current_price + Trail.stop_slippage_absolute

        #                 if Trail.new_stop_price < Trail.stop_price:
        #                     Trail.stop_price = Trail.new_stop_price
        #                     print(f"Trailing Stop Buy Price updated to {Trail.stop_price}")

        #             if Trail.current_price >= Trail.stop_price:
        #                 print(f"Trying to buy at {Trail.current_price}")
        #                 Trail.buy(self)

        #             Trail.previous_price = Trail.current_price

        #     if Trail.order_type == "s":
        #         Trail.sell(self)
        # if Trail.trailing_order_first_run:
        #     Trail.previous_price = best_bid
        #     Trail.stop_price = Trail.previous_price - Trail.previous_price * Strategy.sell_slippage
        #     print(
        #         f"Initial sell price is {Trail.previous_price}\n"
        #         f"Initial Trailing Stop Sell Price set to {Trail.stop_price}"
        #     )
        #     Trail.trailing_order_first_run = False
        # else:
        #     Trail.current_price = best_bid
        #     # if Trail.current_price == Trail.previous_price:
        #     #     print("The price has stayed the same")
        #     if Trail.current_price > Trail.previous_price:
        #         # print("Current price is " + str(Trail.current_price))
        #         Trail.new_stop_price = Trail.current_price - Trail.current_price * Strategy.sell_slippage

        #         if Trail.new_stop_price > Trail.stop_price:
        #             Trail.stop_price = Trail.new_stop_price
        #             print(f"Trailing Stop Sell updated to {Trail.stop_price}")

        #     if Trail.current_price <= Trail.stop_price and Trail.current_price:
        #         print(f"Trying to sell at {Trail.current_price}")
        #         Trail.sell(self)

        #     Trail.previous_price = Trail.current_price


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


client = Client(config.API_KEY, config.API_SECRET, testnet=False)
client.API_URL = 'https://api2.binance.com/api'


class Binance_Bot:
    def __init__(self):
        print("I have awoken Mr. Scalperman. I hope he had a good rest.")

    def start(self):
        self.Klines = Klines()
        self.Wallet = Wallet()
        self.Trail = Trail()
        self.Strategy = Strategy()

        self.Klines.get_formatted_klines()

        self.Wallet.update_balance()

        self.Wallet.print()

        self.twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
        # start is required to initialise its internal loop
        self.twm.start()

        self.twm.start_kline_socket(callback=self.Klines.candle_listener, symbol=TRADE_SYMBOL)

        self.twm.start_symbol_book_ticker_socket(callback=self.Trail.book_ticker_listener, symbol=TRADE_SYMBOL)

    def stop(self):
        print("Mr. Scalperman has returned to his slumber. Do not disturb him.")
        self.twm.stop()

    def wallet(self):
        return self.Wallet


if __name__ == "__main__":
    binance_bot = Binance_Bot()
    binance_bot.start()
