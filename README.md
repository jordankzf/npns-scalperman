# NPNS Scalperman

not profit NOT SELL - a surprisingly simple strategy that might just work.

## Rules

* Long ONLY
* No stop losses
* Take profit at the first possible chance
* No leverage
* Buy low, sell high a.k.a. only buy the dips (red candlesticks)
* Average down
* Many in, one out (exit all positions simultaneously)

## Strategy

This is how the algorithm works:

1. Monitor Stochastic indicator for low range.
1. If favourable, long a small position using trailing stop buy.
1. If the current prices drops by X%, long again with twice the initial position amount.
	1. Repeat if price drops further until running out of capital.
1. If average cost basis price rises by 0.3%, close the position using trailing stop sell.

## To-do list

1. Implement Stochastic monitoring.
2. Implement trailing stop buy.
3. Implement averaging down.