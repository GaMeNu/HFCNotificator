import json
import os

from dotenv import load_dotenv

from db_creation import __version__
import mysql.connector as mysql

from utils.dir_utils import DirUtils

target_version = __version__

load_dotenv()
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')

dir_utils = DirUtils()
dir_utils.ensure_working_directory()

DB_DATA = dir_utils.botdata_dir.joinpath("db_data.json")


class DB_data:
    def __init__(self, data: dict):
        self.local_version = data.get("local_version", None)

    @staticmethod
    def ensure_data_created():
        if not (DB_DATA.exists() and DB_DATA.is_file()):
            DB_DATA.touch()
            with open(DB_DATA, "w") as f:
                json.dump({
                    "local_version": __version__
                }, f)

    @classmethod
    def load(cls):
        global local_version

        cls.ensure_data_created()

        with open(DB_DATA, "r") as f:
            res = json.load(f)

        return cls(res)

    def write(self):
        with open(DB_DATA, "w") as f:
            json.dump({
                "local_version": self.local_version
            }, f)


def updater_1_0_0(connection: mysql.connection.MySQLConnection) -> str:
    with connection.cursor() as crsr:
        crsr.execute("SELECT COLUMN_NAME "
                     "FROM INFORMATION_SCHEMA.COLUMNS "
                     "WHERE TABLE_SCHEMA = 'hfc_db' "
                     "AND TABLE_NAME = 'channels' "
                     "AND COLUMN_NAME = 'locations';")

        exists = (crsr.fetchone() is not None)

        crsr.nextset()

        if exists:
            crsr.execute("ALTER TABLE `hfc_db`.`channels` DROP COLUMN `locations`;")

        crsr.execute("ALTER TABLE `hfc_db`.`channels` ADD COLUMN `locations` JSON NOT NULL DEFAULT ('[]');")

    return '1.0.1'


# Load data
db_data = DB_data.load()

updaters = {
    '1.0.0': updater_1_0_0
}

if db_data.local_version is None:
    current_version = input(f'Could not automatically detect DB version.\nPlease enter current version (latest: {__version__}):\n')
else:
    current_version = db_data.local_version

if current_version == __version__:
    print("Already at target version!")
    exit()

if current_version not in updaters.keys():
    print(f'Invalid version "{current_version}".')
    exit()
with mysql.connect(host='localhost', user=DB_USERNAME, password=DB_PASSWORD) as connection:
    while current_version != target_version:
        current_version = updaters[current_version](connection)
        print(f'Updated DB to version {current_version}')

db_data.local_version = current_version
db_data.write()

print(f'DB is now at target version!')
