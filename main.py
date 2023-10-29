import datetime
import sys
import traceback
import types
from types import TracebackType

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
    await bot.change_presence(activity=discord.Activity(name='for HFC alerts.', type=discord.ActivityType.watching))

    botdata_path = os.path.join(os.path.realpath(__file__), '..', 'botdata')
    if not os.path.isdir(botdata_path):
        os.mkdir(botdata_path)

    botdata_backup_path = os.path.join(botdata_path, 'backups')
    if not os.path.isdir(botdata_backup_path):
        os.mkdir(botdata_backup_path)

    await Notificator.setup(bot, handler)


@bot.event
async def on_error(event, *args, **kwargs):
    e: tuple[type, Exception, types.TracebackType] = sys.exc_info()
    time = datetime.datetime.now()
    path = os.path.join(os.path.realpath(__file__), '..', 'botdata', 'backups', f'ERRLOG_{time.strftime("%Y-%m-%d_%H-%M-%S")}.txt')
    tb_str = '\n'.join(traceback.format_tb(e[2]))

    data = f"""
An error has occurred! Don't worry, I saved an automatic log for ya :)
----------------------------------------------------------------------
Rough DateTime: {time.strftime("%Y-%m-%d %H:%M:%S")}
Error: {e[0].__name__}: {e[1]}

Traceback:
----------
{tb_str}
"""

    with open(path, 'w') as f:
        f.write(data)

bot.run(token=TOKEN, log_handler=handler)
