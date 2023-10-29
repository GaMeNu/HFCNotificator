import datetime
import os
import sys
import traceback


def generate_errlog_folder():
    botdata_path = os.path.join(os.path.realpath(__file__), '..', 'botdata')
    if not os.path.isdir(botdata_path):
        os.mkdir(botdata_path)

    botdata_backup_path = os.path.join(botdata_path, 'backups')
    if not os.path.isdir(botdata_backup_path):
        os.mkdir(botdata_backup_path)
def new_errlog(err: BaseException):
    e: BaseException = err
    time = datetime.datetime.now()
    path = os.path.join(os.path.realpath(__file__), '..', 'botdata', 'backups', f'ERRLOG_{time.strftime("%Y-%m-%d_%H-%M-%S")}.txt')
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


def errlog(func):
    def wrapper(*args, **kwargs):
        try:
            res = func(*args, **kwargs)
        except Exception as e:
            new_errlog(e)
        else:
            print('sdgg')
            return res

    return wrapper



