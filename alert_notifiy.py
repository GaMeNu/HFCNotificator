import datetime
import discord

import db_access

from db_access import AreaDistrict

class Alert:
    """
    Represents an HFC Alert
    """
    def __init__(self, id: int, cat: int, title: str, districts: list[str], desc: str):
        """
        Init an Alert instance
        :param id: Alert ID
        :param cat: Alert category
        :param title: Alert title
        :param districts: districts the alert is running for
        :param desc: Alert description/extra info
        """
        self.id = id
        self.category = cat
        self.title = title
        self.districts = districts
        self.description = desc

    @classmethod
    def from_dict(cls, data: dict):
        """
        Return a new Alert instance from an Alert-formatted dict (matching HFC alert requests)

        Dict format:

        {
            "id": int,
            "cat": int,
            "title": str,
            "data": list[str],
            "desc": str
        }

        :param data: A dict of matching format

        :return: The new Alert instance
        """
        return cls(int(data.get('id', '0')),
                   int(data.get('cat', '0')),
                   data.get('title'),
                   data.get('data'),
                   data.get('desc'))

class AlertEmbed:
    """
    A class representing an AlertEmbed

    :var embed: discord.Embed ready for sending
    :var alert: Alert containing alert data
    :var district: db_access.AreaDistrict | str containing district data
    """

    def __init__(self, alert: Alert | dict,  district: db_access.AreaDistrict | str):
        """
        Initiating the AlertEmbed class directly is equivalent to AlertEmbed.generic_alert, but is not recommended.

        Please use AlertEmbed.generic_alert instead.

        :var embed: discord.Embed ready for sending
        :var alert: Alert containing alert data
        :var district: db_access.AreaDistrict | str containing district data
        """
        self.embed = discord.Embed(color=discord.Color.from_str('#FF0000'))
        self.district = district
        if isinstance(alert, dict):
            self.alert = Alert.from_dict(alert)
        else:
            self.alert = alert

        if isinstance(self.district, AreaDistrict):
            self.embed.title = f'התראה ב{self.district.name}'
            self.embed.add_field(name=self.alert.title, value=f'איזור {self.district.area.name}')

        else:
            self.embed.title = f'התראה ב{self.district}'
            self.embed.add_field(name=self.alert.title, value='')

        self.embed.add_field(name='נכון ל', value=datetime.datetime.now().strftime("%H:%M:%S\n%d/%m/%Y"), inline=False)
        self.embed.add_field(name='מידע נוסף', value=self.alert.description)

    @classmethod
    def generic_alert(cls, alert: Alert | dict, district: db_access.AreaDistrict | str):
        """
        Returns a new Generic AlertEmbed
        :param alert: Alert object
        :param district: AreaDistrict object (District containing Area, check db_access.AreaDistrict)
        :return: New AlertEmbed instance
        """
        ret_alem = cls(alert, district)
        return ret_alem

    @classmethod
    def missile_alert(cls, alert: Alert | dict, district: db_access.AreaDistrict | str):
        """
        Returns a new Missile AlertEmbed

        Similar to Generic AlertEmbed, but contains Migun Time

        :param alert: Alert object
        :param district: AreaDistrict object (District containing Area, check db_access.AreaDistrict)
        :return: New AlertEmbed instance
        """
        ret_alem = cls.generic_alert(alert, district)

        if (not isinstance(district, str)) and (district.migun_time is not None):
            ret_alem.embed.insert_field_at(index=1, name='זמן מיגון', value=f'{district.migun_time} שניות', inline=False)
            return ret_alem

        ret_alem.embed.insert_field_at(index=1, name='זמן מיגון', value='שגיאה באחזרת המידע', inline=False)
        return ret_alem

    @classmethod
    def auto_alert(cls, alert: Alert | dict, district: db_access.AreaDistrict | str):
        """
        Tired of having to CHOOSE an alert type all the time? Well this is JUST for you!

        Introducing... auto_alert! Just init it like any other alert, and it will return the fitting alert right then and there*!

        *"then and there" does not include any computer, end-user, developer, or any other type of tomfoolery.

        (Hopefully now I'll never have to write documentation again >:) )

        :param alert: Alert object or alert dict.
        :param district: District object (from db_access)
        :return: AlertEmbed object
        """
        if isinstance(alert, dict):
            alert_obj = Alert.from_dict(alert)
        else:
            alert_obj = alert

        match alert_obj.category:
            case 1:
                return cls.missile_alert(alert_obj, district)
            case _:
                return cls.generic_alert(alert_obj, district)

