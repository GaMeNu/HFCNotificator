import datetime

import discord

import db_access as db_access

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


class DistrictsEmbed:
    def __init__(self, embed: discord.Embed, districts: list[AreaDistrict | str]):
        self.embed = embed
        self.districts = districts


class AlertEmbedFactory:
    """
    This is a class representing the new alert embed
    """

    @staticmethod
    def make_alert_embed(alert_in: Alert | dict) -> discord.Embed:
        """
        Create a primary alert embed
        """
        alert = alert_in if isinstance(alert_in, Alert) else Alert.from_dict(alert_in)

        embed = discord.Embed(color=discord.Color.from_str("#FF0000"))
        embed.title = alert.title
        embed.description = 'מקומות התראה מצורפים בהודעות הבאות'
        embed.add_field(name='זמן התראה', value=datetime.datetime.now().strftime("%H:%M | %d/%m/%Y"), inline=False)
        # embed.add_field(name='אזורי התראה', value='\n'.join(areas))
        embed.add_field(name='מידע נוסף', value=alert.description, inline=False)
        return embed

    @staticmethod
    def _format_missiles(district: AreaDistrict | str) -> str:
        # This is a string
        if isinstance(district, str):
            return f'**{district}** | זמן מיגון: ללא'

        # We know that district is an AreaDistrict
        if district.migun_time is not None:
            migun_time = f'{district.migun_time} שניות'
        else:
            # It is an AreaDistrict, but for some reason there is no Migun time
            migun_time = "ללא"
        return f'**{district.name}** | זמן מיגון: {migun_time}'

    @staticmethod
    def _format_generic(district: AreaDistrict | str) -> str:
        if isinstance(district, str):
            return f'**{district}**'

        return f'**{district.name}**'

    @staticmethod
    def make_areas_embed(alert: Alert | dict, areas: set[str]):
        # Ensure alert object
        if isinstance(alert, dict):
            alert = Alert.from_dict(alert)

        embed = discord.Embed(color=discord.Color.from_str("#FF0000"))

        embed.title = 'איזורי התראה'
        embed.description = "\n".join(areas)
        return embed

    @staticmethod
    def make_districts_embed(alert: Alert | dict, districts: list[AreaDistrict | str]) -> list[DistrictsEmbed]:
        """
        Create a list of alert_embeds

        :param alert: Valid alert data
        :param districts: All active districts to be sent in the embed

        :returns: A list of all embeds, or an empty list if received no districts
        """

        # Ensure alert object
        if isinstance(alert, dict):
            alert = Alert.from_dict(alert)

        if len(districts) == 0:
            return []

        dists, fmt_ls = AlertEmbedFactory.format_districts(alert, districts)

        embed_ls = []
        if len(fmt_ls) == 0:
            return []

        # construct embeds
        i = 0
        for desc in fmt_ls:
            embed = discord.Embed(color=discord.Color.from_str("#7F7F7F"))
            embed.title = 'מקומות ההתראה'
            embed.description = desc
            dists_emb = DistrictsEmbed(embed, dists[i])
            i += 1
            embed_ls.append(dists_emb)

        return embed_ls

    @staticmethod
    def format_districts(alert: Alert, districts: list[AreaDistrict | str]) -> (list[list[str]], list[str]):
        # select district formatter
        match alert.category:
            case 1:
                formatter = AlertEmbedFactory._format_missiles
            case _:
                formatter = AlertEmbedFactory._format_generic
        # Current embed description
        fmt_ls: list[str] = []
        dists: list[list[str]] = []  # list of districts by embed index
        cur_dists: list[str] = []  # current list
        cur_desc = ''
        cur_dists_str = f"**{alert.title}** | "
        for dist in districts:
            cur_area = formatter(dist)

            if (
                    ((len(cur_desc) + len(cur_area)) > 4095)
                    or ((len(cur_dists_str) + len(f", {dist.name}")) > 1999)
            ):
                # make sure we don't overflow the embed desc limit
                fmt_ls.append(cur_desc)
                cur_desc = ''
                dists.append(cur_dists)
                cur_dists = []
                cur_dists_str = f"**{alert.title}** | "

            cur_dists_str += f", {dist.name}"
            cur_desc += cur_area + "\n"
            cur_dists.append(dist.name if isinstance(dist, AreaDistrict) else dist)

        # add final one
        if len(cur_desc) > 0:
            fmt_ls.append(cur_desc)
            dists.append(cur_dists)
        return dists, fmt_ls

    @staticmethod
    def make_unified_embed(alert_in: Alert | dict, districts: list[AreaDistrict | str]) -> DistrictsEmbed:
        # ensure alert is object
        alert = alert_in if isinstance(alert_in, Alert) else Alert.from_dict(alert_in)
        dists, fmt_ls = AlertEmbedFactory.format_districts(alert, districts)

        embed = discord.Embed(color=discord.Color.from_str("#FF0000"))
        embed.title = alert.title
        embed.add_field(name='זמן התראה', value=datetime.datetime.now().strftime("%H:%M | %d/%m/%Y"), inline=False)
        # embed.add_field(name='אזורי התראה', value='\n'.join(areas))
        embed.add_field(name='מידע נוסף', value=alert.description, inline=False)
        embed.add_field(name='מקומות ההתראה', value="\n".join(fmt_ls))

        dists_str_ls = []
        for dist in districts:
            if isinstance(dist, str):
                dists_str_ls.append(dist)
            else:
                dists_str_ls.append(dist.name)

        return DistrictsEmbed(embed, dists_str_ls)


class AlertEmbed:
    """
    DEPRECATED

    A class representing an AlertEmbed

    :var embed: discord.Embed ready for sending
    :var alert: Alert containing alert data
    :var district: db_access.AreaDistrict | str containing district data
    """

    def __init__(self, alert: Alert | dict, district: db_access.AreaDistrict | str):
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

        self.embed.add_field(name='זמן התראה', value=datetime.datetime.now().strftime("%H:%M | %d/%m/%Y"), inline=False)
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

