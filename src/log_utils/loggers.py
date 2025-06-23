import __main__
import logging
import logging.handlers
from pathlib import Path

import discord

from utils.dir_utils import DirUtils

dir_utils = DirUtils()
LOGGING_DIR = dir_utils.botdata_dir.joinpath('logs')


class ColorFormatter(discord.utils._ColourFormatter):
    """
    Custom formatter based on Discord.py's color formatter, while changing the color for the datetime
    """

    LEVEL_COLOURS = [
        (logging.DEBUG, '\x1b[40;1m', '\x1b[97m'),
        (logging.INFO, '\x1b[34;1m', '\x1b[97;1m'),
        (logging.WARNING, '\x1b[33;1m', '\x1b[93m'),
        (logging.ERROR, '\x1b[31m', '\x1b[91m'),
        (logging.CRITICAL, '\x1b[41m', '\x1b[41;97;1m'),
    ]
    FORMATS = {
        level: logging.Formatter(
            f'\x1b[37;1m%(asctime)s\x1b[0m {type_color}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m {msg_color}%(message)s\x1b[0m',
            '%Y-%m-%d %H:%M:%S',
        )
        for level, type_color, msg_color in LEVEL_COLOURS
    }


class DefaultFileHandler(logging.FileHandler):
    def __init__(self, filename: str):
        generate_logging_folder()

        path = Path(LOGGING_DIR, filename)
        # Make sure the damn file exists
        if not (path.exists() or path.is_file()):
            path.touch()

        super().__init__(Path(LOGGING_DIR, filename))
        self.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            '%Y-%m-%d %H:%M:%S',
        ))
        self.setLevel(logging.INFO)


def generate_logging_folder():
    if not dir_utils.botdata_dir.is_dir():
        dir_utils.botdata_dir.mkdir()

    if not LOGGING_DIR.is_dir():
        LOGGING_DIR.mkdir()
