from discord.ext.commands import Cog
from discord.ext.commands import command
from discord.ext import commands
import discord
import youtube_dl
import pomice
import json
from discord.utils import get
from lib.music.source import YTDLSource, YTDLError

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

from lib.music.player import PlayerContext, Song

class Music(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.player_contexts = {}
        self.lava = True
        self.pomice = pomice.NodePool()
        self.node = None

        
    def load_config(self, filename):
        with open(filename, "r") as f:
            return json.load(f)  
    
    async def start_nodes(self):    
        config = self.load_config("lib/bot/lavanode.json")
         
        await self.bot.wait_until_ready()
        print("Connecting to lavalink node...")
        try:
            self.node = self.pomice.get_best_node(algorithm=pomice.NodeAlgorithm.by_ping)
        except pomice.NoNodesAvailable:
            print("No node found, creating one now...")

            try:
                self.node = await self.pomice.create_node(
                    bot=self.bot,
                    host=config.get("ip"),
                    port=config.get("port"),
                    password=config.get("password"),
                    identifier="MAIN"
                    )
            except Exception as ex:
                print(f"Failed to connect to lavalink node: {repr(ex)}, Using basic player instead")
                self.lava = False
                return
            else:
                print("Node created")

        else:
            await self.node.connect()
        
        print("Node connected")


    @commands.Cog.listener()
    async def on_pomice_track_end(self, player, track, _):
        player_context = self.player_contexts.get(player.guild.id)
        player_context._playback_finished()

    def get_player_context(self, ctx: commands.Context, reset=False):
        context = self.player_contexts.get(ctx.guild.id)
        if not context or reset:
            context = PlayerContext(ctx, self.bot, self.lava, self.node)
            self.player_contexts[ctx.guild.id] = context

        return context

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.player_context = self.get_player_context(ctx)
        
    @Cog.listener()
    async def on_ready(self):
        await self.start_nodes()
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3].split("\\")[-1]) 

    @command(name="stats") 
    async def _stats(self, ctx):
        stats = self.pomice.get_node(identifier="MAIN").stats
        await ctx.send(embed=(discord.Embed(title="Node Stats", color=discord.Color.dark_red()))
        .add_field(name="CPU_CORES", value=stats.cpu_cores, inline=True)
        .add_field(name="CPU_PROCESS_LOAD", value=stats.cpu_process_load, inline=True)
        .add_field(name="ACTIVE_PLAYERS", value=stats.players_active, inline=True)
        .add_field(name="TOTAL_PLAYERS", value=stats.players_total,inline=True))


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
                    if ctx.player_context.lava_enabled:
                        ctx.player_context.player = await channel.connect(cls=pomice.player.Player) 
                    else:
                        ctx.player_context.player = await channel.connect() 

                if not ctx.player_context.player.voice.is_connected:
                    ctx.player_context.player = get(ctx.bot.voice_clients, guild=ctx.guild)
        else:
            if ctx.voice_client:
                if ctx.voice_client.is_connected:
                    ctx.player_context.player = ctx.voice_client

            if ctx.player_context.lava_enabled:
                ctx.player_context.player = await channel.connect(cls=pomice.player.Player) 
            else:
                ctx.player_context.player = await channel.connect() 

        try:
            if ctx.player_context.lava_enabled:
                source = await ctx.player_context.player.voice.get_tracks(query, ctx=ctx)
                if isinstance(source, pomice.Playlist):
                    source = source.tracks
                else:
                    source = (await ctx.player_context.player.voice.get_tracks(query, ctx=ctx))[0]
            else:
                source = await YTDLSource.create_source(ctx, query, loop=self.bot.loop)
        except YTDLError as e:
            await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
        else:
            
            await ctx.player_context.play(source)

            await ctx.message.delete()
        
    
    @commands.command(name="pause")
    async def _pause(self, ctx: commands.Context):
        
        if ctx.player_context.is_playing:
            await ctx.player_context.player.pause()
            await ctx.send("Paused")
    
    @commands.command(name="resume")
    async def _resume(self, ctx: commands.Context):
        
        if not ctx.player_context.is_playing:
            await ctx.player_context.player.resume()
            await ctx.send("Resumed")
    
    @commands.command(name='stop')
    async def _stop(self, ctx: commands.Context):
        
        if ctx.player_context.player:
            await ctx.player_context.stop()

    @commands.command(name="skip")
    async def _skip(self, ctx: commands.Context):

        if ctx.player_context.current:
            await ctx.player_context.skip()
    @commands.command(name='restart')
    async def _restart(self, ctx: commands.Context):

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
        embed = ctx.player_context.current.create_embed()
        await ctx.send(embed=embed)

    @commands.command(name="_play_pause", hidden=True)
    async def _play_pause(self, ctx: commands.Context):
        if ctx.player_context.is_playing:
            await ctx.player_context.player.pause()
        else:
            await ctx.player_context.player.resume()

def setup(bot):
    bot.add_cog(Music(bot))