import datetime
import platform
import re
import sys
from typing import Any

import cpuinfo
import discord
import distro
import psutil
import requests
from discord import app_commands
from discord.ext import commands, tasks

import src.db_access as db_access
from src.cogs.alert_reqs import AlertReqs
from src.utils import errlogging, loggers
from src.alert_maker import AlertEmbed
from src.db_access import *
from src.utils.markdown import md

load_dotenv()
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))

COG_CLASS = "COG_Commands"

cog: Any


# noinspection PyUnresolvedReferences
class COG_Commands(commands.Cog):
    """
    This cog contains all bot commands
    """
    location_group = app_commands.Group(name='locations',
                                        description='Commands related adding, removing, or setting locations.')
    districts: list[dict] = json.loads(requests.get('https://www.oref.org.il/districts/districts_heb.json').text)

    def __init__(self, bot: commands.Bot):
        """
        Create the Cog
        :param bot: Discord commands bot client
        :param handler: Logging handler
        """

        # Set up logging
        self.log = logging.Logger(COG_CLASS)

        handler = logging.StreamHandler()
        handler.setFormatter(loggers.ColorFormatter())
        self.log.addHandler(handler)
        self.log.addHandler(loggers.DefaultFileHandler("LOG_ALL.log"))

        self.log.info(f"Initializing {COG_CLASS}...")

        # Set up client and db
        self.bot = bot
        self.db = DBAccess()

        self.start_time = time.time()

        self.log.info(f"{COG_CLASS} is now initialized")

    @staticmethod
    async def setup(bot: commands.Bot):
        """
        Set up the cog
        :param bot: commands.Bot client
        :param handler: logging handler
        :return: the cog instance that was created and added to the bot
        """

        if bot.get_cog(COG_CLASS) is not None:
            return None

        cog = COG_Commands(bot)
        await bot.add_cog(cog)
        return cog

    def in_registered_channel(self, intr: discord.Interaction) -> bool | None:
        """
        an info about current channel
        :param intr: Command interaction from discord
        :return: Boolean:
        True - is a registered server channel, False - is a registered DM, None - was not found (may not be registered)
        """

        # OPTIONS:
        # Channel ID not None + DB not None: IS Channel and IS Registered => matching output and end
        # Channel ID not None + DB None: IS Channel and NOT Registered => matching output and end
        # Channel ID None cases:
        #   User ID not None + DB not None: IS DM and IS Registered
        #   User ID not None + DB None: IS DM and NOT Registered
        #
        # Off I go to make a utility function!

        # 17:42 update: Turns out I am very dumb and if the channel is not registered I don't return None but rather keep going
        # Thanks yrrad8! (/srs)

        if self.db.is_registered_channel(intr.channel_id):
            return True

        if self.db.is_registered_channel(intr.user.id):
            return False

        return None

    def get_matching_channel(self, intr: discord.Interaction) -> db_access.Channel:
        """
        Gets the matching Channel ID for Server Channel or DM. Returns None if UNREGISTERED or not found
        :param intr: Command interaction from discord
        :return:  registered channel ID
        """

        channel = self.db.get_channel(intr.channel_id)
        if channel is None:
            channel = self.db.get_channel(intr.user.id)
        return channel

    @staticmethod
    async def has_permission(intr: discord.Interaction) -> bool:
        """
        Check if current user have an admin permissions
        :param intr: Command interaction from discord
        :return: Boolean: Have a permissions
        """
        if intr.guild is not None and not intr.user.guild_permissions.manage_channels:
            return False
        return True

    @staticmethod
    def hfc_button_view() -> discord.ui.View:
        """
        Get a discord UI View containing a button with a link to the HFC Website
        :returns: discord.ui.View containing a discord.ui.Button() with link to HFC website
        """
        button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label='אתר פיקוד העורף',
            url='https://www.oref.org.il'
        )
        view = discord.ui.View()
        view.add_item(button)
        return view

    @errlogging.async_errlog
    async def send_new_alert(self, alert_data: dict, new_districts: list[str]):
        """
        Push an alert to all registered channels
        :param alert_data: Alert data dict (see test_alert for format)
        :param new_districts: Currently active districts (districts that were not already active)
        :return:
        """

        self.log.info(f'Sending alerts to channels')

        embed_dict: dict[str, AlertEmbed] = {}

        for district in new_districts:

            district_data = self.db.get_district_by_name(district)

            if district_data is not None:
                embed_dict[district] = AlertEmbed.auto_alert(
                    alert_data,
                    AreaDistrict.from_district(
                        district_data,
                        self.db.get_area(district_data.area_id)
                    )
                )

            else:
                embed_dict[district] = (AlertEmbed.auto_alert(alert_data, district))

        asyncio.create_task(self.send_alerts_to_channels(embed_dict))

    @errlogging.async_errlog
    async def send_alerts_to_channels(self, embed_dict: dict[str, AlertEmbed]):
        """
        Send the embeds in embed_dict to all channels
        :param embed_dict: Dict of AlertEmbeds by districts to send to channels
        """

        for channel_tup in self.db.get_all_channels():
            channel = Channel.from_tuple(channel_tup)
            if channel.server_id is not None:
                dc_ch = self.bot.get_channel(channel.id)
            else:
                dc_ch = self.bot.get_user(channel.id)

            prepped_embeds: dict[str, discord.Embed] = {}  # So preppy

            for dist, emb in embed_dict.items():
                # Skipping conditions
                if dc_ch is None:
                    # Channel could not be found
                    continue

                if len(channel.locations) != 0:
                    # Channel has specific locations registered
                    if isinstance(emb.district, AreaDistrict) and (emb.district.district_id not in channel.locations):
                        # District is registered but isn't in channel's registered location list
                        continue
                    if isinstance(emb.district, str):
                        # District is not registered.
                        continue

                prepped_embeds[dist] = emb.embed

                # Stack up to 10 embeds per message
                if len(prepped_embeds) == 10:
                    await self.send_one_alert_message(dc_ch, emb,  prepped_embeds)
                    prepped_embeds = {}

            # Send remaining alerts in one message
            if len(prepped_embeds) > 0:
                await self.send_one_alert_message(dc_ch, emb, prepped_embeds)

    async def send_one_alert_message(self, dc_ch, alert: AlertEmbed, embs: dict[str, discord.Embed]):
        districts_str = ", ".join(embs.keys())


        try:
            await dc_ch.send(
                content=f'{md.b(alert.alert.title)} ב{districts_str}',
                embeds=embs.values(),
                view=self.hfc_button_view()
            )
            await asyncio.sleep(0.02)
        except Exception as e:
            self.log.warning(f'Failed to send alerts in channel id={dc_ch.name}:\n'
                             f'{e}')

    @app_commands.command(name='register',
                          description='Register a channel to receive HFC alerts (Requires Manage Channels)')
    async def register_channel(self, intr: discord.Interaction):

        if not await COG_Commands.has_permission(intr):
            await intr.response.send_message('Error: You are missing the Manage Channels permission.')
            return

        if intr.guild is not None:
            channel_id = intr.channel_id
            server_id = intr.guild.id
        else:
            channel_id = intr.user.id
            server_id = None

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

        ch = self.bot.get_channel(channel_id)

        try:
            perms = ch.overwrites_for(self.bot.user)
            perms.update(send_messages=True)
            await ch.set_permissions(target=ch.guild.me, overwrite=perms,
                                     reason='Update perms to allow bot to send messages in channel.')
        except discord.errors.Forbidden as e:
            await intr.followup.send(
                f'Could not allow bot to send messages to this channel! Please add the bot to this channel and allow it to send messages.\n'
                f'Error info: {e.__str__()}')
        except AttributeError:
            pass

    @app_commands.command(name='unregister',
                          description='Stop a channel from receiving HFC alerts (Requires Manage Channels)')
    async def unregister_channel(self, intr: discord.Interaction, confirmation: str = None):

        if not await COG_Commands.has_permission(intr):
            await intr.response.send_message('Error: You are missing the Manage Channels permission.')
            return

        channel = self.get_matching_channel(intr)

        if channel is None:
            try:
                await intr.response.send_message(f'Channel #{intr.channel.name} is not yet receiving HFC alerts')
            except AttributeError:
                await intr.response.send_message(f'This channel is not yet receiving HFC alerts')
            return

        conf_str = intr.user.name

        if confirmation is None:
            await intr.response.send_message(
                f'Are you sure you want to unregister the channel?\nThis action will also clear all related data.\n{md.b("Warning:")} this action cannot be reversed!\nPlease type your username ("{conf_str}") in the confirmation argument to confirm.')
            return
        if confirmation != conf_str:
            await intr.response.send_message(f'Invalid confirmation string!')
            return

        await self.attempt_unregistration(intr, channel)

    async def attempt_unregistration(self, intr, channel: db_access.Channel):

        self.db.remove_channel(channel.id)

        try:
            await intr.response.send_message(f'Channel #{intr.channel.name} will no longer receive HFC alerts')
        except AttributeError:
            await intr.response.send_message(f'This channel will no longer receive HFC alerts')

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
            history_page = COG_Commands.get_alert_history_page(time_s, page_number, alert_count)
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

        alert_history = AlertReqs().request_history_json()

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

    @app_commands.command(name='info', description='Get client and system info')
    async def botinfo(self, intr: discord.Interaction):
        await intr.response.defer()
        # Apparently this is a fairly massive command
        # I am trying to prevent major slowdowns by creating a new task
        # This is futile
        asyncio.create_task(self.execute_bot_info(intr))

    async def execute_bot_info(self, intr):
        def format_timedelta(timedelta: datetime.timedelta):
            return f'{timedelta.days} days, {((timedelta.seconds // 3600) % 24):02}:{((timedelta.seconds // 60) % 60):02}:{(timedelta.seconds % 60):02}'

        curtime = time.time()
        client_uptime = datetime.timedelta(seconds=int(round(curtime - self.start_time)))
        client_uptime_format = format_timedelta(client_uptime)
        system_uptime = datetime.timedelta(seconds=int(round(curtime - psutil.boot_time())))
        system_uptime_format = format_timedelta(system_uptime)
        uname = platform.uname()
        if uname.system != "Linux":
            system_name = f'{uname.system} {uname.release}'
        else:
            # Goddamnit Linux too many distros
            system_name = f'{distro.name()} {distro.version_parts()[0]}.{distro.version_parts()[1]} ({distro.codename()})'
        b_to_mb = 1000000

        pid = os.getpid()
        process = psutil.Process(pid)

        e = discord.Embed(color=discord.Color.orange())
        e.title = 'Home Front Command Commands'
        e.description = 'Info about this bot instance'
        e.add_field(name='', value=f'''```asciidoc
==== Instance and Client Information ====
Bot Version            :: {botinfo.version} 
Client Uptime          :: {client_uptime_format}
Instance Maintainer(s) :: {botinfo.maintainer}

Guilds Joined          :: {len(self.bot.guilds)}
Registered channels    :: {len(self.db.get_all_channels())}

==== System Information ====
OS            :: {system_name}
System Uptime :: {system_uptime_format}

CPU           :: {cpuinfo.get_cpu_info()["brand_raw"]}
CPU Usage     :: {psutil.cpu_percent()}%
Cores         :: {psutil.cpu_count(logical=False)} ({psutil.cpu_count(logical=True)} Threads)

RAM Usage     :: {(psutil.virtual_memory().used / b_to_mb):.2f} MB / {(psutil.virtual_memory().total / b_to_mb):.2f} MB ({psutil.virtual_memory().percent}%)
```''', inline=False)
        await intr.followup.send(embed=e)

    @app_commands.command(name='about', description='About the bot')
    async def about_bot(self, intr: discord.Interaction):
        e = discord.Embed(color=discord.Color.orange())
        e.title = 'Home Front Command Commands'
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
                    value=md.bq(f'{md.hl("GitHub", "https://github.com/GaMeNu/HFCCommands")}\n'
                                f'{md.hl("Official Bot Invite Link", "https://discord.com/api/oauth2/authorize?client_id=1160344131067977738&permissions=0&scope=applications.commands%20bot")}\n'
                                f'{md.hl("HFC Website", "https://www.oref.org.il/")}\n'
                                f'{md.hl("Bot Profile (for DMs)", "https://discord.com/users/1160344131067977738")}\n'
                                f'{md.hl("Support Server", "https://discord.gg/K3E4a5ekNy")}'),
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
            url='https://github.com/GaMeNu/HFCCommands'
        )
        view = discord.ui.View()
        view.add_item(hfc_button)
        view.add_item(gh_button)
        await intr.response.send_message(embed=e, view=view)

    @app_commands.command(name='send_alert', description='Send a custom alert (available to bot author only)')
    @app_commands.describe(title='Alert title',
                           desc='Alert description',
                           districts='Active alert districts',
                           cat='Alert category',
                           override='Whether to override cooldown protection')
    async def test_alert(self,
                         intr: discord.Interaction,
                         title: str = 'בדיקת מערכת שליחת התראות',
                         desc: str = 'התעלמו מהתראה זו',
                         districts: str = 'בדיקה',
                         cat: int = 99,
                         override: bool = False):
        """
        A function to send a test alert
        :param intr: Command interaction from discord
        :param title: Title of the alert
        :param desc: Description of the alert
        :param districts: Districts of the alert
        :param cat: Category of the alert
        :return:
        """
        if intr.user.id not in [AUTHOR_ID]:
            await intr.response.send_message('No access.')
            return
        await intr.response.send_message('Sending test alert...')

        districts_ls = [word.strip() for word in districts.split(',')]

        alert_data = {
            "id": "133413211330000000",
            "cat": str(cat),
            "title": title,
            "data": districts_ls,
            "desc": desc
        }

        if not override:
            await self.handle_alert_data(alert_data)
        else:
            await self.send_new_alert(alert_data, districts_ls)

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

        page_content = f'Page {md.b(f"{page + 1}/{max_page}")}\n\n'

        start_i = page * res_in_page
        end_i = min(start_i + res_in_page, dist_len)
        for district in dist_ls[start_i:end_i]:
            page_content += f'{district[0]} - {district[1]}\n'

        return page_content

    @location_group.command(name='list',
                            description='List all available locations, by IDs and names. Sorted alphabetically')
    @app_commands.describe(search='Search tokens, separated by spaces')
    async def locations_list(self, intr: discord.Interaction, search: str | None = None, page: int = 1):
        # decide the search_results
        if search is not None:
            search_results = self.db.search_districts(*re.split(r"\s+", search))
        else:
            search_results = self.db.get_all_districts()

        try:
            # Turn into a display-able page
            page = self.locations_page(sorted(search_results, key=lambda tup: tup[1]), page - 1)
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
            await intr.response.send_message('Error: You are missing the Manage Channels permission.')
            return

        channel = self.get_matching_channel(intr)
        if channel.id is None:
            await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
            return

        locations_ls = [word.strip() for word in locations.split(',')]
        location_ids = []
        for location in locations_ls:
            try:
                location_ids.append(int(location))
            except ValueError:
                await intr.response.send_message(f'District ID {md.b(f"{location}")} is not a valid district ID.')
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
            await intr.response.send_message('Error: You are missing the Manage Channels permission.')
            return

        channel = self.get_matching_channel(intr)
        if channel is None:
            await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
            return

        locations_ls = [word.strip() for word in locations.split(',')]
        location_ids = []
        for location in locations_ls:
            try:
                location_ids.append(int(location))
            except ValueError:
                await intr.response.send_message(f'District ID {md.b(f"{location}")} is not a valid district ID.')
                return

        self.db.remove_channel_districts(channel.id, location_ids)
        await intr.response.send_message('Successfully removed all IDs')

    @location_group.command(name='clear', description='Clear all registered locations (get alerts on all locations)')
    async def location_clear(self, intr: discord.Interaction, confirmation: str = None):

        if not await self.has_permission(intr):
            await intr.response.send_message('Error: You are missing the Manage Channels permission.')
            return

        channel = self.get_matching_channel(intr)
        if channel is None:
            await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
            return

        conf_str = intr.user.name

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

    @location_group.command(name='registered',
                            description='List all locations registered to this channel, by IDs and names. Sorted alphabetically')
    @app_commands.describe(search='Search tokens, separated by spaces')
    async def location_registered(self, intr: discord.Interaction, search: str | None = None, page: int = 1):

        channel = self.get_matching_channel(intr)
        if channel is None:
            await intr.response.send_message('Could not find this channel. Are you sure it is registered?')
            return

        if search is None:
            search_results = [dist.to_tuple() for dist in
                              self.db.district_ids_to_districts(*self.db.get_channel_district_ids(channel.id))]
        else:
            search_results = [dist.to_tuple() for dist in
                              self.db.search_channel_districts(channel.id, *re.split(r"\s+", search))]

        districts = sorted(search_results, key=lambda tup: tup[1])

        page = self.locations_page(districts, page - 1)

        if len(page) > 2000:
            await intr.response.send_message(
                'Page content exceeds character limit.\nPlease contact the bot authors with the command you\'ve tried to run.')
            return

        await intr.response.send_message(page)


async def setup(bot: commands.Bot):
    global cog
    cog = await COG_Commands.setup(bot)


async def teardown(bot: commands.Bot):
    cog.check_for_updates.cancel()
