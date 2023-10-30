import datetime
import logging
import os
import sys
import traceback


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
        path = os.path.join(os.path.realpath(__file__), '..', 'botdata', 'errlogs',
                            f'ERRLOG_{time.strftime("%Y-%m-%d_%H-%M-%S")}.txt')
        tb_str = '\n'.join(traceback.format_tb(e.__traceback__))

        data = f"""An error has occurred! Don't worry, I saved an automatic log for ya :)
----------------------------------------------------------------------
Rough DateTime: {time.strftime("%Y-%m-%d %H:%M:%S")}

Error Info:
-----------
{type(e).__name__}: {e}

Context:
{e.__context__}

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
    botdata_path = os.path.join(os.path.realpath(__file__), '..', 'botdata')
    if not os.path.isdir(botdata_path):
        os.mkdir(botdata_path)

    botdata_backup_path = os.path.join(botdata_path, 'errlogs')
    if not os.path.isdir(botdata_backup_path):
        os.mkdir(botdata_backup_path)


def new_errlog(err: BaseException):
    ErrLogger().new_errlog(err)


def errlog(func):
    return ErrLogger().errlog(func)


def async_errlog(func):
    return ErrLogger().async_errlog(func)



