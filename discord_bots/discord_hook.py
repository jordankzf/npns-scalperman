import discord
from discord.ext import commands
from discord.utils import get
import config
from bot import Binance_Bot

description = 'Waifu Discord bot for Mr. Scalperman'
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='$', description=description, intents=intents)

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the markets very closely 👀"))

@bot.command()
async def webhook(ctx):
    channel = ctx.channel

    hooks = await channel.webhooks()

    if len(hooks) == 0:
        pfp_path = "scalperchan.png"
        fp = open(pfp_path, 'rb')
        pfp = fp.read()
        await channel.create_webhook(name="Scalper-ちゃん", avatar=pfp)
        await ctx.send("New webhook created successfully!")
    
    hooks = await channel.webhooks()
    
    string_hooks = str(hooks[0])
    truncated_hooks = string_hooks[12:30]
    hook = get(hooks, id=int(truncated_hooks))
    # print(f"before avatar {hook.avatar}")
    # hook.avatar_url = ''
    # print(f"after avatar {hook.avatar}")
    config.WEBHOOK = hook.url

    await ctx.send("Webhook connected successfully!")

@bot.command()
async def awaken(ctx):
    global binance_bot
    binance_bot = Binance_Bot()
    binance_bot.start()

@bot.command()
async def sleep(ctx):
    binance_bot.stop()

@bot.command()
async def wallet(ctx):
    Wallet = binance_bot.wallet()
    Wallet.print()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('uwu what\'s this? a long red bar just for me? what a juicy dip owo')
        return
    
    if message.content.startswith('$areyougreen'):
        await message.channel.send('What do you fucking think?')
        return

    if message.content.startswith('$btcdropwhen'):
        await message.channel.send('I\'m not a 🔮 fortune teller 🔮 bruh 🚫🧢')
        return

    if message.content.startswith('$iloveyou'):
        await message.channel.send('Ew 🤮')
        return

    if message.content.startswith('$iselondumb'):
        await message.channel.send('0 IQ')
        return

    if message.content.startswith('+search'):
        await message.channel.send('Stop gambling omg 🙄')
        return

    if message.author.id == config.DISCORD_MASTER:
        await bot.process_commands(message)
    elif message.content.startswith('$'):
        await message.channel.send("Sorry, you're not Daddy J. Can't take orders from a stranger 🤧")
    
    return

bot.run(config.DISCORD_TOKEN)

