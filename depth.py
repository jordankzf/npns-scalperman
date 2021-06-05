from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
import config

api_key = config.API_KEY
api_secret = config.API_SECRET

client = Client(api_key, api_secret)

# socket manager using threads
twm = ThreadedWebsocketManager()
twm.start()

# depth cache manager using threads
dcm = ThreadedDepthCacheManager()
dcm.start()

def handle_socket_message(msg):
    return
    # print(f"message type: {msg['e']}")
    # print(msg)

def handle_dcm_message(depth_cache):
    print(f"symbol {depth_cache.symbol}")
    print("top 5 bids")
    print(depth_cache.get_bids()[:5])
    print("top 5 asks")
    print(depth_cache.get_asks()[:5])
    print("last update time {}".format(depth_cache.update_time))

twm.start_kline_socket(callback=handle_socket_message, symbol='BNBBTC')

dcm.start_depth_cache(callback=handle_dcm_message, symbol='BTCUSDT')

# join the threaded managers to the main thread
twm.join()
dcm.join()