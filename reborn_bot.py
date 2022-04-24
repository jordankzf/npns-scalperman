import decimal
from binance import Client, ThreadedWebsocketManager
from pandas import to_datetime, DataFrame
from ta.momentum import StochasticOscillator
import config

decimal.getcontext().rounding = decimal.ROUND_DOWN

class Strategy:
    def __init__(
        self,
        stochK_threshold : int = 98,
        kline_length : decimal.Decimal = 1.001,
        profit_target : decimal.Decimal = 0.00025,
        base_precision : int = 4,
        quote_precision : int = 2,
        base_symbol : str = 'ETH',
        quote_symbol : str = 'BUSD',
    ):
        self.stochK_threshold = stochK_threshold
        self.kline_length = kline_length
        self.profit_target = profit_target
        self.base_precision = base_precision
        self.quote_precision = quote_precision
        self.base_symbol = base_symbol
        self.quote_symbol = quote_symbol

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

    def update_klines(self, tick, cutoff=60):
        candle = tick['k']
        
        candle['t'] = to_datetime(candle['t'], unit='ms')
        self.formatted_klines.loc[candle['t']] = [float(candle['o']), float(candle['h']), float(candle['l']),
                                            float(candle['c']), float(candle['v'])]

        self.formatted_klines = self.formatted_klines.tail(cutoff)

    def indicators(self):
        indicators_klines = self.formatted_klines.copy()

        stoch_indicator = StochasticOscillator(close=indicators_klines['Close'],
                                                high=indicators_klines['High'],
                                                low=indicators_klines['Low'])

        indicators_klines['Stoch K'] = stoch_indicator.stoch()
        return indicators_klines

class Wallet:
    def __init__(self):
        self.initial_base_balance : decimal.Decimal = 0
        self.quote_balance : decimal.Decimal = 0
        self.base_balance : decimal.Decimal = 0
        self.base_profit : decimal.Decimal = 0
        self.quote_profit : decimal.Decimal = 0
        self.percentage_profit : decimal.Decimal = 0.00
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

    def calculate_profit(self, profit_target, best_ask):
        self.trades_made += 1
        self.base_profit = self.base_balance * profit_target
        self.quote_profit = self.base_profit * best_ask
        self.percentage_profit = self.base_profit / self.initial_base_balance * 100
        self.balance_enquiry()

class Remisier:
    def __init__(self, strategy : Strategy, wallet : Wallet, client : Client, klines : Klines):
        self.strategy = strategy
        self.wallet = wallet
        self.client = client
        self.klines = klines

        self.best_ask : str
        self.buy_at_rounded : decimal.Decimal
        self.quantity_rounded : decimal.Decimal

        self.try_to_sell : bool = False
        self.try_to_buy : bool = False
        self.above24hr : bool = False

    def open(self):
        quantity_rounded = self.wallet.base_balance
        quantity_rounded = round(quantity_rounded, self.strategy.base_precision)

        sell_at = decimal.Decimal(self.best_ask) + decimal.Decimal(0.1)
        sell_at = round(sell_at, 2)

        sell = self.client.order_limit_sell(symbol=self.strategy.trade_symbol, quantity=quantity_rounded, price=sell_at)

        print(f"sell {sell}")

        buy_at = sell_at * (1 - self.strategy.profit_target)
        self.buy_at_rounded = round(buy_at, self.strategy.quote_precision)
        quantity = quantity_rounded * decimal.Decimal(1 + self.strategy.profit_target)
        self.quantity_rounded = round(quantity, self.strategy.base_precision)

        self.try_to_sell = True

    def scary_numbers(self):
        # print(f"price is {self.best_ask}")
        split_price = str(self.best_ask).split(".")[0]
        ones = split_price[-1]
        tens = split_price[-2]
        hundreds = split_price[-3]

        return ones in "129" or tens in "19"
        # or hundreds in "19"
        

    def kline_listener(self, tick):
        self.klines.update_klines(tick)

        current_stochK = self.klines.indicators().tail(1)['Stoch K'].values[0]
        kline_length = self.klines.indicators().tail(1)['High'].values[0] / self.klines.indicators().tail(1)['Low'].values[0]

        if not self.try_to_sell and not self.try_to_buy and self.above24hr and current_stochK >= self.strategy.stochK_threshold and kline_length >= self.strategy.kline_length and not self.scary_numbers():
            self.open()
        else:
            print(f"StochK is {round(current_stochK, 2)}, Above24hr is {self.above24hr}, Kline Length is {round((kline_length - 1) * 100, 3)}%, Number is scary {self.scary_numbers()}")

    def bookticker_listener(self, tick):
        self.best_ask = tick["a"]

    def user_listener(self, tick):
        if self.try_to_sell or self.try_to_buy:
            if tick['e'] == 'executionReport' and tick['X'] == 'FILLED' and tick['s'] == self.strategy.trade_symbol:
                buy = self.client.order_limit_buy(symbol="ETHBUSD", quantity=self.quantity_rounded, price=self.buy_at_rounded)
                print(f'buy {buy}')
                side = tick['S']
                if side == "BUY":
                    self.wallet.calculate_profit(self.strategy.profit_target, decimal.Decimal(self.best_ask))
                    self.try_to_buy = False
                elif side == "SELL":
                    print(self.wallet.balance_enquiry)
                    self.try_to_buy = True
                    self.try_to_sell = False

    def symbolticker_listener(self, tick):
        self.above24hr = decimal.Decimal(tick["a"]) > decimal.Decimal(tick["w"])

class Main:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.twm = ThreadedWebsocketManager(api_key, api_secret)
        self.strategy = Strategy()
        self.klines = Klines()
        self.wallet = Wallet()
        self.remisier = Remisier(self.strategy, self.wallet, self.client, self.klines)

    def start(self):
        self.wallet.base_balance = decimal.Decimal(self.client.get_asset_balance(asset=self.strategy.base_symbol)['free'])
        self.wallet.initial_base_balance = self.wallet.base_balance

        self.klines.format_klines(self.client.get_historical_klines(self.strategy.trade_symbol, "1m", "1 hour ago UTC"))

        self.wallet.balance_enquiry()

        print("I have awoken Scalper-san. I hope she had a good rest.")

        self.twm.start()

        self.twm.start_symbol_book_ticker_socket(callback=self.remisier.bookticker_listener, symbol=self.strategy.trade_symbol) # Get best price
        self.twm.start_symbol_ticker_socket(callback=self.remisier.symbolticker_listener, symbol=self.strategy.trade_symbol) # Get 24hr average
        self.twm.start_kline_socket(callback=self.remisier.kline_listener, symbol=self.strategy.trade_symbol) # Calculate indicators
        self.twm.start_user_socket(callback=self.remisier.user_listener) # Get purchase updates

        self.twm.join()

    def stop(self):
        print("Scalper-san has returned to her slumber. Do not disturb her.")
        self.twm.stop()

if __name__ == "__main__":
    main = Main(config.API_KEY, config.API_SECRET)

    main.start()