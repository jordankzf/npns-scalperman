from binance import Client, ThreadedWebsocketManager
from binance.helpers import round_step_size
from pandas import to_datetime, DataFrame
from ta.momentum import StochasticOscillator
from ta.volume import ForceIndexIndicator
import config

class Strategy:
    def __init__(
        self,
        profit_target : float = 0.003,
        initial_double_down_target : float = 0.001,
        double_down_target_ratio : float = 5.07659274961738,
        initial_entry_size : float = 54,
        order_size_ratio : float = 2.31776962504738,
        bullets : int = 5,
        base_precision : float = 0.00001,
        quote_precision : float = 0.0000001,
        commission : float = 0.0006,
        base_symbol : str = 'ETH',
        quote_symbol : str = 'USDT',
        bear_mode : bool = False
    ):
        self.profit_target = profit_target
        self.initial_double_down_target = initial_double_down_target
        self.double_down_target_ratio = double_down_target_ratio
        self.initial_entry_size = initial_entry_size
        self.order_size_ratio = order_size_ratio
        self.bullets = bullets
        self.base_precision = base_precision
        self.quote_precision = quote_precision
        self.commission = commission
        self.base_symbol = base_symbol
        self.quote_symbol = quote_symbol
        self.bear_mode = bear_mode

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

        force_index_indicator = ForceIndexIndicator(close=indicators_klines['Close'],
                                                    volume=indicators_klines['Volume'])

        indicators_klines['Stoch K'] = stoch_indicator.stoch()
        indicators_klines['Force Index'] = force_index_indicator.force_index()

        return indicators_klines

    def entry_signal(self, indicator_klines, bear_mode):
        current_stochK = indicator_klines.tail(1)['Stoch K'].values[0]
        current_FI = indicator_klines.tail(1)['Force Index'].values[0]

        if bear_mode:
            return current_stochK <= 8 and current_FI <= -800
        else:
            return current_stochK >= 90 and current_FI >= 150

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

    def cost_basis(self, commission, bear_mode):
        if bear_mode:
            average_price = self.quote_spent / self.base_balance
            return average_price / (1 - commission * 2)
        else:
            average_price = self.quote_balance / self.base_spent
            return average_price * (1 - commission * 2)
            
class Remisier:
    def __init__(self, strategy : Strategy, wallet : Wallet, client : Client, klines : Klines):
        self.strategy = strategy
        self.wallet = wallet
        self.client = client
        self.klines = klines

        self.last_entry_price : float
        self.open_positions : int = 0

    def open(self):
        quote_amount = self.order_size()

        rounded_amount = round_step_size(quote_amount, self.strategy.quote_precision)

        try:
            if self.strategy.bear_mode:
                order = self.client.order_market_buy(
                        symbol=self.strategy.trade_symbol,
                        quoteOrderQty=rounded_amount)

                cummulativeQuoteQty = float(order['cummulativeQuoteQty'])
                executedQty = float(order['executedQty'])

                self.wallet.quote_balance -= cummulativeQuoteQty
                self.wallet.quote_spent += cummulativeQuoteQty
                self.wallet.base_balance += executedQty
            else:
                order = self.client.order_market_sell(
                        symbol=self.strategy.trade_symbol,
                        quoteOrderQty=rounded_amount)

                cummulativeQuoteQty = float(order['cummulativeQuoteQty'])
                executedQty = float(order['executedQty'])

                self.wallet.base_balance -= executedQty
                self.wallet.base_spent += executedQty
                self.wallet.quote_balance += cummulativeQuoteQty
                
            print(f"Open Order Response {order}")
        except Exception as e:
                print(f"an exception occured - {e}")
            
        else:
            self.open_positions += 1
            real_price = cummulativeQuoteQty / executedQty
            self.last_entry_price = real_price

            self.wallet.balance_enquiry()

            print(
                f"Wallet after opening\n"
                f"TP close price is {self.take_profit()}\n"
                f"Will double down if price hits {self.double_down_target()}"
            )

    def close(self):
        try:
            if self.strategy.bear_mode:
                rounded_amount = round_step_size(self.wallet.base_balance, self.strategy.base_precision)

                order = self.client.order_market_sell(
                        symbol=self.strategy.trade_symbol,
                        quantity=rounded_amount)

                cummulativeQuoteQty = float(order['cummulativeQuoteQty'])
                executedQty = float(order['executedQty'])

                self.wallet.quote_balance += cummulativeQuoteQty
                real_price = cummulativeQuoteQty / executedQty

                this_profit = (real_price / self.wallet.cost_basis(self.strategy.commission, self.strategy.bear_mode) * self.wallet.quote_spent) - self.wallet.quote_spent

                self.wallet.base_balance = 0
                self.wallet.quote_spent = 0
                
            else:
                rounded_amount = round_step_size(self.wallet.quote_balance, self.strategy.base_precision)

                order = self.client.order_market_buy(
                        symbol=self.strategy.trade_symbol,
                        quoteOrderQty=rounded_amount)

                cummulativeQuoteQty = float(order['cummulativeQuoteQty'])
                executedQty = float(order['executedQty'])
                
                self.wallet.base_balance += executedQty
                real_price = cummulativeQuoteQty / executedQty

                this_profit = (1 - (real_price / self.wallet.cost_basis(self.strategy.commission, self.strategy.bear_mode)) * self.wallet.base_spent) - self.wallet.base_spent

                self.wallet.quote_balance = 0
                self.wallet.base_spent = 0

        except Exception as e:
            print(f"an exception occured - {e}")
        else:
            print(f"Sell Order Response {order}")

            self.wallet.profit += this_profit

            print(
                f"Profit! I bestow upon you: {this_profit}\n"
                f"So far, I have earned you {self.wallet.profit} this session."
            )

            self.open_positions = 0

            print(f"Wallet after selling")
            self.wallet.balance_enquiry()

    def order_size(self):
        if self.open_positions < 1:
            return self.strategy.initial_entry_size
        return self.strategy.initial_entry_size * self.strategy.order_size_ratio ** self.open_positions

    def double_down_target(self):
        percentage = self.strategy.initial_double_down_target * self.strategy.double_down_target_ratio ** (self.open_positions - 1)
        if self.strategy.bear_mode:
            return self.last_entry_price * (1 - percentage)
        else:
            return self.last_entry_price * (1 + percentage)

    def take_profit(self):
        if self.strategy.bear_mode:
            return self.wallet.cost_basis(self.strategy.commission, self.strategy.bear_mode) * (1 + self.strategy.profit_target)
        else:
            return self.wallet.cost_basis(self.strategy.commission, self.strategy.bear_mode) * (1 - self.strategy.profit_target)

    def kline_listener(self, tick):
        self.klines.update_klines(tick)

        if self.klines.entry_signal(self.klines.indicators(), self.strategy.bear_mode) and self.open_positions < 1:
            self.open()

    def bookticker_listener(self, tick):
        if self.open_positions > 0:
            best_ask = float(tick["a"])
            best_bid = float(tick["b"])

            if self.strategy.bear_mode:
                if best_bid > self.take_profit():
                    self.close()
                elif best_ask < self.double_down_target():
                    self.open()
            else:
                if best_bid < self.take_profit():
                    self.close()
                elif best_ask > self.double_down_target():
                    self.open()

class Main:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.twm = ThreadedWebsocketManager(api_key, api_secret)
        self.strategy = Strategy()
        self.klines = Klines()
        self.wallet = Wallet()
        self.remisier = Remisier(self.strategy, self.wallet, self.client, self.klines)
        
    def start(self):
        if self.strategy.bear_mode:
            self.wallet.quote_balance = float(self.client.get_asset_balance(asset=self.strategy.quote_symbol)['free'])
        else:
            self.wallet.base_balance = float(self.client.get_asset_balance(asset=self.strategy.base_symbol)['free'])
        
        self.klines.format_klines(self.client.get_historical_klines(self.strategy.trade_symbol, "1m", "1 hour ago UTC"))

        self.wallet.balance_enquiry()

        self.twm.start()

        self.twm.start_kline_socket(callback=self.remisier.kline_listener, symbol=self.strategy.trade_symbol)
        self.twm.start_symbol_book_ticker_socket(callback=self.remisier.bookticker_listener, symbol=self.strategy.trade_symbol)

        print("I have awoken Scalper-san. I hope she had a good rest.")

    def stop(self):
        print("Scalper-san has returned to her slumber. Do not disturb her.")
        self.twm.stop()

if __name__ == "__main__":
    main = Main(config.API_KEY, config.API_SECRET)
    main.start()
