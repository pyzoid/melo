from discord.ext import menus
from discord.ext.menus.views import ViewMenu
import discord
import asyncio


class PlayerMenu(ViewMenu):
    def __init__(self, bot, timeout=10.0, message=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.dead = asyncio.Event()
        self.author_only = False
        if message:
            self.message = message


    async def send_initial_message(self, ctx, channel, song_embed=None):
        self.message = await self.send_with_view(channel, embed=song_embed)

    @classmethod
    async def construct_from_existing(cls, message, bot, timeout=10):
        return cls(bot, timeout, message)

    @menus.button('⏯️')
    async def on_pause_resume(self, interaction):
        await self.ctx.invoke(self.bot.get_command("_play_pause"))

    @menus.button('\N{BLACK RIGHTWARDS ARROW}')
    async def on_skip(self, interaction):
        #await interaction.followup.send("Song Skipped", ephemeral=True)
        #await interaction.defer(ephemeral=False)
        await self.ctx.invoke(self.bot.get_command('skip'))

    @menus.button('\N{BLACK SQUARE FOR STOP}\ufe0f')
    async def on_stop(self, interaction):
        #await interaction.defer(ephemeral=False)
        await self.ctx.invoke(self.bot.get_command('stop'))

    def context(self, state):
        self._player_state = state

    async def finalize(self, timed_out):
        self.stop()
        self.dead.set()

    
    