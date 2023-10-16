import logging
import os
import time

from dotenv import load_dotenv
from mysql import connector as mysql

load_dotenv()
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')


class Area:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name


class District:
    def __init__(self, id: int, name: str, area_id: int, migun_time: int):
        self.id = id
        self.name = name
        self.area_id = area_id
        self.migun_time = migun_time


class Channel:
    def __init__(self, id: int, server_id: int | None, channel_lang: str):
        self.id = id
        self.server_id = server_id
        self.channel_lang = channel_lang


class Server:
    def __init__(self, id: int, lang: str):
        self.id = id
        self.lang = lang


class ChannelIterator:
    def __init__(self, cursor: mysql.connection.MySQLCursor):
        self.cursor = cursor

    def __iter__(self):
        return self

    def __next__(self) -> Channel:
        res = self.cursor.fetchone()
        if res is None:
            self.cursor.close()
            raise StopIteration
        return Channel(res[0], res[1], res[2])


class DBAccess:
    def __init__(self, handler: logging.Handler = None):

        log = logging.Logger('DBAccess')

        if handler is not None:
            log.addHandler(handler)
        else:
            log.addHandler(logging.StreamHandler())

        self.connection = None

        for i in range(12):
            try:
                self.connection = mysql.connect(
                    host='localhost',
                    user=DB_USERNAME,
                    password=DB_PASSWORD,
                    database='hfc_db'
                )
                break
            except mysql.Error as e:
                self.connection = None
                log.warning(f"Couldn't connect to db. This is attempt #{i}")
                time.sleep(5)

        if self.connection is None:
            self.connection = mysql.connect(
                host='localhost',
                user=DB_USERNAME,
                password=DB_PASSWORD,
                database='hfc_db'
            )

    def add_area(self, area_id: int, area_name: str):
        with self.connection.cursor() as crsr:
            crsr.execute(f'REPLACE INTO areas (area_id, area_name) VALUES (%s, %s)', (area_id, area_name))
            self.connection.commit()

    def add_district(self, district_id: int, district_name: str, area_id: int, area_name: str, migun_time: int):
        with self.connection.cursor() as crsr:
            crsr.execute(f'SELECT * FROM areas WHERE area_id=%s', (area_id,))
            crsr.fetchall()

            if crsr.rowcount == 0:
                self.add_area(area_id, area_name)

            crsr.execute(f'REPLACE INTO districts (district_id, district_name, area_id, migun_time) VALUES (%s, %s, %s, %s)', (district_id, district_name, area_id, migun_time))
            self.connection.commit()

    def add_server(self, server_id: int, server_lang: str):
        with self.connection.cursor() as crsr:
            crsr.execute(f'INSERT IGNORE INTO servers (server_id, server_lang) VALUES (%s, %s)', (server_id, server_lang))
        self.connection.commit()

    def add_channel(self, channel_id: int, server_id: int | None, channel_lang: str | None):
        with self.connection.cursor() as crsr:
            if server_id is not None:
                self.add_server(server_id, channel_lang)
            crsr.execute(f'REPLACE INTO channels (channel_id, server_id, channel_lang) VALUES (%s, %s, %s)', (channel_id, server_id, channel_lang))
            self.connection.commit()

    def get_area(self, id: int) -> Area | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM areas WHERE area_id=%s', (id,))
            res = crsr.fetchone()
            crsr.fetchall()

        if res is not None:
            return Area(res[0], res[1])
        else:
            return None

    def get_district(self, id: int) -> District | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM districts WHERE district_id=%s', (id,))
            res = crsr.fetchone()
            crsr.fetchall()

        if res is not None:
            return District(res[0], res[1], res[2], res[3])
        else:
            return None

    def get_district_area(self, district: District) -> Area | None:
        return self.get_area(district.area_id)

    def get_server(self, id: int) -> Server | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM servers WHERE server_id=%s', (id,))
            res = crsr.fetchone()
            crsr.fetchall()

        if res is not None:
            return Server(res[0], res[1])
        else:
            return None

    def get_channel(self, id: int) -> Channel | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM channels WHERE channel_id=%s', (id,))
            res = crsr.fetchone()
            crsr.fetchall()

        if res is not None:
            return Channel(res[0], res[1], res[2])
        else:
            return None

    def get_channel_server(self, channel: Channel) -> Server:
        return self.get_server(channel.server_id)

    def channel_iterator(self):
        crsr = self.connection.cursor()

        crsr.execute('SELECT * FROM channels')

        return ChannelIterator(crsr)

    def remove_channel(self, id: int):
        print(id)
        with self.connection.cursor() as crsr:
            crsr.execute('DELETE FROM channels WHERE channel_id=%s', (id,))
        self.connection.commit()

    def remove_server(self, id: int):
        with self.connection.cursor() as crsr:
            crsr.execute('DELETE FROM channels WHERE server_id=%s', (id,))
            crsr.execute('DELETE FROM servers WHERE server_id=%s', (id,))
        self.connection.commit()

    def remove_district(self, id: int):
        with self.connection.cursor() as crsr:
            crsr.execute('DELETE FROM districts WHERE district_id=%s', (id,))
        self.connection.commit()

    def remove_area(self, id: int):
        with self.connection.cursor() as crsr:
            crsr.execute('DELETE FROM districts WHERE area_id=%s', (id,))
            crsr.execute('DELETE FROM areas WHERE area_id=%s', (id,))
        self.connection.commit()

    def get_district_by_name(self, name: str) -> District | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM districts WHERE district_name=%s', (name,))
            res = crsr.fetchone()
            crsr.fetchall()

        if res is None:
            return None

        return District(res[0], res[1], res[2], res[3])
