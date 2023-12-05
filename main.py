import sys

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
import os

import errlogging
from cog_notificator import Notificator

# Set up constants and logger
logger = logging.Logger('General Log')
load_dotenv()
TOKEN = os.getenv('TOKEN')
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))

handler = logging.StreamHandler()
logger.addHandler(handler)

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

    errlogging.generate_errlog_folder()

    await Notificator.setup(bot, handler)


@bot.event
async def on_error(event, *args, **kwargs):
    logger.error('An error has occurred! Check the latest ERRLOG for more info')
    errlogging.new_errlog(sys.exc_info()[1])

bot.run(token=TOKEN, log_handler=handler)
