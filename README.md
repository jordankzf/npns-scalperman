# NPNS Scalperman

not profit NOT SELL - a surprisingly simple strategy that might just work.

## Rules

* Long ONLY
* Close only with profit
* Take profit at the first possible chance
* No leverage
* Buy the dips! (Buy low, sell high duh)
* Average down
* Many in, one out (exit all positions simultaneously)

## Strategy

This is how the algorithm works:

1. Monitor Stochastic indicator for low range.
1. If favourable, long a small position using trailing stop buy.
1. If the current prices drops by X%, long again with twice the initial position amount.
	1. Repeat if price drops further until running out of capital.
1. If average cost basis price rises by 0.3%, close the position using trailing stop sell.

## Extra Features
1. Volume monitoring
2. Confidence adjustment

## Acronyms
1. NPNS - not profit NOT SELL
2. MIMO - I'm in, I'm out
3. FTW - Follow the whales
4. RTD - Ride the dip
5. JBAP - Just be a pussy

## Instructions
1. Create a Discord bot
2. Add it to your server via https://discord.com/oauth2/authorize?client_id=852766365012983828&permissions=268823632&scope=bot

## To-do list

1. Implement Stochastic monitoring. ✅
2. Implement live price data ✅
2. Implement trailing stop buy. ✅
3. Implement averaging down. ✅
4. Implement MIMO sell. ✅
5. Implement backtesting. ✅
6. Clean up variable names. ✅
7. Implement graceful exiting. ✅
8. Refactor with OOP. ✅
9. Integrate Discord bot support. ✅
10. Instabuy / instasell based on Force Index. ❌
11. Fix trailing stop. ❌
12. Implement crash recovery. ❌
13. DIY Range-bound Force Index ❌

## Known bugs
1. $webhook command indiscriminately selects first existing webhook.
2. config.WEBHOOK doesn't work when it's empty.
3. Ctrl+C crash recovery doesn't exit gracefully. ❌
4. buy() missing 1 required positional argument: 'self' ✅ Fixed
5. current_purchase_size will double endlessly if quote asset runs out. ✅

## Resources

1. Live RSI Monitoring from  Binance https://github.com/hackingthemarkets/binance-tutorials
1. Backtrade Testing with Binance https://github.com/lth-elm/backtrading-python-binance