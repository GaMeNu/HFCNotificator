import os

from dotenv import load_dotenv

from db_creation import __version__
import mysql.connector as mysql

target_version = __version__

load_dotenv()
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')


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


updaters = {
    '1.0.0': updater_1_0_0
}

current_version = input(f'Please enter current version (latest: {__version__}):\n')

if current_version not in updaters.keys():
    print('Invalid version.')
    exit()
with mysql.connect(host='localhost', user=DB_USERNAME, password=DB_PASSWORD) as connection:
    while current_version != target_version:
        current_version = updaters[current_version](connection)
        print(f'Updated DB to version {current_version}')

print(f'DB is now at target version!')
