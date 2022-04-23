import decimal
from xmlrpc.client import Boolean
from binance import Client, ThreadedWebsocketManager
from pandas import to_datetime, DataFrame
from ta.momentum import StochasticOscillator
import config

decimal.getcontext().rounding = decimal.ROUND_DOWN

class Strategy:
    def __init__(
        self,
        profit_target : float = 0.00025,
        base_precision : float = 0.001,
        quote_precision : float = 0.00001,
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
        self.above24hr : Boolean = False
     
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
        self.above24hr = float(tick["a"]) > float(tick["w"])

    def entry_signal(self, indicator_klines):
        current_stochK = indicator_klines.tail(1)['Stoch K'].values[0]
        longboi = indicator_klines.tail(1)['High'].values[0] / indicator_klines.tail(1)['Low'].values[0] 

        print(f"Stoch {current_stochK} Above24hr {self.above24hr} Longboi {longboi}")
        return current_stochK >= 98 and self.above24hr and longboi >= 1.001

class Wallet:
    def __init__(self):
        self.quote_balance : float = 0
        self.base_balance : float = 0
        self.quote_spent : float = 0
        self.base_spent : float = 0
        self.profit : float = 0

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

        self.last_entry_price : float
        self.try_to_sell : Boolean = False
        self.try_to_buy : Boolean = False

        self.best_ask : float

        self.buy_at_rounded : float
        self.quantityRounded : float

    def open(self):
        quote_amount = self.wallet.base_balance

        # rounded_amount = round_step_size(quote_amount, self.strategy.quote_precision)

        quantityRounded = decimal.Decimal(quote_amount)
        quantityRounded = round(quantityRounded, 4)

        take_profit = 0.00025

        sell_at = self.best_ask + 0.1
        sell_at = round(sell_at, 2)

        sell = self.client.order_limit_sell(symbol=self.strategy.trade_symbol, quantity=quantityRounded, price=sell_at)

        print(f"sell {sell}")

        buy_at = sell_at * (1 - take_profit)
        self.buy_at_rounded = round(buy_at, 2)
        quantity = quantityRounded * decimal.Decimal(1 + take_profit)
        self.quantityRounded = round(quantity, 4)

        self.try_to_sell = True

    def kline_listener(self, tick):
        self.klines.update_klines(tick)

        if self.klines.entry_signal(self.klines.indicators()) and not self.try_to_buy and not self.try_to_sell:
            self.open()

    def bookticker_listener(self, tick):
        self.best_ask = float(tick["a"])

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
        self.wallet.base_balance = float(self.client.get_asset_balance(asset=self.strategy.base_symbol)['free'])
        
        self.klines.format_klines(self.client.get_historical_klines(self.strategy.trade_symbol, "1m", "1 hour ago UTC"))

        self.wallet.balance_enquiry()

        self.twm.start()

        self.twm.start_symbol_book_ticker_socket(callback=self.remisier.bookticker_listener, symbol=self.strategy.trade_symbol)
        self.twm.start_symbol_ticker_socket(callback=self.klines.symbolticker_listener, symbol=self.strategy.trade_symbol) # Get 24hr average
        self.twm.start_kline_socket(callback=self.remisier.kline_listener, symbol=self.strategy.trade_symbol)
        self.twm.start_user_socket(callback=self.remisier.user_listener) # Get purchase updates

        print("I have awoken Scalper-san. I hope she had a good rest.")

    def stop(self):
        print("Scalper-san has returned to her slumber. Do not disturb her.")
        self.twm.stop()

if __name__ == "__main__":
    main = Main("eUXdZ64iVV2b2Rwb53r675CXEb4DCcpCuymnjkj3CQRCsSEdcFG4J2xeJusxJsrW", "oXh6fDA0ricTeplgJ4HwIhD6767QvF1lHPyd8FMhaaqonUUD2mPTGpaNzRyanKba")

    main.start()

