import time
import config

from binance import ThreadedWebsocketManager

api_key = config.API_KEY
api_secret = config.API_SECRET

previousPrice = 99999.0
currentPrice = 99999.0
stopPrice = 99999.0
newStopPrice = 99999.0
firstRun = True
positionOpened = False

def main():

    TRADE_SYMBOL = 'BTCUSDT'

    twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)
    # start is required to initialise its internal loop
    twm.start()   

    def handle_socket_message(msg):
        global firstRun, previousPrice, stopPrice, positionOpened, newStopPrice
        if firstRun:
            previousPrice = float(msg["a"])
            print("Initial price is " + str(previousPrice))
            stopPrice = previousPrice / 0.999
            print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
            firstRun = False
        else:
            if (not positionOpened):
                currentPrice = float(msg["a"])
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice < previousPrice:
                    # print("Current price is " + str(currentPrice))

                    newStopPrice = currentPrice / 0.999
                
                    if newStopPrice < stopPrice:
                        stopPrice = newStopPrice
                        print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                
                if currentPrice >= stopPrice:
                    print("Bought at " + str(currentPrice))
                    positionOpened = True
                    twm.stop()

                previousPrice = currentPrice
        # print(f"message type: {msg['e']}")
        # print(msg)

    # twm.start_kline_socket(callback=handle_socket_message, TRADE_SYMBOL=TRADE_SYMBOL)

    # multiple sockets can be started
    # twm.start_depth_socket(callback=handle_socket_message, TRADE_SYMBOL=TRADE_SYMBOL)

    twm.start_symbol_book_ticker_socket(callback=handle_socket_message, TRADE_SYMBOL=TRADE_SYMBOL)



    # # or a multiplex socket can be started like this
    # # see Binance docs for stream names
    # streams = ['btcusdt@bookTicker']
    # twm.start_multiplex_socket(callback=handle_socket_message, streams=streams)

    twm.join()


if __name__ == "__main__":
    main()