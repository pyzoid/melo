from discord.ext.commands import Cog
from discord.ext.commands import command
from discord.ext import commands
import discord
import youtube_dl
import asyncio
import functools
from discord.utils import get
import random
import itertools
from async_timeout import timeout
from lib.menu import PlayerMenu
from lib.music.source import YTDLSource, YTDLError
#inspired heavily by https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

from lib.music.player import PlayerContext, Song

class Music(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.player_contexts = {}

    def get_player_context(self, ctx: commands.Context, reset=False):
        context = self.player_contexts.get(ctx.guild.id)
        if not context or reset:
            context = PlayerContext(ctx, self.bot)#VoiceState(self.bot, ctx)
            self.player_contexts[ctx.guild.id] = context
        
        #if state.stale:
        #    state.revive()
        return context

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.player_context = self.get_player_context(ctx)
        
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3]) 

    @command(name="play")
    async def _play(self, ctx, *, query):
        if not hasattr(ctx, "voice_state"):
            ctx.player_context = self.get_player_context(ctx)

        channel = None
        try:
            channel = ctx.message.author.voice.channel
        except:
            pass

        if not channel:
            await ctx.send("You must join a voice channel first")
            return

        if ctx.player_context.player:
            if ctx.player_context.is_stale:
                ctx.player_context = self.get_player_context(ctx, reset=True)
                if not ctx.player_context.player:
                    ctx.player_context.player = await channel.connect() 
                if not ctx.player_context.player.voice.is_connected():
                    ctx._player_context.player = get(ctx.bot.voice_clients, guild=ctx.guild)
            else:
                await ctx.player_context.player.voice.move_to(channel)
        else:
            ctx.player_context.player = await channel.connect() 

        try:
            source = await YTDLSource.create_source(ctx, query, loop=self.bot.loop)
        except YTDLError as e:
            await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
        else:
            song = Song(source)

            await ctx.player_context.play(song)

            await ctx.message.delete()
        
    
    @commands.command(name="pause")
    async def _pause(self, ctx: commands.Context):
        
        if ctx.player_context.is_playing:
            ctx.player_context.player.pause()
            await ctx.send("Paused")
    
    @commands.command(name="resume")
    async def _resume(self, ctx: commands.Context):
        
        if not ctx.player_context.is_playing:
            ctx.player_context.player.resume()
            await ctx.send("Resumed")
    
    @commands.command(name='stop')
    async def _stop(self, ctx: commands.Context):
        
        if ctx.player_context.player:
            ctx.player_context.stop()

    @commands.command(name="skip")
    async def _skip(self, ctx: commands.Context):

        if ctx.player_context.current:
            ctx.player_context.skip()
    @commands.command(name='restart')
    async def _restart(self, ctx: commands.Context):
        
        #if not ctx.voice_state:
        #    return

        ctx.player_context.player.stop()

        ctx.player_context = self.get_player_context(ctx, reset=True)

        await ctx.send("PlayerContext succesfully reset")

    @commands.command(name='volume')
    async def _volume(self, ctx: commands.Context, * ,volume: int):

        if not ctx.player_context.player:
            return await ctx.send("No player instance to set volume for")

        if 0 > volume > 100:
            return await ctx.send("Volume must be between 0 and 100")
        
        ctx.player_context.player.volume = volume / 100

        await ctx.send('Volume of the player set to {}%'.format(volume))

    @commands.command(name='playing')
    async def _playing(self, ctx: commands.Context):
        embed = ctx.voice_state.current.create_embed()
        await ctx.send(embed=embed)

    @commands.command(name="_play_pause", hidden=True)
    async def _play_pause(self, ctx: commands.Context):
        if ctx.player_context.is_playing:
            ctx.player_context.player.pause()
        else:
            ctx.player_context.player.resume()
        
def setup(bot):
    bot.add_cog(Music(bot))