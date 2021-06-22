from requests import post, get
import time

WHALE = "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ"
BARNACLE = "1FZWLKAAHHOOV3KZTGYX6QSSWXJ6SCXKSR"

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

    if (WHALE_currentbal - WHALE_lastbal) >= 1000:
        discord("The 🐳 bought!")

    WHALE_lastbal = WHALE_currentbal

    BARNACLE_currentbal = get_address_balance(BARNACLE)
    time.sleep(10)

    if (BARNACLE_currentbal - BARNACLE_currentbal) >= 1000:
        discord("The barnacle bought!")

    BARNACLE_lastbal = BARNACLE_currentbal