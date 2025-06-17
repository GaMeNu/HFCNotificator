import sys
from typing import Any

import discord
import requests
from discord.ext import commands, tasks
from discord import app_commands

import src.db_access as db_access
from src.utils.alert_reqs import AlertReqs
from src.logging import errlogging, loggers
from src.utils.alert_maker import AlertEmbed
from src.db_access import *
from src.utils.markdown import md

load_dotenv()
AUTHOR_ID = int(os.getenv('AUTHOR_ID'))
EXPECTED_LOOP_DELTA_MIN = 0.8
EXPECTED_LOOP_DELTA_MAX = 1.2

COG_CLASS = "COG_Notificator"

cog: Any

# 2023-10-26 I have decided to start documenting the project.


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

        # Set up logging
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
        self.district_timeouts = {}

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
            self.district_timeouts[dist_name] -= 1
            # I like <= over ==, due to a (probably unreasonable) fear that something might go wrong, and it would get decremented twice
            if self.district_timeouts[dist_name] <= 0:
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

    async def handle_alert_data(self, current_alert: dict):

        active_districts: list[str] = current_alert["data"]
        new_districts: list[str] = []

        # Gather only the new districts, and reset all district cooldowns
        for district_name in active_districts:

            # Gather new district to new_districts list
            if district_name not in self.district_timeouts.keys():
                new_districts.append(district_name)

            # Set district timeout to 60s, whether new or not
            self.district_timeouts[district_name] = 60

        if len(new_districts) == 0:
            return

        try:
            # We have picked out the new districts. Send out alerts.
            await self.send_new_alert(current_alert, new_districts)
        except Exception as e:
            self.log.error(f'Could not send message!\nError info: {e.__str__()}')

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


async def setup(bot: commands.Bot):
    global cog
    cog = await COG_Notificator.setup(bot)


async def teardown(bot: commands.Bot):
    cog.check_for_updates.cancel()
