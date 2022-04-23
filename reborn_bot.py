import decimal
from binance import Client, ThreadedWebsocketManager
from pandas import to_datetime, DataFrame
from ta.momentum import StochasticOscillator
import config

decimal.getcontext().rounding = decimal.ROUND_DOWN

class Strategy:
    def __init__(
        self,
        profit_target : decimal.Decimal = 0.00025,
        base_precision : decimal.Decimal = 0.001,
        quote_precision : decimal.Decimal = 0.00001,
        base_symbol : str = 'ETH',
        quote_symbol : str = 'BUSD',
    ):
        self.profit_target = profit_target
        self.base_precision = base_precision
        self.quote_precision = quote_precision
        self.base_symbol = base_symbol
        self.quote_symbol = quote_symbol

        self.trade_symbol = base_symbol + quote_symbol

class Klines:
    def __init__(self):
        self.formatted_klines : DataFrame
        self.above24hr : bool = False
     
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
    
    def symbolticker_listener(self, tick):
        self.above24hr = decimal.Decimal(tick["a"]) > decimal.Decimal(tick["w"])

    def entry_signal(self, indicator_klines):
        current_stochK = indicator_klines.tail(1)['Stoch K'].values[0]
        kline_length = indicator_klines.tail(1)['High'].values[0] / indicator_klines.tail(1)['Low'].values[0]

        print(f"Stoch {current_stochK} Above24hr {self.above24hr} Longboi {kline_length}")
        return current_stochK >= 98 and self.above24hr and kline_length >= 1.0005

class Wallet:
    def __init__(self):
        self.quote_balance : decimal.Decimal = 0
        self.base_balance : decimal.Decimal = 0
        self.quote_spent : decimal.Decimal = 0
        self.base_spent : decimal.Decimal = 0
        self.profit : decimal.Decimal = 0

    def balance_enquiry(self):
        print(
            f"Quote_balance: {self.quote_balance}\n"
            f"Quote_spent: {self.quote_spent}\n"
            f"Base_balance: {self.base_balance}\n"
            f"Base_spent: {self.base_spent}"
        )
            
class Remisier:
    def __init__(self, strategy : Strategy, wallet : Wallet, client : Client, klines : Klines):
        self.strategy = strategy
        self.wallet = wallet
        self.client = client
        self.klines = klines

        self.last_entry_price : decimal.Decimal
        self.try_to_sell : bool = False
        self.try_to_buy : bool = False

        self.best_ask : decimal.Decimal

        self.buy_at_rounded : decimal.Decimal
        self.quantityRounded : decimal.Decimal

    def open(self):
        quote_amount = self.wallet.base_balance

        # rounded_amount = round_step_size(quote_amount, self.strategy.quote_precision)

        quantityRounded = decimal.Decimal(quote_amount)
        quantityRounded = round(quantityRounded, 4)

        sell_at = self.best_ask + 0.1
        sell_at = round(sell_at, 2)

        sell = self.client.order_limit_sell(symbol=self.strategy.trade_symbol, quantity=quantityRounded, price=sell_at)

        print(f"sell {sell}")

        buy_at = sell_at * (1 - self.strategy.profit_target)
        self.buy_at_rounded = round(buy_at, 2)
        quantity = quantityRounded * decimal.Decimal(1 + self.strategy.profit_target)
        self.quantityRounded = round(quantity, 4)

        self.try_to_sell = True

    def kline_listener(self, tick):
        self.klines.update_klines(tick)

        if not self.try_to_sell and not self.try_to_buy and self.klines.entry_signal(self.klines.indicators()):
            self.open()

    def bookticker_listener(self, tick):
        self.best_ask = decimal.Decimal(tick["a"])

    def user_listener(self, tick):
        if self.try_to_sell or self.try_to_buy:
            res = tick
            if res['e'] == 'executionReport' and res['X'] == 'FILLED':
                buy = self.client.order_limit_buy(symbol="ETHBUSD", quantity=self.quantityRounded, price=self.buy_at_rounded)
                print(f'buy {buy}')
                if res['S'] == "BUY":
                    self.try_to_buy = False
                elif res['S'] == "SELL":
                    self.try_to_buy = True
                    self.try_to_sell = False
        return

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
        
        self.klines.format_klines(self.client.get_historical_klines(self.strategy.trade_symbol, "1m", "1 hour ago UTC"))

        self.wallet.balance_enquiry()

        self.twm.start()

        self.twm.start_symbol_book_ticker_socket(callback=self.remisier.bookticker_listener, symbol=self.strategy.trade_symbol)
        self.twm.start_symbol_ticker_socket(callback=self.klines.symbolticker_listener, symbol=self.strategy.trade_symbol) # Get 24hr average
        self.twm.start_kline_socket(callback=self.remisier.kline_listener, symbol=self.strategy.trade_symbol)
        self.twm.start_user_socket(callback=self.remisier.user_listener) # Get purchase updates

        self.twm.join()

        print("I have awoken Scalper-san. I hope she had a good rest.")

    def stop(self):
        print("Scalper-san has returned to her slumber. Do not disturb her.")
        self.twm.stop()

if __name__ == "__main__":
    main = Main("eUXdZ64iVV2b2Rwb53r675CXEb4DCcpCuymnjkj3CQRCsSEdcFG4J2xeJusxJsrW", "oXh6fDA0ricTeplgJ4HwIhD6767QvF1lHPyd8FMhaaqonUUD2mPTGpaNzRyanKba")

    main.start()

