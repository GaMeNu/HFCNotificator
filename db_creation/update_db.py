import os

from dotenv import load_dotenv

import db_creation
import mysql.connector as mysql

target_version = db_creation.__version__

load_dotenv()
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')


def updater_1_0_0(connection: mysql.connection.MySQLConnection) -> str:
    crsr = connection.cursor()
    crsr.execute('ALTER TABLE `hfc_db`.`channels` '
                 'ADD COLUMN `locations` JSON '
                 'DEFAULT JSON_ARRAY();')
    crsr.close()
    return '1.0.1'


updaters = {
    '1.0.0': updater_1_0_0
}

current_version = input('Please enter current version:\n')

if current_version not in updaters.keys():
    print('Invalid version.')
    exit()
with mysql.connect(host='localhost', user=DB_USERNAME, password=DB_PASSWORD) as connection:
    while current_version != target_version:
        current_version = updaters[current_version](connection)
