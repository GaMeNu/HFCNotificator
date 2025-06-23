import asyncio
import json
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import os

from log_utils import errlogging, loggers
from utils.dir_utils import DirUtils
from botinfo import botinfo

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
        # Give COG_Notificator's loop time to breath and do another cycle,
        # and lower system resource usage
        await asyncio.sleep(0.5)


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


async def reload_bot():
    # Reload all cogs
    await load_all_cogs()
    logger.info("All cogs loaded")

    # Reload bot info
    botinfo.reload()
    logger.info("Bot information reloaded")


@bot.command(name="reload")
async def _reload_cogs(ctx: commands.Context):
    if ctx.author.id != AUTHOR_ID:
        return

    logger.info(f"Reload was initiated by user @{ctx.author.name} (id={ctx.author.id})")
    await ctx.reply("Reloading...", delete_after=3)
    await reload_bot()
    await ctx.reply("Done reloading!")


@bot.command(name="sync")
async def _reload_cogs_and_sync(ctx: commands.Context):
    if ctx.author.id != AUTHOR_ID:
        return

    # Notify about sync occuring
    logger.info(f'Sync was initiated by user @{ctx.author.name} (id={ctx.author.id})')
    logger.info('Syncing commands...')
    await ctx.reply('Syncing...', delete_after=3)

    tree.clear_commands(guild=None)

    await reload_bot()
    # Sync
    await tree.sync()

    logger.info('Synced!')
    await ctx.reply('Done syncing!')


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
