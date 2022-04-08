import asyncio
from binance import BinanceSocketManager, AsyncClient
import decimal

decimal.getcontext().rounding = decimal.ROUND_DOWN

# client = Client("eUXdZ64iVV2b2Rwb53r675CXEb4DCcpCuymnjkj3CQRCsSEdcFG4J2xeJusxJsrW", "oXh6fDA0ricTeplgJ4HwIhD6767QvF1lHPyd8FMhaaqonUUD2mPTGpaNzRyanKba")

precision = 0.0001

# SCALP Button
# 1. Get ETH balance
# 2. Get lowest book order price
# 3. Calculate sell order 2 + 0.1
# 4. Place sell order #3
# 4. Listen for order completion
# 5. Place buy order #3 + 0.025%

async def main():
    client = await AsyncClient.create("eUXdZ64iVV2b2Rwb53r675CXEb4DCcpCuymnjkj3CQRCsSEdcFG4J2xeJusxJsrW", "oXh6fDA0ricTeplgJ4HwIhD6767QvF1lHPyd8FMhaaqonUUD2mPTGpaNzRyanKba")
    # client = await AsyncClient.create("YZu9lbP2nRYflUHU1TU3L9JS0QTORQni1TuvOTpbrp6QIPmYxNN2IpIakL5Ab2Pv", "i39EspBAfFC5bSWOydo2Jb1MKnre7ijDhFsWo3OEjlQQafeLP8kKUvT0EQy9mZFn", testnet=True)
    bsm = BinanceSocketManager(client)

    orders = await client.get_open_orders(symbol='ETHBUSD')
    print(orders)

    ticker = await client.get_ticker(symbol="ETHBUSD")

    average = (decimal.Decimal(ticker['highPrice']) + decimal.Decimal(ticker['lowPrice'])) / 2

    lastPrice = ticker['lastPrice']

    banned = ['1', '2', '8', '9']
    if set(banned) & set(lastPrice[2:4]):
        print("Have some discipline! Don't trade at pivot numbers.")
        await client.close_connection()
        quit()

    if (decimal.Decimal(lastPrice) < average):
        print("Have some discipline! Wait till we're above the 24hr average.")
        await client.close_connection()
        quit()

    ETH_bal = (await client.get_asset_balance(asset="ETH"))['free']

    print(f'ETH Bal is {ETH_bal}')

    quantityRounded = decimal.Decimal(ETH_bal)
    quantityRounded = round(quantityRounded, 4)

    print(f'rounded sell quantity {quantityRounded}')

    # input("On standby - waiting on your command...")

    option = input("How big are your balls?")
    take_profit_table = {
        "5": 0.003,
        "4": 0.002,
        "3": 0.001,
        "2": 0.0005,
        "1": 0.00025
    }

    take_profit = take_profit_table[option]

    # {'lastUpdateId': 8408009886, 'bids': [['3397.35000000', '0.12340000']], 'asks': [['3397.36000000', '59.31670000']]}
    ETH_currentprice = await client.get_order_book(symbol="ETHBUSD", limit=1)

    print(f'ETH current price is {ETH_currentprice}')

    sell_at = float(ETH_currentprice['asks'][0][0]) + 0.1
    sell_at = round(sell_at, 2)

    sell = await client.order_limit_sell(symbol="ETHBUSD", quantity=quantityRounded, price=sell_at)

    print(f'sell {sell}')

    if sell['status'] == "FILLED":
        print("Oops, I fucked up. That was a market buy.")

    async with bsm.user_socket() as ts:
        while True:
            res = await ts.recv()
            print(f'recv {res}')
            # {'e': 'executionReport', 'E': 1648638930181, 's': 'ETHBUSD', 'c': 'electron_8e0c75c855594e06be0a4e68a64', 'S': 'BUY', 'o': 'LIMIT', 'f': 'GTC', 'q': '4.25190000', 'p': '3387.67000000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '', 'x': 'TRADE', 'X': 'PARTIALLY_FILLED', 'r': 'NONE', 'i': 4427591143, 'l': '0.12400000', 'z': '0.12400000', 'L': '3387.67000000', 'n': '0.00000000', 'N': 'BNB', 'T': 1648638930180, 't': 280261711, 'I': 9101786246, 'w': False, 'm': True, 'M': True, 'O': 1648638876738, 'Z': '420.07108000', 'Y': '420.07108000', 'Q': '0.00000000'}
            if res['e'] == 'executionReport' and res['X'] == 'FILLED':
                buy_at = sell_at * (1 - take_profit)
                buy_at_rounded = round(buy_at, 2)
                quantity = quantityRounded * decimal.Decimal(1 + take_profit)
                quantityRounded = round(quantity, 4)
                buy = await client.order_limit_buy(symbol="ETHBUSD", quantity=quantityRounded, price=buy_at_rounded)
                print(f'buy {buy}')
                await client.close_connection()
                break
            # {'e': 'outboundAccountPosition', 'E': 1648638930181, 'u': 1648638930180, 'B': [{'a': 'ETH', 'f': '0.12408258', 'l': '0.00000000'}, {'a': 'BNB', 'f': '0.02467758', 'l': '0.00000000'}, {'a': 'BUSD', 'f': '0.03082154', 'l': '13983.96299300'}]}
            # if res['e'] == 'outboundAccountPosition' and res['']
            # if order_status == "FILLED":
            #     order_quantity = res['q']
            #     print(f'order quantity {order_quantity}')
            #     break
            
    # BUSD_bal = (await client.get_asset_balance(asset="BUSD"))['free']
    # ETH_currentprice = await client.get_order_book(symbol="ETHBUSD", limit=1)
    # min_buy_at = float(ETH_currentprice['bids'][0][0]) - 0.1
    # buy_at = sell_at * (1 - take_profit)
    # buy_at_rounded = round(buy_at, 2)
    # # quantity = decimal.Decimal(BUSD_bal) / buy_at
    # quantity = quantityRounded * decimal.Decimal(1 + take_profit)
    # quantityRounded = round(quantity, 4)
    # buy = await client.order_limit_buy(symbol="ETHBUSD", quantity=quantityRounded, price=buy_at_rounded)
    # print(f'buy {buy}')
    
    # await client.close_connection()



    # print(orders)
    # print(ETH_currentprice)
    # print(sell_at)

if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())


    # orders = client.get_all_orders(symbol='ETHBUSD', limit=1)

    # orders[0]['status']