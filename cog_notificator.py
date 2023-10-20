import asyncio
import datetime
import json
import os
import random
from _xxsubinterpreters import channel_recv

import requests

import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands

import logging

import db_access
from db_access import *
from markdown import md

load_dotenv()
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))


class AlertReqs:
    @staticmethod
    def request_alert_json() -> dict | None:
        """
        Request a json of the current running alert
        :return: JSON object as Python dict, or None if there's no alert running
        :raises requests.exceptions.Timeout: If request times out (5 seconds)
        """
        req = requests.get('https://www.oref.org.il/WarningMessages/alert/alerts.json', headers={
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest',
            'Client': 'HFC Notificator bot for Discord'
        }, timeout=5)

        decoded = req.content.decode('utf-8-sig')

        if decoded is None or len(decoded) < 3:  # Why does it get a '\r\n' wtf
            ret_dict = {}
        else:
            try:
                ret_dict = json.loads(decoded)
            except (json.decoder.JSONDecodeError, json.JSONDecodeError):
                ret_dict = None

        return ret_dict

    @staticmethod
    def request_history_json() -> dict | None:
        """
        Request a json of the alert history from last day
        :return: JSON object as Python dict
        :raises requests.exceptions.Timeout: If request times out (5 seconds)
        """
        req = requests.get('https://www.oref.org.il/WarningMessages/History/AlertsHistory.json', timeout=5)

        content = req.text

        try:
            ret_dict = json.loads(content)
        except (json.JSONDecodeError, json.decoder.JSONDecodeError):
            ret_dict = None
        return ret_dict


class Alert:
    def __init__(self, id: int, cat: int, title: str, districts: list[str], desc: str):
        self.id = id
        self.category = cat
        self.title = title
        self.districts = districts
        self.description = desc

    @staticmethod
    def from_dict(data: dict):
        return Alert(int(data.get('id', '0')),
                     int(data.get('cat', '0')),
                     data.get('title'),
                     data.get('data'),
                     data.get('desc'))


class DistrictEmbed(discord.Embed):
    def __init__(self, district_id: int, **kwargs):
        self.district_id = district_id
        super().__init__(**kwargs)

# noinspection PyUnresolvedReferences
class Notificator(commands.Cog):
    location_group = app_commands.Group(name='locations',
                                        description='Commands related adding, removing, or setting locations.')
    districts: list[dict] = json.loads(requests.get('https://www.oref.org.il//Shared/Ajax/GetDistricts.aspx').text)

    def __init__(self, bot: commands.Bot, handler: logging.Handler):
        self.bot = bot

        self.log = logging.Logger('Notificator')
        self.log.addHandler(handler)

        self.db = DBAccess()

        self.active_districts = []
        self.reset_district_checker = 0

        if not self.check_for_updates.is_running():
            self.check_for_updates.start()

    @staticmethod
    async def setup(bot: commands.Bot, handler: logging.Handler):

        notf = Notificator(bot, handler)
        if bot.get_cog('Notificator') is None:
            await bot.add_cog(notf)
        return notf

    @commands.Cog.listener()
    async def on_ready(self):
        if self.check_for_updates.is_running():
            return
        self.check_for_updates.start()

    @tasks.loop(seconds=1)
    async def check_for_updates(self):
        try:
            current_alert: dict = AlertReqs.request_alert_json()
        except requests.exceptions.Timeout as error:
            self.log.error(f'Request timed out: {error}')
            return
        self.log.debug(f'Alert response: {current_alert}')

        if current_alert is None or len(current_alert) == 0:
            if current_alert is None:
                self.log.warning('Error while current alert data.')

            if len(self.active_districts) == 0:
                return

            self.reset_district_checker += 1
            if self.reset_district_checker == 3:
                print('reset')
                self.active_districts = []
                self.reset_district_checker = 0
            return

        data: list[str] = current_alert["data"]

        new_districts: list[str] = []

        for district in data:

            if district in self.active_districts:
                continue

            new_districts.append(district)

        if len(new_districts) == 0:
            return
        try:
            await self.send_new_alert(current_alert, new_districts)
        except BaseException as e:
            self.log.error(f'Could not send message!\nError info: {e.__str__()}')
        self.active_districts = data

    @check_for_updates.after_loop
    async def update_loop_error(self):
        # Attempt to force stupid "Unread Result" down its own throat
        # and just reset the connection.
        # I'm not dealing with Unread Results
        self.db.connection.close()
        self.db = DBAccess()
        if not self.check_for_updates.is_running():
            self.check_for_updates.start()

    @staticmethod
    def generate_alert_embed(alert_object: Alert, district: str, arrival_time: int | None, time: str,
                             lang: str, district_id: int) -> DistrictEmbed:
        # TODO: Using 1 generate alert function is probably bad, should probably split into a utility class
        e = DistrictEmbed(district_id=district_id, color=discord.Color.from_str('#FF0000'))
        e.title = f'התראה ב{district}'
        e.add_field(name=district, value=alert_object.title, inline=False)
        match alert_object.category:
            case 1:
                if arrival_time is not None:
                    e.add_field(name='זמן מיגון', value=f'{arrival_time} שניות', inline=False)
                else:
                    e.add_field(name='זמן מיגון', value='שגיאה באחזרת המידע', inline=False)

            case _:
                pass
        e.add_field(name='נכון ל', value=time, inline=False)
        e.add_field(name='מידע נוסף', value=alert_object.description)
        return e

    @staticmethod
    def hfc_button_view() -> discord.ui.View:
        button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label='אתר פיקוד העורף',
            url='https://www.oref.org.il'
        )
        view = discord.ui.View()
        view.add_item(button)
        return view

    async def send_new_alert(self, alert_data: dict, new_districts: list[str]):
        try:
            alert_history = AlertReqs.request_history_json()[0:100]
        except requests.exceptions.Timeout as error:
            self.log.error(f'Request timed out: {error}')
            alert_history = None
        self.log.info(f'Sending alerts to channels')

        embed_ls: list[DistrictEmbed] = []

        new_alert = Alert.from_dict(alert_data)

        for district in new_districts:
            district_data = self.db.get_district_by_name(district)  # DB
            alert_time = datetime.datetime.now()  # .strftime()

            # TODO: THIS REQUIRES SIMPLIFICATION ASAP
            if alert_history is not None:
                for alert in alert_history:
                    if alert["data"] == district:
                        new_time = datetime.datetime.strptime(alert["alertDate"], "%Y-%m-%d %H:%M:%S")
                        time_diff = abs(alert_time - new_time)
                        # Check if new time is withing 5 minutes
                        if time_diff <= datetime.timedelta(minutes=1):
                            # We have a match. Assign and stop looking
                            alert_time = new_time
                            break
            else:
                alert_time = datetime.datetime.now()

                # it's not within 5 minutes, keep looking.
                # DF Code ruined me, and now I overuse break and continue.

            alert_time_str = alert_time.strftime("%H:%M:%S\n%d/%m/%Y")
            if district_data is not None:
                embed_ls.append(Notificator.generate_alert_embed(new_alert, district, district_data.migun_time,
                                                                 alert_time_str, 'he', district_data.id))
            else:
                embed_ls.append(Notificator.generate_alert_embed(new_alert, district, None, alert_time_str, 'he', district_data.id))

        for channel_tup in self.db.get_all_channels():
            channel = Channel.from_tuple(channel_tup)
            if channel.server_id is not None:
                dc_ch = self.bot.get_channel(channel.id)
            else:
                dc_ch = self.bot.get_user(channel.id)

            channel_districts = self.db.get_channel_district_ids(channel.id)

            for emb in embed_ls:
                if dc_ch is None:
                    continue
                if len(channel.locations) != 0 and emb.district_id not in channel.locations:
                    continue
                try:
                    await dc_ch.send(embed=emb, view=self.hfc_button_view())
                    await asyncio.sleep(0.01)
                except BaseException as e:
                    self.log.warning(f'Failed to send alert in channel id={channel.id}:\n'
                                     f'{e}')

    @app_commands.command(name='register',
                          description='Register a channel to receive HFC alerts (Requires Manage Channels)')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def register_channel(self, intr: discord.Interaction):
        channel_id = intr.channel_id
        if intr.channel.guild is not None:
            server_id = intr.channel.guild.id
        else:
            server_id = None
            channel_id = intr.user.id

        await self.attempt_registration(intr, channel_id, server_id)

    async def attempt_registration(self, intr, channel_id, server_id):
        if self.db.get_channel(channel_id) is not None:
            try:
                await intr.response.send_message(f'Channel #{intr.channel.name} is already receiving HFC alerts.')
            except AttributeError:
                await intr.response.send_message(f'This channel is already receiving HFC alerts.')
            return

        if server_id is not None and self.db.get_server(server_id) is None:
            self.db.add_server(server_id, 'he')
        self.db.add_channel(channel_id, server_id, 'he')
        try:
            await intr.response.send_message(f'Channel #{intr.channel.name} will now receive HFC alerts.')
        except AttributeError:
            await intr.response.send_message(f'This channel will now receive HFC alerts.')
        try:
            ch = self.bot.get_channel(channel_id)
            perms = ch.overwrites_for(self.bot.user)
            perms.update(send_messages=True)
            await ch.set_permissions(target=ch.guild.me, overwrite=perms,
                                     reason='Update perms to allow bot to send messages in channel.')
        except discord.errors.Forbidden as e:
            await intr.followup.send(
                f'Could not allow bot to send messages to this channel! Please add the bot to this channel and allow it to send messages.\n'
                f'Error info: {e.__str__()}')

    @register_channel.error
    async def register_channel_error(self, intr: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if intr.guild is not None:
                await intr.response.send_message('Error: You are missing the Manage Channels permission.')
                return
            await self.attempt_registration(intr, intr.user.id, None)

    @app_commands.command(name='unregister',
                          description='Stop a channel from receiving HFC alerts (Requires Manage Channels)')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unregister_channel(self, intr: discord.Interaction, confirmation: str = None):
        channel_id = intr.channel_id

        conf_str = intr.user.name

        if confirmation is None:
            await intr.response.send_message(
                f'Are you sure you want to unregister the channel?\nThis action will also clear all related data.\n{md.b("Warning:")} this action cannot be reversed!\nPlease type your username ("{conf_str}") in the confirmation argument to confirm.')
            return
        if confirmation != conf_str:
            await intr.response.send_message(f'Invalid confirmation string!')
            return

        channel = self.db.get_channel(channel_id)
        if channel is None:
            channel = self.db.get_channel(intr.user.id)

        await self.attempt_unregistration(intr, channel)

    async def attempt_unregistration(self, intr, channel):
        if channel is None:
            try:
                await intr.response.send_message(f'Channel #{intr.channel.name} is not yet receiving HFC alerts')
            except AttributeError:
                await intr.response.send_message(f'This channel is not yet receiving HFC alerts')
            return

        if channel.server_id is not None:
            self.db.remove_channel(channel.id)
        else:
            self.db.remove_channel(intr.user.id)
        try:
            await intr.response.send_message(f'Channel #{intr.channel.name} will no longer receive HFC alerts')
        except AttributeError:
            await intr.response.send_message(f'This channel will no longer receive HFC alerts')

    @unregister_channel.error
    async def unregister_channel_error(self, intr: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if intr.guild is not None:
                await intr.response.send_message('Error: You are missing the Manage Channels permission.')
                return
            await self.attempt_unregistration(intr, self.db.get_channel(intr.user.id))

    @app_commands.command(name='latest',
                          description='Get all alerts up to a certain time back (may be slightly outdated)')
    @app_commands.describe(time='Amount of time back',
                           unit="The unit of time, can be 'h' (hors), 'm' (minutes), or 's' (seconds)",
                           page='Results page')
    async def latest_alerts(self, intr: discord.Interaction, time: int, unit: str, page: int = 1):
        """
        Get all alerts up to a certain time back (this may be slightly outdated)
        :param intr: command
        :param time: Amount of time back
        :param unit: The unit of time, can be 'h' (hors), 'm' (minutes), or 's' (seconds)
        :param page: Results page
        :return:
        """
        units = ['h', 'hours', 'm', 'minutes', 's', 'seconds']
        if unit not in units:
            await intr.response.send_message(f'Invalid time unit, please use one of the following:\n'
                                             f'{", ".join(units)}')
            return
        time_s = time
        if unit in ['h', 'hours']:
            time_s *= 3600
        elif unit in ['m', 'minutes']:
            time_s *= 60

        if time_s > 86400:
            await intr.response.send_message('You can currently only view history up to 1 day back.\n'
                                             f'Please use the {md.u(md.hl("Home Front Command Website", "https://www.oref.org.il/"))} to view alerts further back')
            return

        page_number = page - 1
        alert_count = 20

        try:
            history_page = Notificator.get_alert_history_page(time_s, page_number, alert_count)
        except requests.exceptions.Timeout:
            await intr.response.send_message('Request timed out.')
            return
        except ValueError as e:
            await intr.response.send_message(e.__str__())
            return

        if history_page == '':
            history_page = 'No results found.'

        view = self.hfc_button_view()
        await intr.response.send_message(history_page,
                                         view=view)

    @staticmethod
    def get_alert_history_page(time_back_amount: int, page_number: int, alerts_in_page: int) -> str:
        """
        max_page is EXCLUSIVE!
        :param time_back_amount: amount of time back
        :param page_number: the page number (starting at 0)
        :param alerts_in_page: The number of alerts in one page
        :return: page as str
        """
        alert_history = AlertReqs.request_history_json()

        current_time = datetime.datetime.now()
        time_back = datetime.timedelta(seconds=time_back_amount)

        alert_counter = 0

        for alert in alert_history:
            # This can be merged with the other loop to optimize performance.
            # Especially considering Python is a slow language.
            # Too bad!
            alert_date = datetime.datetime.strptime(alert["alertDate"], "%Y-%m-%d %H:%M:%S")

            if abs(current_time - alert_date) > time_back:
                break

            alert_counter += 1

        max_page = alert_counter // alerts_in_page

        if alert_counter % alerts_in_page != 0:
            max_page += 1

        print(max_page, page_number)

        if time_back_amount <= 0:
            raise ValueError("Time can't be lower than 1.")

        if max_page == 0:
            raise ValueError("No results found.")

        if page_number >= max_page:
            raise ValueError("Page number is too high.")
        if page_number < 0:
            raise ValueError("Page number is too low.")

        page_info = f'Page {page_number + 1}/{alert_counter // alerts_in_page + 1}\n\n'

        ret_str = ''

        for alert in alert_history[(page_number * alerts_in_page):((page_number + 1) * alerts_in_page)]:
            alert_date = datetime.datetime.strptime(alert["alertDate"], "%Y-%m-%d %H:%M:%S")

            if abs(current_time - alert_date) > time_back:
                break

            ret_str += f'התראה ב{md.b(alert["data"])}\n' \
                       f'{md.u(alert["title"])}\n' \
                       f'בשעה {alert["alertDate"]}\n\n'

        if ret_str == '':
            ret_str = 'No results found'
        else:
            ret_str = page_info + ret_str

        return ret_str

    @app_commands.command(name='about', description='Info about the bot')
    async def about_bot(self, intr: discord.Interaction):
        e = discord.Embed(color=discord.Color.orange())
        e.title = 'Home Front Command Notificator'
        e.description = 'A bot to send Discord messages for HFC alerts'
        e.add_field(name='Important info!',
                    value=f'This bot is {md.b("unofficial")} and is not related to the Home Front Command. Please do not rely on this alone.',
                    inline=False)
        e.add_field(name='What is this?',
                    value='This is a bot that connects to the HFC\'s servers and sends real-time notifications about alerts in Israel.',
                    inline=False)
        e.add_field(name='Setup',
                    value='Just invite the bot to a server (see Links below), and /register a channel to start receiving notifications.\n'
                          'Alternatively, you can /register a DM directly with the bot.\n'
                          'Please do note that the main instance of the bot is hosted on a private machine, so it may be a bit slow.\n'
                          'Feel free to host your own instance!',
                    inline=False)
        e.add_field(name='Can I host it?',
                    value='Yes! Everything is available in the GitHub repository.\nMore info on the project\'s README page (See Links below).',
                    inline=False)
        e.add_field(name='Links',
                    value=md.bq(f'{md.hl("GitHub", "https://github.com/GaMeNu/HFCNotificator")}\n'
                                f'{md.hl("Official Bot Invite Link", "https://discord.com/api/oauth2/authorize?client_id=1160344131067977738&permissions=0&scope=applications.commands%20bot")}\n'
                                f'{md.hl("HFC Website", "https://www.oref.org.il/")}\n'
                                f'{md.hl("Bot Profile (for DMs)", "https://discord.com/users/1160344131067977738")}'),
                    inline=True)

        e.add_field(name='Created by', value=md.bq('GaMeNu (@gamenu)\n'
                                                   'Yrrad8'),
                    inline=True)
        hfc_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label='HFC Website',
            url='https://www.oref.org.il'
        )
        gh_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label='GitHub Repository',
            url='https://github.com/GaMeNu/HFCNotificator'
        )
        view = discord.ui.View()
        view.add_item(hfc_button)
        view.add_item(gh_button)
        await intr.response.send_message(embed=e, view=view)

    @app_commands.command(name='send_alert', description='Send a custom alert (available to bot author only)')
    async def test_alert(self,
                         intr: discord.Interaction,
                         title: str = 'בדיקת מערכת שליחת התראות',
                         desc: str = 'התעלמו מהתראה זו',
                         districts: str = 'בדיקה',
                         cat: int = 99):
        if intr.user.id != AUTHOR_ID:
            await intr.response.send_message('No access.')
            return
        await intr.response.send_message('Sending test alert...')

        districts_ls = [word.strip() for word in districts.split(',')]

        await self.send_new_alert({
            "id": "133413211330000000",
            "cat": str(cat),
            "title": title,
            "data": districts_ls,
            "desc": desc
        }, districts_ls)

    @staticmethod
    async def has_permission(intr: discord.Interaction) -> bool:
        if intr.guild is not None and not intr.user.guild_permissions.manage_channels:
            await intr.response.send_message('Error: You are missing the Manage Channels permission.')
            return False
        return True

    @staticmethod
    def locations_page(data_list: list, page: int, res_in_page: int = 50) -> str:
        """
        Page starts at 0

        max_page is EXCLUSIVE
        :param data_list: custom data list to get page info of
        :param page: District page
        :param res_in_page: Amount of districts to put in one pages
        :return:
        """

        dist_ls = data_list

        dist_len = len(dist_ls)

        if dist_len == 0:
            return 'No results found.'

        max_page = dist_len // res_in_page
        if dist_len % res_in_page != 0:
            max_page += 1

        if page >= max_page:
            raise ValueError('Page number is too high.')
        if page < 0:
            raise ValueError('Page number is too low.')

        page_content = f'Page {md.b(f"{page + 1}/{max_page}")}\n\n<District ID> - <District name>\n\n'

        start_i = page * res_in_page
        end_i = min(start_i + res_in_page, dist_len)
        for district in dist_ls[start_i:end_i]:
            page_content += f'{district[0]} - {district[1]}\n'

        return page_content

    @location_group.command(name='list', description='Show the list of all available locations')
    async def locations_list(self, intr: discord.Interaction, page: int = 1):

        try:
            page = self.locations_page(sorted(self.db.get_all_districts(), key=lambda tup: tup[1]), page - 1)
        except ValueError as e:
            await intr.response.send_message(e.__str__())
            return

        if len(page) > 2000:
            await intr.response.send_message(
                'Page content exceeds character limit.\nPlease contact the bot authors with the command you\'ve tried to run.')
            return

        await intr.response.send_message(page)

    @location_group.command(name='add', description='Add a location(s) to the location list')
    @app_commands.describe(locations='A list of comma-separated Area IDs')
    async def location_add(self, intr: discord.Interaction, locations: str):
        if not await self.has_permission(intr):
            return

        locations_ls = [word.strip() for word in locations.split(',')]
        location_ids = []
        for location in locations_ls:
            try:
                location_ids.append(int(location))
            except ValueError:
                await intr.response.send_message(f'District ID {md.b(f"{location}")} is not a valid district ID.')
                return

        channel_id = intr.channel_id

        channel = self.db.get_channel(channel_id)
        if channel is None:
            channel = self.db.get_channel(intr.user.id)
            if channel is None:
                await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
                return

        try:
            self.db.add_channel_districts(channel.id, location_ids)
        except ValueError as e:
            await intr.response.send_message(e.__str__())
            return

        await intr.response.send_message('Successfully added all IDs')

    @location_group.command(name='remove', description='Remove a location(s) to the location list')
    @app_commands.describe(locations='A list of comma-separated Area IDs')
    async def location_remove(self, intr: discord.Interaction, locations: str):

        if not await self.has_permission(intr):
            return

        locations_ls = [word.strip() for word in locations.split(',')]
        location_ids = []
        for location in locations_ls:
            try:
                location_ids.append(int(location))
            except ValueError:
                await intr.response.send_message(f'District ID {md.b(f"{location}")} is not a valid district ID.')
                return

        channel_id = intr.channel_id

        channel = self.db.get_channel(channel_id)
        if channel is None:
            channel = self.db.get_channel(intr.user.id)
            if channel is None:
                await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
                return

        self.db.remove_channel_districts(channel.id, location_ids)
        await intr.response.send_message('Successfully removed all IDs')

    @location_group.command(name='clear', description='Clear all registered locations (get alerts on all locations)')
    async def location_clear(self, intr: discord.Interaction, confirmation: str = None):

        if not await self.has_permission(intr):
            return

        conf_str = intr.user.name

        channel_id = intr.channel_id

        channel = self.db.get_channel(channel_id)
        if channel is None:
            channel = self.db.get_channel(intr.user.id)
            if channel is None:
                await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
                return

        if confirmation is None:
            await intr.response.send_message(
                f'Are you sure you want to clear all registered locations?\n{md.b("Warning:")} this action cannot be reversed!\nPlease type your username ("{conf_str}") in the confirmation argument to confirm.')
            return
        if confirmation != conf_str:
            await intr.response.send_message(f'Invalid confirmation string!')
            return

        self.db.clear_channel_districts(channel.id)
        await intr.response.send_message(
            f'Cleared all registered locations.\nChannel will now receive alerts from every location.')

    @location_group.command(name='registered', description='List all locations registered to this channel')
    async def location_registered(self, intr: discord.Interaction, page: int = 1):

        channel_id = intr.channel_id

        channel = self.db.get_channel(channel_id)
        if channel is None:
            channel = self.db.get_channel(intr.user.id)
            if channel is None:
                await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
                return

        # Congrats! It's a MESS!
        # This code is so ugly, but basically
        #
        # It gets a list of all of a channel's districts
        # Converts it to a tuple form in which
        # district_tuple = (district_id: int, district_name: str, area_id: int, migun_time: int)
        # Then it sorts it with the key being district_name
        districts = sorted([self.db.get_district(district_id).to_tuple()
                            for district_id
                            in self.db.get_channel_district_ids(channel.id)],
                           key=lambda tup: tup[1])

        page = self.locations_page(districts, page - 1)

        if len(page) > 2000:
            await intr.response.send_message(
                'Page content exceeds character limit.\nPlease contact the bot authors with the command you\'ve tried to run.')
            return

        await intr.response.send_message(page)
