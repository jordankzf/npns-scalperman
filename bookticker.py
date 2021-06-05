import time
import config

from binance import ThreadedWebsocketManager

api_key = config.API_KEY
api_secret = config.API_SECRET

def main():

    symbol = 'BTCUSDT'

    twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)
    # start is required to initialise its internal loop
    twm.start()

    def handle_socket_message(msg):
        # print(f"message type: {msg['e']}")
        print(msg)

    # twm.start_kline_socket(callback=handle_socket_message, symbol=symbol)

    # multiple sockets can be started
    # twm.start_depth_socket(callback=handle_socket_message, symbol=symbol)

    twm.start_symbol_book_ticker_socket(callback=handle_socket_message, symbol=symbol)

    # # or a multiplex socket can be started like this
    # # see Binance docs for stream names
    # streams = ['btcusdt@bookTicker']
    # twm.start_multiplex_socket(callback=handle_socket_message, streams=streams)

    twm.join()


if __name__ == "__main__":
    main()