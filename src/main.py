import asyncio
import json
import sys
from importlib import import_module

import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import os

from src.utils import errlogging, loggers
from src.utils.dir_utils import DirUtils

DirUtils.ensure_working_directory()

# Set up constants and logger
load_dotenv()
TOKEN = os.getenv('TOKEN')
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))

logger = logging.Logger('General Log')
handler = logging.StreamHandler()
handler.setFormatter(loggers.ColorFormatter())
logger.addHandler(handler)
logger.addHandler(loggers.DefaultFileHandler("LOG_ALL.log"))

bot = commands.Bot('hfc/', intents=discord.Intents.all())
tree = bot.tree

cogs: dict[str, str]

def read_cog_data():
    global cogs
    with open("./src/cogs/cogs.json", "r") as f:
        cogs = json.load(f)


async def load_all_cogs():
    """
    This method will load or reload all cogs
    """

    # update cogs
    read_cog_data()

    for cog in cogs.values():
        await load_single_cog(cog)


async def load_single_cog(cog):
    """
    This method loads or reloads a single cog to the bot

    :param cog: The cog import to load
    """
    if cog in bot.extensions:
        logger.info(f'Reloading cog {cog}')
        await bot.reload_extension(cog)
    else:
        logger.info(f'Loading cog {cog}')
        await bot.load_extension(cog)


@bot.command(name="sync")
async def _reload_cogs_and_sync(ctx: commands.Context):
    if ctx.author.id != AUTHOR_ID:
        return

    # Notify about sync occuring
    logger.info(f'Sync was initiated by user @{ctx.author.name} (id={ctx.author.id})')
    logger.info('Syncing commands...')
    await ctx.send('Syncing...', delete_after=3, reference=ctx.message)

    tree.clear_commands(guild=None)
    # Reload all cogs
    await load_all_cogs()

    # Sync
    await tree.sync()

    logger.info('Synced!')
    await ctx.send('Synced!', delete_after=3, reference=ctx.message)


@bot.command()
async def load_cog(ctx: commands.Context, cog_name: str):
    if ctx.author.id != AUTHOR_ID:
        return

    read_cog_data()

    if cog_name not in cogs:
        await ctx.reply(f'Could not find cog `"{cog_name}"`')
        return

    cog = cogs[cog_name]

    if cog in bot.extensions:
        await ctx.reply(f'Reloading cog `{cog_name} ({cog})`')
    else:
        await ctx.reply(f'Loading cog `{cog_name} ({cog})`')

    await load_single_cog(cog)

    await ctx.reply('Finished!')


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(name='for HFC alerts.', type=discord.ActivityType.watching))

    errlogging.generate_errlog_folder()
    loggers.generate_logging_folder()

    if bot.get_cog('Notificator') is None:
        await load_all_cogs()


@bot.event
async def on_resumed():
    if bot.get_cog('Notificator') is None:
        await load_all_cogs()

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error('An error has occurred! Check the latest ERRLOG for more info')
    errlogging.new_errlog(sys.exc_info()[1])

if __name__ == "__main__":
    logger.info('Starting HFCNotificator...')
    logger.info(f'Working directory: {os.getcwd()}')

    bot.run(token=TOKEN, log_handler=handler, log_formatter=handler.formatter)
