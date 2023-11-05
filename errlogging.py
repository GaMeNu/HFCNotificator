import datetime
import logging
import os
import sys
import traceback

import __main__
from pathlib import Path

main_dir = Path(__main__.__file__).parent
botdata_dir = main_dir.joinpath('botdata')
errlog_dir = botdata_dir.joinpath('errlogs')


class ErrLogger:
    def __init__(self, handler: logging.Handler=None):
        if handler is None:
            handler = logging.StreamHandler()

        self.log = logging.Logger('ErrLogger')
        self.log.addHandler(handler)

    def new_errlog(self, err: BaseException):
        self.log.error('An error has occurred! Check the latest ERRLOG file for more info.')
        e: BaseException = err
        time = datetime.datetime.now()
        path = os.path.join(errlog_dir,
                            f'ERRLOG_{time.strftime("%Y-%m-%d_%H-%M-%S")}.txt')
        tb_str = ''

        context_ls = list()
        context_ls.append(e)

        ctx = e.__context__

        while ctx is not None:
            context_ls.append(ctx)

        context_str = '\n'.join([context.__str__() for context in context_ls])

        tb_str = '\n\n'.join(
            ['\n'.join(traceback.format_tb(exc.__traceback__)) for exc in context_ls]
        )

        data = f"""An error has occurred! Don't worry, I saved an automatic log for ya :)
----------------------------------------------------------------------
Rough DateTime: {time.strftime("%Y-%m-%d %H:%M:%S")}

Error Info:
-----------
{type(e).__name__}: {e}

Context:
{context_str}

Caused by:
{e.__cause__}

Full Traceback:
---------------
{tb_str}
"""

        with open(path, 'w') as f:
            f.write(data)

    def errlog(self, func):
        def wrapper(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
            except Exception as e:
                self.new_errlog(e)
            else:
                return res

        return wrapper

    def async_errlog(self, func):
        async def wrapper(*args, **kwargs):
            try:
                res = await func(*args, **kwargs)
            except Exception as e:
                self.new_errlog(e)
            else:
                return res

        return wrapper


def generate_errlog_folder():
    if not botdata_dir.is_dir():
        botdata_dir.mkdir()

    if not errlog_dir.is_dir():
        errlog_dir.mkdir()


def new_errlog(err: BaseException):
    ErrLogger().new_errlog(err)


def errlog(func):
    return ErrLogger().errlog(func)


def async_errlog(func):
    return ErrLogger().async_errlog(func)



