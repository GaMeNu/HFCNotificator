import datetime
import json
import os
import requests

import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands

import logging
from db_access import DBAccess
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
            ret_dict = None
        else:
            ret_dict = json.loads(decoded)

        return ret_dict

    @staticmethod
    def request_history_json() -> dict:
        """
        Request a json of the alert history from last day
        :return: JSON object as Python dict
        :raises requests.exceptions.Timeout: If request times out (5 seconds)
        """
        req = requests.get('https://www.oref.org.il/WarningMessages/History/AlertsHistory.json', timeout=5)

        content = req.text

        return json.loads(content)


class Alert:
    def __init__(self, id: int, cat: int, title: str, districts: list[str], desc: str):
        self.id = id
        self.category = cat
        self.title = title
        self.districts = districts
        self.description = desc

    @staticmethod
    def from_dict(data: dict):
        return Alert(int(data.get('id', '0')), int(data.get('cat', '0')), data.get('title'), data.get('data'),
                     data.get('desc'))


# noinspection PyUnresolvedReferences
class Notificator(commands.Cog):
    districts: list[dict] = json.loads(requests.get('https://www.oref.org.il//Shared/Ajax/GetDistricts.aspx').text)

    def __init__(self, bot: commands.Bot, handler: logging.Handler):
        self.bot = bot

        self.log = logging.Logger('Notificator')
        self.log.addHandler(handler)

        self.db = DBAccess()

        self.active_districts = []



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
        if current_alert is None:
            return

        data: list[str] = current_alert["data"]

        new_districts: list[str] = []

        for district in data:

            if district in self.active_districts:
                continue

            new_districts.append(district)

        if len(new_districts) == 0:
            return

        await self.send_new_alert(current_alert, new_districts)
        self.active_districts = data

    @staticmethod
    def generate_alert_embed(alert_object: Alert, district: str, arrival_time: int | None, time: str,
                             lang: str) -> discord.Embed:
        e = discord.Embed(color=discord.Color.from_str('#FF0000'))
        e.title = f'התראה ב{district}'
        match alert_object.category:
            case 1:
                e.add_field(name=district, value=alert_object.title, inline=False)
                if arrival_time is not None:
                    e.add_field(name='זמן מיגון', value=f'{arrival_time} שניות', inline=False)
                else:
                    e.add_field(name='זמן מיגון', value='שגיאה בהוצאת המידע', inline=False)
            case _:
                e.add_field(name=district, value=alert_object.title)
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

        embed_ls: list[discord.Embed] = []
        embed_ls_ls: list[list[discord.Embed]] = []

        new_alert = Alert.from_dict(alert_data)

        for district in new_districts:
            district_data = self.db.get_district_by_name(district)
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

            alert_time_str = alert_time.strftime("%Y-%m-%d %H:%M:%S")
            if district_data is not None:
                embed_ls.append(Notificator.generate_alert_embed(new_alert, district, district_data.migun_time,
                                                                 alert_time_str, 'he'))
            else:
                embed_ls.append(Notificator.generate_alert_embed(new_alert, district, None, alert_time_str, 'he'))
            if len(embed_ls) == 10:
                embed_ls_ls.append(embed_ls)
                embed_ls = []

        if len(embed_ls) > 0:
            embed_ls_ls.append(embed_ls)

        for channel in self.db.channel_iterator():
            self.log.info(channel.id)
            if channel.server_id is not None:
                dc_ch = self.bot.get_channel(channel.id)
            else:
                dc_ch = self.bot.get_user(channel.id)
            for embed_list in embed_ls_ls:
                if dc_ch is None:
                    continue
                try:
                    await dc_ch.send(embeds=embed_list, view=self.hfc_button_view())
                except BaseException as e:
                    self.log.warning(f'Failed to send alert in channel {await self.bot.get_channel(channel.id).name} ({channel.id}):\n'
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
            await ch.set_permissions(target=ch.guild.me, overwrite=perms, reason='Update perms to allow bot to send messages in channel.')
        except discord.errors.Forbidden as e:
            await intr.followup.send(f'Could not allow bot to send messages to this channel! Please add the bot to this channel and allow it to send messages.\n'
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
    async def unregister_channel(self, intr: discord.Interaction):
        channel_id = intr.channel_id

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

        page_info = f'Page {page_number + 1}/{alert_counter//alerts_in_page + 1}\n\n'

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
                          'Please do note that the main version of the bot is hosted on a private machine, so it may be a bit slow.\n'
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

    @app_commands.command(name='test_alert', description='Send a test alert (available to bot author only)')
    async def test_alert(self, intr: discord.Interaction):
        if intr.user.id != AUTHOR_ID:
            await intr.response.send_message('No access.')
            return
        await intr.response.send_message('Sending test alert...')

        await self.send_new_alert({
            "id": "133413211330000000",
            "cat": "1",
            "title": "בדיקת מערכת שליחת התראות",
            "data": [
                "בדיקה"
            ],
            "desc": "התעלמו מהודעה זו."
        }, ['בדיקה'])
