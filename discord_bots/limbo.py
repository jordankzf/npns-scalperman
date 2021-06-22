from binance import Client, ThreadedWebsocketManager
import config as config
import threading
from requests import post

# Constants
TRADE_SYMBOL = 'BTCUSDT'

client = Client(config.API_KEY, config.API_SECRET, testnet=False)
client.API_URL = 'https://api2.binance.com/api'

def discord(message):
    threading.Thread(target=post, args=('https://discord.com/api/webhooks/855017513758228480/NlT411d0zOWn8ucgbKtlombbM1v-52fVoPB3ndQIOj67Em0Au7264AfSfWAnMDGU7NPa', ({"content": message}),)).start()

class Binance_Bot:
    def tick_listener(self, tickers):
        for ticker in tickers:
            pair = ticker['s']

            if pair == 'BTCUSDT':
                current_price = ticker['c']
                low = ticker['l']

                print(ticker)

                if current_price <= low:
                    discord(f"{pair} just hit today's lowest of {low}")

    def __init__ (self):
        print("I have awoken Mr. Scalperman. I hope he had a good rest.")

    def start(self):

        self.twm = ThreadedWebsocketManager(config.API_KEY, config.API_SECRET)
        # start is required to initialise its internal loop
        self.twm.start()

        self.twm.start_miniticker_socket(callback=self.tick_listener)

if __name__ == "__main__":
   binance_bot = Binance_Bot()
   binance_bot.start()