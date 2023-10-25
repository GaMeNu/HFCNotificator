import json
import logging
import os
import time
from typing import Sequence

from dotenv import load_dotenv
from mysql import connector as mysql
from mysql.connector.abstracts import MySQLCursorAbstract

load_dotenv()
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')


class Area:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    @staticmethod
    def from_tuple(tup: Sequence):
        return Area(tup[0], tup[1])


class District:
    def __init__(self, id: int, name: str, area_id: int, migun_time: int):
        self.district_id = id
        self.name = name
        self.area_id = area_id
        self.migun_time = migun_time

    @staticmethod
    def from_tuple(tup: Sequence):
        return District(tup[0], tup[1], tup[2], tup[3])

    def to_tuple(self) -> tuple:
        return self.district_id, self.name, self.area_id, self.migun_time


class AreaDistrict(District):
    def __init__(self, id: int, name: str, area_id: int, migun_time: int, area: Area):
        super().__init__(id, name, area_id, migun_time)
        self.area = area

    @classmethod
    def from_district(cls, district: District, area: Area):
        return cls(district.district_id, district.name, district.area_id, district.migun_time, area)


class Channel:
    def __init__(self, id: int, server_id: int | None, channel_lang: str, locations: list):
        self.id = id
        self.server_id = server_id
        self.channel_lang = channel_lang
        self.locations = locations

    @staticmethod
    def from_tuple(tup: tuple):
        return Channel(tup[0], tup[1], tup[2], json.loads(tup[3]))


class Server:
    def __init__(self, id: int, lang: str):
        self.id = id
        self.lang = lang


class ChannelIterator:
    def __init__(self, cursor: MySQLCursorAbstract):
        self.cursor = cursor

    def __iter__(self):
        return self

    def __next__(self) -> Channel:
        res = self.cursor.fetchone()
        if res is None:
            self.cursor.close()
            raise StopIteration
        return Channel.from_tuple(res)


class DistrictIterator:
    def __init__(self, cursor: MySQLCursorAbstract):
        self.cursor = cursor

    def __iter__(self):
        return self

    def __next__(self) -> District:
        res = self.cursor.fetchone()
        if res is None:
            self.cursor.close()
            raise StopIteration
        return District.from_tuple(res)


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
                log.warning(f"Couldn't connect to db. This is attempt #{i}\n{e.msg}")
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
            crsr.nextset()

        if res is not None:
            return Area.from_tuple(res)
        else:
            return None

    def get_district(self, id: int) -> District | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM districts WHERE district_id=%s', (id,))
            res = crsr.fetchone()
            crsr.nextset()

        if res is not None:
            return District.from_tuple(res)
        else:
            return None

    def get_district_area(self, district: District) -> Area | None:
        return self.get_area(district.area_id)

    def get_server(self, id: int) -> Server | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM servers WHERE server_id=%s', (id,))
            res = crsr.fetchone()
            crsr.nextset()

        if res is not None:
            return Server(res[0], res[1])
        else:
            return None

    def get_channel(self, id: int) -> Channel | None:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM channels WHERE channel_id=%s', (id,))
            res = crsr.fetchone()
            crsr.nextset()

        if res is not None:
            return Channel.from_tuple(res)
        else:
            return None

    def get_channel_server(self, channel: Channel) -> Server:
        return self.get_server(channel.server_id)

    def channel_iterator(self):
        """
        This function is DEPRECATED!

        Please use get_all_channels() instead.

        Reason: Cannot create more queries while an iterator is active due to unread results.
        """
        raise NotImplementedError("This function has been deprecated!")

        with self.connection.cursor() as crsr:

            crsr.execute('SELECT * FROM channels')

            return ChannelIterator(crsr)

    def get_all_channels(self):
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM channels')
            res = crsr.fetchall()

        return res

    def remove_channel(self, id: int):
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
            crsr.nextset()

        if res is None:
            return None

        return District.from_tuple(res)

    def get_all_districts(self) -> Sequence:
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM districts')
            ret = crsr.fetchall()
        return ret

    def search_districts(self, *tokens: str) -> Sequence:
        with self.connection.cursor() as crsr:
            query = 'SELECT * FROM districts WHERE '
            query += ' AND '.join(["district_name LIKE %s" for _ in tokens])
            query += ';'
            crsr.execute(query, [f'%{token}%' for token in tokens])
            ret = crsr.fetchall()
        return ret

    def district_iterator(self) -> DistrictIterator:
        """
        This function is DEPRECATED!

        Please use get_all_districts() instead.

        Reason: Cannot create more queries while an iterator is active due to unread results.
        """
        raise NotImplementedError("This function has been deprecated!")

        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM district')

            return DistrictIterator(crsr)

    def add_channel_district(self, channel_id: int, district_id: int):
        with self.connection.cursor() as crsr:
            crsr.execute('SELECT * FROM districts WHERE district_id=%s', (district_id,))
            res = crsr.fetchone()
            crsr.nextset()
        if res is None:
            raise ValueError(f'Invalid District ID {district_id}')

        with self.connection.cursor() as crsr:
            crsr.execute("UPDATE channels "
                         "SET locations = JSON_ARRAY_APPEND(locations, '$', %s) "
                         "WHERE channel_id=%s;",
                         (district_id, channel_id))
        self.connection.commit()

    def add_channel_districts(self, channel_id: int, district_ids: list[int]):
        with self.connection.cursor() as crsr:
            # Sorry for the messy statement. I'm lazy and it's 02:13 rn
            crsr.execute(f"SELECT * FROM districts WHERE district_id IN ({','.join(['%s'] * len(district_ids))})", tuple(district_ids))
            res = crsr.fetchall()

        if len(district_ids) > len(res):
            raise ValueError('Received invalid district IDs')

        # Sorry for this way of doing things (3 DB queries omg)
        # JSON_MERGE_PATCH kept overwriting the existing data
        # while JSON_MERGE_PRESERVE did not remove duplicates
        dists = self.get_channel_district_ids(channel_id)
        updated = [district for district in district_ids if district not in dists]

        with self.connection.cursor() as crsr:

            crsr.execute("UPDATE channels "
                         "SET locations = JSON_MERGE_PRESERVE(locations, %s) "
                         "WHERE channel_id=%s;",
                         (json.dumps(updated), channel_id))
        self.connection.commit()

    def get_channel_district_ids(self, channel_id: int) -> list:
        with self.connection.cursor() as crsr:
            crsr.nextset()
            crsr.execute('SELECT locations '
                         'FROM channels '
                         'WHERE channel_id=%s;', (channel_id,))
            dist = crsr.fetchone()
            crsr.nextset()

        districts = json.loads(dist[0])
        return districts

    def district_ids_to_districts(self, *district_ids) -> list[District]:
        return [self.get_district(district_id) for district_id in district_ids]

    def search_channel_districts(self, channel_id: int, *tokens: str) -> list[District]:
        district_ids = self.get_channel_district_ids(channel_id)

        districts = [self.get_district(district_id) for district_id in district_ids]

        filtered_districts = [district for district in districts if all(token in district.name for token in tokens)]

        return filtered_districts

    def remove_channel_districts(self, channel_id: int, district_ids: list[int]):
        with self.connection.cursor() as crsr:

            districts = self.get_channel_district_ids(channel_id)

            updated = [district for district in districts if district not in district_ids]

            crsr.execute('UPDATE channels '
                         'SET locations = %s '
                         'WHERE channel_id = %s;',
                         (json.dumps(updated), channel_id))

        self.connection.commit()

    def clear_channel_districts(self, channel_id: int):
        with self.connection.cursor() as crsr:
            crsr.execute('UPDATE channels '
                         'SET locations = JSON_ARRAY() '
                         'WHERE channel_id = %s;',
                         (channel_id,))

        self.connection.commit()

    def is_registered_channel(self, channel_id: int) -> bool:
        return self.get_channel(channel_id) is not None

