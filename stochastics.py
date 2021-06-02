from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager, BinanceSocketManager, AsyncClient
import json
import csv
import pandas as pd
import btalib
import asyncio

api_key = "HnufrYMSQS2zCl00YZnTgKBYtx8JoPXyNxGAJY24am9XZKpFhhsLaV220FvGAzCh"
api_secret = "Bkca4jr0ffcgNxOsKD2vBkjkmx5j9jF5pn4YecZP9s6UXR1sHr7AGQEqxA2HeLHO"

client = Client(api_key, api_secret)
client.API_URL = "https://testnet.binance.vision/api"

timestamp = client._get_earliest_valid_timestamp('BTCUSDT', '1m')
bars = client.get_historical_klines('BTCUSDT', '1m', timestamp, limit=1000)

for line in bars:
    del line[5:]

btc_df = pd.DataFrame(bars, columns=['date', 'open', 'high', 'low', 'close'])
btc_df.set_index('date', inplace=True)
print(btc_df.head())
btc_df.to_csv('btc_bars3.csv')

btc_df = pd.read_csv('btc_bars3.csv', index_col=0)
btc_df.index = pd.to_datetime(btc_df.index, unit='ms')

stoch = btalib.stoch(btc_df, period=14)

print(stoch.df.k[-1])

##async def main():
##    client = await AsyncClient.create()
##    bm = BinanceSocketManager(client)
##    # start any sockets here, i.e a trade socket
##    ts = bm.trade_socket('BTCUSDT')
##    # then start receiving messages
##    async with ts as tscm:
##        while True:
##            res = await tscm.recv()
##            print(res)
##
##    await client.close_connection()
##
##if __name__ == "__main__":
##
##    loop = asyncio.get_event_loop()
##    loop.run_until_complete(main())
