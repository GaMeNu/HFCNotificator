import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
import os

from cog_notificator import Notificator

# Set up constants and logger
logger = logging.Logger('General Log')
load_dotenv()
TOKEN = os.getenv('TOKEN')
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))

handler = logging.StreamHandler()

bot = commands.Bot('!', intents=discord.Intents.all())
tree = bot.tree


@bot.event
async def on_message(msg: discord.Message):
    # Special command to sync messages
    if msg.content == '/sync_cmds' and msg.author.id == AUTHOR_ID:
        print('syncing')
        await msg.reply('Syncing...', delete_after=3)
        await Notificator.setup(bot, handler)
        await tree.sync()
        print('synced')
        await msg.reply('Synced!', delete_after=3)


@bot.event
async def on_ready():
    await Notificator.setup(bot, handler)
    await bot.change_presence(activity=discord.Activity(name='for HFC alerts.', type=discord.ActivityType.watching))


bot.run(token=TOKEN, log_handler=handler)
