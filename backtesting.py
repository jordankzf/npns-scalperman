import pandas as pd
from ta.momentum import StochasticOscillator
from ta.volume import ForceIndexIndicator, VolumeWeightedAveragePrice

btc_df = pd.read_csv('btc_bars3.csv', index_col=0)

stoch_indicator = StochasticOscillator(close=btc_df['Close'], high=btc_df['High'], low=btc_df['Low'])
force_index_indicator = ForceIndexIndicator(close=btc_df['Close'], volume=btc_df['Volume'])
vwap_indicator = VolumeWeightedAveragePrice(close=btc_df['Close'], high=btc_df['High'], low=btc_df['Low'], volume=btc_df['Volume'])

# Add TA indicators as columns to cloned dataframe
btc_df['Stoch K'] = stoch_indicator.stoch()
btc_df['Force Index'] = force_index_indicator.force_index()
btc_df['VWAP'] = vwap_indicator.volume_weighted_average_price()

# btc_df = btc_df.tail(1483583)

commission = 1.0006

previousPrice = 99999.0
currentPrice = 99999.0
stopPrice = 99999.0
newStopPrice = 99999.0
firstRun = True
attemptPurchase = False
activeOrder = False
orderType = "b"
lastPurchasePriceAt = 99999.0
noOfOrders = 0

USDT_balance = 5000
BTC_balance = 0
BTC_cost_basis = 0
USDT_spent = 0
purchase_size = 10

def trail_order(tick):
    global firstRun, previousPrice, stopPrice, newStopPrice, attemptPurchase, activeOrder, orderType, lastPurchasePriceAt
    if attemptPurchase:
        if orderType == "b":
            if firstRun:
                previousPrice = tick['Close']
                # print("Initial price is " + str(previousPrice))
                stopPrice = previousPrice / 0.999
                # print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
                firstRun = False
            else:
                currentPrice = tick['Close']
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice < previousPrice:
                    # print("Current price is " + str(currentPrice))
                    newStopPrice = currentPrice / 0.999

                    if newStopPrice < stopPrice:
                        stopPrice = newStopPrice
                        # print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                if currentPrice >= stopPrice:
                    print("Bought at " + str(currentPrice))
                    buy(currentPrice)
                    lastPurchasePriceAt = currentPrice
                    attemptPurchase = False
                    activeOrder = True
                    firstRun = True

                    previousPrice = currentPrice
        elif orderType == "s":
            if firstRun:
                previousPrice = tick['Close']
                # print("Initial price is " + str(previousPrice))
                stopPrice = previousPrice * 1
                # print("Initial Stop Loss Price updated to {:.4f}".format(stopPrice))
                firstRun = False
            else:
                currentPrice = tick['Close']
                # if currentPrice == previousPrice:
                #     print("The price has stayed the same")
                if currentPrice > previousPrice:
                    # print("Current price is " + str(currentPrice))
                    newStopPrice = currentPrice * 0.999

                    if newStopPrice > stopPrice:
                        stopPrice = newStopPrice
                        # print("Stop Loss Price updated to {:.4f}".format(stopPrice))
                    
                if currentPrice <= stopPrice:
                    print("Sold at " + str(currentPrice))
                    sell(currentPrice)
                    attemptPurchase = False
                    activeOrder = False
                    firstRun = True

                    previousPrice = currentPrice

def buy(BTC_price):
    global USDT_balance, BTC_balance, USDT_spent, noOfOrders, purchase_size

    # BTC_price = BTC_price * commission

    if noOfOrders == 0:
        purchase_size = 10
    else:
        purchase_size = purchase_size * 2

    USDT_amount = purchase_size
    
    if USDT_amount <= USDT_balance:
        USDT_balance -= USDT_amount
        USDT_spent += USDT_amount
        BTC_balance += USDT_amount / BTC_price / commission
        noOfOrders += 1

def sell(BTC_price):
    global USDT_balance, BTC_balance, USDT_spent, noOfOrders

    # BTC_price = BTC_price / commission

    USDT_balance += BTC_balance * BTC_price / commission
    BTC_balance = 0
    USDT_spent = 0
    noOfOrders = 0

def calcCostBasis():
    global USDT_spent, BTC_balance
    return USDT_spent / BTC_balance * commission * commission

def calcProfitTarget():
    return calcCostBasis() * 1.003
    
for index, tick in btc_df.iterrows():
    trail_order(tick)
    # Initial entry
    if (tick['Close'] < tick['VWAP']) and (tick['Stoch K'] <= 30) and (tick['Force Index'] <= -250) and not activeOrder:
        orderType = "b"
        attemptPurchase = True
    # If I have any open positions
    if BTC_balance > 0:
        # If I'm at profit
        if tick['Close'] > calcProfitTarget():
            orderType = "s"
            attemptPurchase = True
        # If price dropped further
        if tick['Close'] < (lastPurchasePriceAt * 0.996):
            orderType = "b"
            attemptPurchase = True


print("Final USDT balance is")
print(USDT_balance)

print("Final BTC balance is")
print(BTC_balance)

algo_return = (((USDT_balance + BTC_balance * btc_df['Close'][-1]) / 5000) - 1) * 100

print("Mr. Scalperman has bestowed upon you {:.2f}%".format(algo_return))

bnh_return = ((btc_df['Close'][-1] / btc_df['Close'][0]) - 1) * 100

print("If you were to just buy and hodl, you would have gotten {:.2f}%".format(bnh_return))