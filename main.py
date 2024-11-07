import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import os

import errlogging
import loggers
from cog_notificator import Notificator

# Set up constants and logger
load_dotenv()
TOKEN = os.getenv('TOKEN')
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))

logger = logging.Logger('General Log')
handler = logging.StreamHandler()
handler.setFormatter(loggers.ColorFormatter())
logger.addHandler(handler)
logger.addHandler(loggers.DefaultFileHandler("LOG_GENERAL.log"))

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
    loggers.generate_logging_folder()

    if bot.get_cog('Notificator') is None:
        await Notificator.setup(bot, handler)

@bot.event
async def on_resumed():
    if bot.get_cog('Notificator') is None:
        await Notificator.setup(bot, handler)


@bot.event
async def on_error(event, *args, **kwargs):
    logger.error('An error has occurred! Check the latest ERRLOG for more info')
    errlogging.new_errlog(sys.exc_info()[1])


bot.run(token=TOKEN, log_handler=handler, log_formatter=handler.formatter)
