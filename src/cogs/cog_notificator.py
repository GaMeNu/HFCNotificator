import asyncio
import sys
from typing import Any

import db_access as db_access
import discord
import requests
from db_access import *
from discord import app_commands, VoiceChannel, StageChannel, ForumChannel, CategoryChannel
from discord.abc import PrivateChannel
from discord.ext import commands, tasks
from log_utils import errlogging, loggers
from utils.alert_maker import AlertEmbed, AlertEmbedFactory, DistrictsEmbed, Alert
from utils.alert_reqs import AlertReqs

load_dotenv()
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))
EXPECTED_LOOP_DELTA_MIN = 0.8
EXPECTED_LOOP_DELTA_MAX = 1.2

COG_CLASS = "COG_Notificator"

cog: Any

# 2023-10-26 I have decided to start documenting the project.


class AlertEmbeds:
    """
    This is a container class for all embeds that need to be sent in an alert
    """
    def __init__(self, start_embed: discord.Embed, district_embeds: list[DistrictsEmbed], end_embed: discord.Embed):
        self.start_embed = start_embed
        self.district_embeds = district_embeds
        self.end_embed = end_embed


# noinspection PyUnresolvedReferences
class COG_Notificator(commands.Cog):
    """
    This cog handles the HFC update loop,
    monitoring new alerts
    """

    districts: list[dict] = json.loads(requests.get('https://www.oref.org.il/districts/districts_heb.json').text)

    def __init__(self, bot: commands.Bot):
        """
        Create the Cog
        :param bot: Discord commands bot client
        :param handler: Logging handler
        """

        # Set up log_utils
        self.log = logging.Logger(COG_CLASS)

        handler = logging.StreamHandler()
        handler.setFormatter(loggers.ColorFormatter())
        self.log.addHandler(handler)
        self.log.addHandler(loggers.DefaultFileHandler("LOG_ALL.log"))

        self.log.info(f'Initializing {COG_CLASS}...')

        # Set up client and db
        self.bot = bot
        self.db = DBAccess()
        self.alert_reqs = AlertReqs()

        # set up internal vars
        self.district_timeouts: dict[str, dict[int, int]] = {}

        self.loop_count_checker = 0
        self.last_loop_run_time = time.time() - 1  # Verify first iteration goes by smoothly

        # begin check task
        if not self.check_for_updates.is_running():
            self.check_for_updates.start()

        self.has_connection = True

        self.start_time = time.time()

        self.log.info(f'{COG_CLASS} is now initialized')

    @staticmethod
    async def setup(bot: commands.Bot):
        """
        Set up the cog
        :param bot: commands.Bot client
        :return: the cog instance that was created and added to the bot
        """

        if bot.get_cog(COG_CLASS) is not None:
            return None

        _cog = COG_Notificator(bot)
        await bot.add_cog(_cog)
        return _cog

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Start API update task when ready
        """
        if self.check_for_updates.is_running():
            return
        self.check_for_updates.start()

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

    async def _decrement_districts_timeouts(self):
        for dist_name in self.district_timeouts.copy().keys():
            for cat in self.district_timeouts[dist_name].copy().keys():
                self.district_timeouts[dist_name][cat] -= 1
                if self.district_timeouts[dist_name][cat] <= 0:
                    self.district_timeouts[dist_name].pop(cat, None)
                    self.log.debug(f'Popped district category {dist_name}:{cat}')

            # I like <= over ==, due to a (probably unreasonable) fear that something might go wrong, and it would get decremented twice
            if len(self.district_timeouts[dist_name]) == 0:
                self.district_timeouts.pop(dist_name, None)
                self.log.debug(f'Popped district {dist_name}')

    @tasks.loop(seconds=1, reconnect=False)
    async def check_for_updates(self):
        # Check if the loop is running multiple too fast or too slow
        current_time = time.time()
        delta = round(current_time - self.last_loop_run_time, 3)

        if delta < EXPECTED_LOOP_DELTA_MIN:
            self.log.warning(f'Loop is running too quickly! Expected delta > {EXPECTED_LOOP_DELTA_MIN}s, but got {delta}s. Restarting...')
            self.check_for_updates.stop()
            return

        if delta > EXPECTED_LOOP_DELTA_MAX:
            self.log.warning(f'Loop is running too slowly! Expected delta < {EXPECTED_LOOP_DELTA_MAX}s, but got {delta}s instead. Do you have enough resources?')

        self.last_loop_run_time = current_time

        # Check if the loop is running multiple times
        if self.loop_count_checker >= 1:
            # This might cause the loop to still "run" multiple times in the background
            # But it should prevent it from at least sending multiple messages
            # (and perhaps speedrun through the queue, if that's the case)
            self.loop_count_checker -= 1
            return

        # Increment the loop checker
        self.loop_count_checker += 1

        try:
            # Get the newest alert
            current_alert: dict | None = self.alert_reqs.request_alert_json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # handle connection issues
            self.log.warning("Lost connection!")
            current_alert = await self.handle_connection_failure()

        self.log.debug(f'Alert response: {current_alert}')

        # Decrement all districts' cooldowns.
        await self._decrement_districts_timeouts()

        # If the current alert is None, it means there was an error retrieving the data
        if current_alert is None:
            self.log.warning('Error while getting current alert data')
            return

        # Decrement the loop checker
        self.loop_count_checker -= 1

        # We have some data! Better go handle that lol
        if len(current_alert) > 0:
            await self.handle_alert_data(current_alert)

    async def handle_connection_failure(self):
        """
        Attempt getting a new alert data, until connection is restored
        """
        while True:
            # Wait more time, because we're already effed anyway and there's no point spamming
            await asyncio.sleep(5)
            try:
                self.log.info("Attempting reconnection: ")
                alert = self.alert_reqs.request_alert_json()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                self.log.info("Failed to reconnect.")
            else:
                return alert

    @check_for_updates.after_loop
    async def after_update_loop(self):
        # Attempt to force stupid "Unread Result" down its own throat
        # and just reset the connection.
        # I'm not dealing with Unread Results
        self.db.connection.close()
        self.db = DBAccess()
        self.start_loop()

    def start_loop(self):
        self.db = DBAccess()
        self.check_for_updates.restart()

    @check_for_updates.error
    async def update_loop_error(self, err: Exception):
        self.log.warning(f"Update loop errored: {err}")
        errlogging.new_errlog(err)

        errlogging.new_errlog(sys.exc_info()[1])
        if isinstance(err, requests.exceptions.Timeout):
            while True:
                self.log.info(f'Attempting reconnect...')
                await asyncio.sleep(2)
                try:
                    self.alert_reqs.request_alert_json()
                except requests.exceptions.Timeout as error:
                    self.log.error(f'Request timed out: {error}')
                except requests.exceptions.ConnectionError as error:
                    self.log.error(f'Request failed: {error}')
                else:
                    self.log.info(f'Back online!')
                    break

        self.check_for_updates.cancel()

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

    async def handle_alert_data(self, current_alert: dict):

        # Code for testing nationwide alert
        if current_alert["data"][0] == '*':
            current_alert["data"] = [tup[1] for tup in self.db.get_all_districts()]

        active_districts: list[str] = current_alert["data"]
        new_districts: list[str] = []

        alert_cat = current_alert.get("cat")

        # Gather only the new districts, and reset all district cooldowns
        for district_name in active_districts:

            # Gather new district to new_districts list
            if district_name not in self.district_timeouts.keys():
                new_districts.append(district_name)
            elif alert_cat not in self.district_timeouts.get(district_name):
                new_districts.append(district_name)

            # Set district timeout to 60s, whether new or not
            if self.district_timeouts.get(district_name, None) is None:
                self.district_timeouts[district_name] = {}

            self.district_timeouts[district_name][alert_cat] = 60

        if len(new_districts) == 0:
            return

        new_districts_tup = tuple(new_districts)

        try:
            # We have picked out the new districts. Send out alerts.
            await self.send_new_alert(current_alert, new_districts_tup)
        except Exception as e:
            self.log.error(f'Could not send message!\nError info: {e.__str__()}')

    @errlogging.async_errlog
    async def send_new_alert(self, alert_data: dict, new_districts: tuple[str, ...]):
        """
        Push an alert to all registered channels
        :param alert_data: Alert data dict (see test_alert for format)
        :param new_districts: Currently active districts (districts that were not already active)
        :return:
        """

        if new_districts[0] == '*':
            new_districts = tuple(dist[1] for dist in self.db.get_all_districts())

        self.log.info(f'Sending alerts to channels')

        alert = Alert.from_dict(alert_data)

        # generate primary alert_embed
        alert_embed = AlertEmbedFactory.make_alert_embed(alert)
        end_alert_embed = AlertEmbedFactory.make_alert_embed(alert)
        end_alert_embed.description = "סוף רשימת מקומות להתראה.\n**הערה:** הטמעה זו נשלחת רק כאשר נשלחו לפחות 2 הטמעות של \"מקומות התתראה\"."

        # get all new districts' data
        # TODO: This can probably even be done as an external cache, reducing load whenever an alert is sent
        dists = self.db.get_area_districts_by_name(new_districts)

        # Make districts gettable by ID instead of by name for quick lookup
        # TODO: This can probably even be done as an external cache, reducing load whenever an alert is sent
        dists_by_id = {}
        for dist_name, dist in dists.items():
            # prepare dists by ID
            dists_by_id[dist.district_id] = dist

        # Get all registered channels and prep them for sending
        for channel_tup in self.db.get_all_channels():
            # Convert from DB channel to sendable channel
            channel = Channel.from_tuple(channel_tup)
            dc_ch = self.get_sendable_channel(channel)

            # Filter the channel's locations
            filtered_locations = await self._filter_channel_locations(new_districts, dists, dists_by_id, channel)

            # No alerts shall be sent in this channel
            if len(filtered_locations) == 0:
                continue

            # Send alert embed to minimize messages even more
            # and to allow for mobile/overlay notifs
            if len(filtered_locations) <= 8:
                result_embed = AlertEmbedFactory.make_unified_embed(alert, filtered_locations)

                # relay to a secondary thread and start prepping the next channel
                asyncio.create_task(self.send_unified_embed_to_channel(alert, dc_ch, result_embed))

                # prep next channel
                continue

            # Make all districts' embeds, now that we know we're going to have to send a locations embed
            district_embeds: list[DistrictsEmbed] = AlertEmbedFactory.make_districts_embed(alert, filtered_locations)

            # place in container object
            embeds = AlertEmbeds(alert_embed, district_embeds, end_alert_embed)

            # relay to a secondary thread and start prepping the next channel
            asyncio.create_task(self.send_to_one_channel(alert, dc_ch, embeds))

    @staticmethod
    async def _filter_channel_locations(
            new_districts: tuple[str, ...],
            dists: dict[str, AreaDistrict],
            dists_by_id: dict[int, AreaDistrict],
            channel: Channel
    ) -> list[AreaDistrict | str]:
        """
        Filters the locations associated with a given channel based on the provided districts.

        :param new_districts: A tuple of strings representing all new districts.
        :param dists: A mapping of district names to AreaDistrict objects.
        :param dists_by_id: A mapping of district IDs to AreaDistrict objects.
        :param channel: The channel to filter for

        :returns: A list of filtered locations with either the AreaDistrict objects or strings.
        """
        # Check if the channel has a locations filter
        if len(channel.locations) == 0:
            # Filtered locations is basically all active locations
            filtered_locations: list[AreaDistrict | str] = []
            for dist in new_districts:
                dist = dists.get(dist, dist)
                filtered_locations.append(dist)
        else:
            # prepare only registered locations
            # (while minimizing queries to the DB)
            filtered_locations = []
            for loc in channel.locations:
                dist = dists_by_id.get(loc)
                if dist is not None:  # Because if the dist is not in the new dists, it'll be None
                    filtered_locations.append(dist)
        return filtered_locations

    def get_sendable_channel(self, channel: Channel):
        """
        Takes in a database Channel object and converts it to a Discord sendable channel object
        The result Discord channel is either a type of server channel, or a user.
        """
        dc_ch: VoiceChannel | StageChannel | ForumChannel | CategoryChannel | Thread | PrivateChannel | User | None
        if channel.server_id is not None:
            dc_ch = self.bot.get_channel(channel.id)
        else:
            dc_ch = self.bot.get_user(channel.id)
        return dc_ch

    async def send_unified_embed_to_channel(self, alert: Alert, dc_ch, embed: DistrictsEmbed):
        try:
            content = self.format_districts_content(alert, embed)
            await dc_ch.send(content=content, embed=embed.embed)
        except Exception as e:
            if isinstance(dc_ch, discord.User):
                self.log.warning(f'Could not send (unified) alert to user @{dc_ch.name}.\nError info: {e}')
            else:
                self.log.warning(f'Could not send alert to channel #{dc_ch.name}@{dc_ch.guild}.\nError info: {e}')
            errlogging.new_errlog(e)
        else:
            self.log.info(f"Finished channel {dc_ch.name}")

    async def send_to_one_channel(self, alert: Alert, dc_ch, embeds: AlertEmbeds):
        alert_embed = embeds.start_embed
        district_embeds = embeds.district_embeds
        end_alert_embed = embeds.end_embed

        try:
            await dc_ch.send(embed=alert_embed)
            for dists_emb in district_embeds:
                content = self.format_districts_content(alert, dists_emb)
                await dc_ch.send(content=content, embed=dists_emb.embed)
                await asyncio.sleep(0.02)
            if len(district_embeds) >= 2:
                await dc_ch.send(embed=end_alert_embed)
        except Exception as e:
            if isinstance(dc_ch, discord.User):
                self.log.warning(f'Could not send alert to user @{dc_ch.name}.\nError info: {e}')
            else:
                self.log.warning(f'Could not send alert to channel #{dc_ch.name}@{dc_ch.guild}.\nError info: {e}')
            errlogging.new_errlog(e)
        else:
            self.log.info(f"Finished channel {dc_ch.name}")

    @staticmethod
    def format_districts_content(alert: Alert, dists_emb: DistrictsEmbed):
        """
        This method formats the districts content that shall be sent alongside the embed
        """
        districts_content_fmt = ", ".join(dists_emb.districts)
        content = f"**{alert.title}** | {districts_content_fmt}"
        return content

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

        if override:
            await self.send_new_alert(alert_data, tuple(districts_ls))
        else:
            await self.handle_alert_data(alert_data)


async def setup(bot: commands.Bot):
    global cog
    cog = await COG_Notificator.setup(bot)


async def teardown(bot: commands.Bot):
    cog.check_for_updates.cancel()
