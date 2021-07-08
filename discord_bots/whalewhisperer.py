from requests import post, get
import time

WHALE = "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ"
BARNACLE = "1FzWLkAahHooV3kzTgyx6qsswXJ6sCXkSR"

WHALE_currentbal = None
WHALE_lastbal = None

BARNACLE_currentbal = None
WHALE_lastbal = None

def discord(message):
    post('https://discord.com/api/webhooks/856781181672095754/djDk_aohnI32yuVwniamZi6VT8ErS_P1Bj9b9Hn_f880VJhNBU7V-tu17V3viRchQpNw', {"content": message})

def get_address_balance(address, confirmations=0):
    URL = f'https://blockchain.info/q/addressbalance/{address}?confirmations={confirmations}'
    return float(get(URL).text) / 100000000

WHALE_lastbal = get_address_balance(WHALE)
time.sleep(10)
BARNACLE_lastbal = get_address_balance(BARNACLE)
time.sleep(10)

while True:
    WHALE_currentbal = get_address_balance(WHALE)
    time.sleep(10)

    change = (WHALE_currentbal - WHALE_lastbal)

    if change >= 1000:
        discord("The 🐳 bought!")
    elif change <= -1000:
        discord("The 🐳 sold!")
    else:
        print(f"The 🐳's balance stayed the same at {WHALE_currentbal}")

    WHALE_lastbal = WHALE_currentbal

    BARNACLE_currentbal = get_address_balance(BARNACLE)
    time.sleep(10)

    change = (BARNACLE_currentbal - BARNACLE_lastbal)

    if change >= 100:
        discord("The barnacle bought!")
    elif change <= -100:
        discord("The barnacle sold!")
    else:
        print(f"The barnacle's balance stayed the same at {BARNACLE_currentbal}")

    BARNACLE_lastbal = BARNACLE_currentbal