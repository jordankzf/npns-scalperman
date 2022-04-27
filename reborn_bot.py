from math import floor
from binance import Client, ThreadedWebsocketManager
from pandas import to_datetime, DataFrame
from ta.momentum import StochasticOscillator
import config
import time

class Strategy:
    def __init__(
        self,
        stochK_threshold : int = 97,
        profit_target : float = 0.001,
        stop_loss : float = 0.01,
        base_precision : int = 4,
        quote_precision : int = 2,
        base_symbol : str = 'ETH',
        quote_symbol : str = 'BUSD',
        slippage : float = 0.05,
    ):
        self.stochK_threshold = stochK_threshold
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.base_precision = base_precision
        self.quote_precision = quote_precision
        self.base_symbol = base_symbol
        self.quote_symbol = quote_symbol
        self.slippage = slippage

        self.trade_symbol = base_symbol + quote_symbol

class Klines:
    def __init__(self):
        self.formatted_klines : DataFrame

    def format_klines(self, raw_klines):
        for row in raw_klines:
            del row[6:]
        formatted_klines = DataFrame(raw_klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        formatted_klines = formatted_klines.astype(float)
        formatted_klines.set_index('Time', inplace=True)
        formatted_klines.index = to_datetime(formatted_klines.index, unit='ms')

        self.formatted_klines = formatted_klines

    def update_klines(self, candle, cutoff=60):       
        candle['t'] = to_datetime(candle['t'], unit='ms')
        self.formatted_klines.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']),
                                            float(candle['c']), float(candle['v'])]

        self.formatted_klines = self.formatted_klines.tail(cutoff)

    def indicators(self):
        indicators_klines = self.formatted_klines.copy()

        stoch_indicator = StochasticOscillator(close=indicators_klines['Close'],
                                                high=indicators_klines['High'],
                                                low=indicators_klines['Low'],
                                                window=30)

        indicators_klines['Stoch K'] = stoch_indicator.stoch()
        return indicators_klines

class Wallet:
    def __init__(self):
        self.initial_base_balance : float = 0
        self.quote_balance : float = 0
        self.base_balance : float = 0
        self.base_profit : float = 0
        self.quote_profit : float = 0
        self.percentage_profit : float = 0.00
        self.trades_made : int = 0

    def balance_enquiry(self):
        print(
            f"Trades made: {self.trades_made}\n\n"
            f"Quote_balance: {self.quote_balance}\n"
            f"Base_balance: {self.base_balance}\n\n"
            f"Base_profit: {self.base_profit}¢\n"
            f"Quote_profit: ${self.quote_profit}\n"
            f"Percentage_profit: {self.percentage_profit}%\n"
        )

    def update_balance(self, new_balance, price):
        self.base_balance = new_balance
        # self.trades_made += 1

        # change = new_balance - self.base_balance

        # if change > 0:
        #     print("Profit!")
        # else:
        #     print("FUck!")

        # self.base_profit += change
        # self.quote_profit += self.base_profit * price
        # self.percentage_profit =  new_balance / self.initial_base_balance * 100
        # self.base_balance = new_balance

        # self.balance_enquiry()
class Remisier:
    def __init__(self, strategy : Strategy, wallet : Wallet, client : Client, klines : Klines):
        self.strategy = strategy
        self.wallet = wallet
        self.client = client
        self.klines = klines

        self.best_ask : str
        self.best_bid : str

        self.stop_loss : float
        self.buy_at_rounded : float
        self.quantity_rounded : float

        self.try_to_sell : bool = False
        self.try_to_buy : bool = False

        self.sell_order_time : float

        self.order_ID : str
    
    def round_decimals_down(self, number:float, decimals:int=2):
        """
        Returns a value rounded down to a specific number of decimal places.
        """

        factor = 10 ** decimals
        return floor(number * factor) / factor

    def open(self):
        quantity_rounded = self.wallet.base_balance
        quantity_rounded = self.round_decimals_down(quantity_rounded, self.strategy.base_precision)

        sell_at = float(self.best_ask) + self.strategy.slippage
        sell_at = self.round_decimals_down(sell_at, self.strategy.quote_precision)

        sell = self.client.order_limit_sell(symbol=self.strategy.trade_symbol, quantity=quantity_rounded, price=sell_at)

        self.sell_order_time = time.time()

        print(f"sell {sell}")

        buy_at = sell_at * (1 - self.strategy.profit_target)
        self.stop_loss = sell_at * (1 + self.strategy.stop_loss)
        self.buy_at_rounded = self.round_decimals_down(buy_at, self.strategy.quote_precision)
        quantity = self.wallet.base_balance * (1 + self.strategy.profit_target)
        self.quantity_rounded = self.round_decimals_down(quantity, self.strategy.base_precision)

        self.try_to_sell = True

    def cancel(self):
        cancel = self.client.cancel_order(symbol=self.strategy.trade_symbol, orderId=self.order_ID)

        print(f"cancel order {cancel}")

    def close(self):
        self.cancel()

        quantity_rounded = self.wallet.base_balance * (1 - self.strategy.stop_loss)
        quantity_rounded = self.round_decimals_down(quantity_rounded, self.strategy.base_precision)

        buy_at = float(self.best_bid) - self.strategy.slippage
        self.buy_at_rounded = self.round_decimals_down(buy_at, self.strategy.quote_precision)

        buy = self.client.order_limit_buy(symbol=self.strategy.trade_symbol, quantity=quantity_rounded, price=self.buy_at_rounded)

        print(f"buy back at loss {buy}")
        
    def kline_listener(self, tick):
        candle = tick['k']
        self.klines.update_klines(candle)

        current_stochK = self.klines.indicators().tail(1)['Stoch K'].values[0]

        # is_kline_complete = candle['x']
        # kline_close_price = float(candle['c'])

        # SHORT + CANDLE CLOSED + CLOSE PRICE ABOVE STOP LOSS
        if self.try_to_buy and candle['x'] and float(candle['c']) >= self.stop_loss:
            self.close()
        # TRY TO SHORT + BUT MORE THAN 2 MINS, ORDER HAS NOT FILLED = GIVE UP
        elif self.try_to_sell and time.time() - self.sell_order_time >= 120:
            self.cancel()
            self.try_to_sell = False
        # No open orders
        elif current_stochK >= self.strategy.stochK_threshold:
            self.open()
        else:
            print(f"Stoch K is {current_stochK}")
        

    def bookticker_listener(self, tick):
        self.best_ask = tick["a"]
        self.best_bid = tick["b"]

    def user_listener(self, tick):
        if self.try_to_sell or self.try_to_buy and tick['e'] == 'executionReport' and tick['X'] == 'FILLED' and tick['s'] == self.strategy.trade_symbol:
            side = tick['S']
            if side == "SELL": # If sold successfully (open)
                buy = self.client.order_limit_buy(symbol="ETHBUSD", quantity=self.quantity_rounded, price=self.buy_at_rounded)
                self.order_ID = buy['orderId']
                print(f'buy {buy}')
                # self.wallet.balance_enquiry()
                self.try_to_buy = True
                self.try_to_sell = False
            elif side == "BUY": # If bought successfully (close)
                # Update balance
                new_base_balance = float(self.client.get_asset_balance(asset=self.strategy.base_symbol)['free'])
                self.wallet.update_balance(new_base_balance, self.buy_at_rounded)
                self.try_to_buy = False

class Main:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.twm = ThreadedWebsocketManager(api_key, api_secret)
        self.strategy = Strategy()
        self.klines = Klines()
        self.wallet = Wallet()
        self.remisier = Remisier(self.strategy, self.wallet, self.client, self.klines)

    def start(self):
        self.wallet.base_balance = float(self.client.get_asset_balance(asset=self.strategy.base_symbol)['free'])
        self.wallet.initial_base_balance = self.wallet.base_balance

        self.klines.format_klines(self.client.get_historical_klines(self.strategy.trade_symbol, "1m", "1 hour ago UTC"))

        self.wallet.balance_enquiry()

        print("I have awoken Scalper-san. I hope she had a good rest.")
        
        self.twm.start()

        self.twm.start_symbol_book_ticker_socket(callback=self.remisier.bookticker_listener, symbol=self.strategy.trade_symbol) # Get best price
        self.twm.start_kline_socket(callback=self.remisier.kline_listener, symbol=self.strategy.trade_symbol) # Calculate indicators
        self.twm.start_user_socket(callback=self.remisier.user_listener) # Get purchase updates

        self.twm.join()

    def stop(self):
        print("Scalper-san has returned to her slumber. Do not disturb her.")
        self.twm.stop()

if __name__ == "__main__":
    main = Main(config.API_KEY, config.API_SECRET)

    try:
        main.start()
    except Exception as e:
        print(f"an exception occured - {e}")