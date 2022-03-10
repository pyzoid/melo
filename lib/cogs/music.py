from disnake.ext.commands import Cog
from disnake.ext.commands import command, slash_command
from disnake.ext import commands
import disnake
import youtube_dl
import pomice
import json
from disnake.utils import get
import sys
from lib.util.decorators import player_slash_command
from lib.music.source import YTDLSource, YTDLError

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''
msg_delete_time = 3

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

        if self.pomice.nodes:
            return
        
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

        
        print("Node connected")


    @commands.Cog.listener()
    async def on_pomice_track_end(self, player, track, _):
        player_context = self.player_contexts.get(player.guild.id)
        player_context._playback_finished()

    def get_player_context(self, interaction: disnake.CommandInteraction, reset=False):
        context = self.player_contexts.get(interaction.guild.id)
        if not context or reset:
            context = PlayerContext(interaction ,self.bot, self.lava, self.node)
            self.player_contexts[interaction.guild.id] = context

        return context

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.player_context = self.get_player_context(ctx)
        
    @Cog.listener()
    async def on_ready(self):
        if self.lava:
            await self.start_nodes()
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3].split("\\")[-1]) 

    @slash_command(name="stats") 
    async def _stats(self, ctx):
        stats = self.pomice.get_node(identifier="MAIN").stats
        await ctx.send(embed=(disnake.Embed(title="Node Stats", color=disnake.Color.dark_red()))
        .add_field(name="CPU_CORES", value=stats.cpu_cores, inline=True)
        .add_field(name="CPU_PROCESS_LOAD", value=stats.cpu_process_load, inline=True)
        .add_field(name="ACTIVE_PLAYERS", value=stats.players_active, inline=True)
        .add_field(name="TOTAL_PLAYERS", value=stats.players_total,inline=True))

    @player_slash_command(guild_ids=[678809641597140992],name="play")
    async def _play(self, interaction: disnake.CommandInteraction, query):
        player_context = interaction.player_context

        building = not player_context._player_window

        if building:
            await interaction.response.send_message("Building Player...", delete_after=10)

        channel = None
        try:
            channel = interaction.author.voice.channel
        except:
            pass

        if not channel:
            await interaction.send("You must join a voice channel first",delete_after=msg_delete_time)
            return

        if player_context.player:
            await interaction.send("Song added to queue", delete_after=msg_delete_time)
            if player_context.is_stale:
                player_context = self.get_player_context(interaction, reset=True)
                if not player_context.player:
                    if player_context.lava_enabled:
                        player_context.player = await channel.connect(cls=pomice.player.Player) 
                    else:
                        player_context.player = await channel.connect() 

                if not player_context.player.voice.is_connected:
                    player_context.player = get(interaction.bot.voice_clients, guild=interaction.guild)
        else:
            if interaction.guild.voice_client:
                if interaction.guild.voice_client.is_connected:
                    player_context.player = interaction.voice_client

            if player_context.lava_enabled:
                player_context.player = await channel.connect(cls=pomice.player.Player) 
            else:
                player_context.player = await channel.connect() 

        try:
            if player_context.lava_enabled:
                source = await player_context.player.voice.get_tracks(query, ctx=interaction)
                if isinstance(source, pomice.Playlist):
                    source = source.tracks
                else:
                    source = (await player_context.player.voice.get_tracks(query, ctx=interaction))[0]
            else:
                source = await YTDLSource.create_source(interaction, query, loop=self.bot.loop)
        except YTDLError as e:
            await interaction.send('An error occurred while processing this request: {}'.format(str(e)),delete_after=msg_delete_time)
        else:
            
            await player_context.play(source)
        
        if building:
            await interaction.delete_original_message()
        
    
        
    
    @player_slash_command(guild_ids=[678809641597140992],name="pause")
    async def _pause(self, interaction: disnake.CommandInteraction):

        if interaction.player_context.is_playing:
            await interaction.player_context.player.pause()
            await interaction.send("Player Paused", delete_after=msg_delete_time)
    
    @player_slash_command(guild_ids=[678809641597140992],name="resume")
    async def _resume(self, interaction: disnake.CommandInteraction):

        if not interaction.player_context.is_playing:
            await interaction.player_context.player.resume()
            await interaction.send("Player Resumed", delete_after=msg_delete_time)
    
    @player_slash_command(guild_ids=[678809641597140992],name="stop")
    async def _stop(self, interaction: disnake.CommandInteraction):

        if interaction.player_context.player:
            await interaction.player_context.stop()
            await interaction.send("Player Stopped", delete_after=msg_delete_time)

    @player_slash_command(guild_ids=[678809641597140992],name="skip")
    async def _skip(self, interaction: disnake.CommandInteraction):

        if interaction.player_context.current:
            interaction.player_context.current_loop = None
            await interaction.player_context.skip()
            await empty_response(interaction)

    @player_slash_command(guild_ids=[678809641597140992],name="shuffle")
    async def _shuffle(self, interaction: disnake.CommandInteraction):

        if not interaction.player_context.queue.empty():
            interaction.player_context.queue.shuffle()
            await empty_response(interaction)


    @player_slash_command(guild_ids=[678809641597140992],name="restart")
    async def _restart(self, interaction: disnake.CommandInteraction):
        await interaction.player_context.player.stop()

        self.get_player_context(interaction, reset=True)

        await interaction.send("Player Context reset", ephemeral=True)

    @player_slash_command(guild_ids=[678809641597140992],name="volume")
    async def _volume(self, interaction: disnake.CommandInteraction, * ,volume: int):

        if not interaction.player_context.player:
            return await interaction.send("No player instance to set volume for", delete_after=msg_delete_time)
        
        if 0 <= volume >= 251:
            return await interaction.send("Volume must be between 0 and 250",delete_after=msg_delete_time)
        await interaction.player_context.player.volume(volume)

        await interaction.send('Volume of the player set to {}%'.format(volume),delete_after=msg_delete_time)

    @player_slash_command(guild_ids=[678809641597140992],name="playing")
    async def _playing(self, interaction: disnake.CommandInteraction):
        embed = interaction.player_context.current.create_embed()
        await interaction.send(embed=embed)

    @player_slash_command(guild_ids=[678809641597140992],name="loop")
    async def _loop(self, interaction: disnake.CommandInteraction):
        player_context = interaction.player_context

        if not player_context.current:
            return 

        player_context.current_loop = None if player_context.current_loop else player_context.current

        await empty_response(interaction)


    @player_slash_command(guild_ids=[678809641597140992],name="seek")
    async def _seek(self, interaction: disnake.CommandInteraction, pos: float):
        if pos < 0:
            return
        if pos > interaction.player_context.current.track.raw_duration:
            return await interaction.send("Cannot seek past song length", delete_after=msg_delete_time)
        await interaction.player_context.player.seek(pos*1000)

        await interaction.send(f"Player Seeked: {pos} seconds", delete_after=msg_delete_time)


    
    @commands.command(name="_play_pause", hidden=True)
    async def _play_pause(self, ctx: commands.Context):
        player_context = self.get_player_context(ctx)

        if player_context.is_playing:
            await player_context.player.pause()
        else:
            await player_context.player.resume()

def empty_response(interaction):
    return interaction.send("‎", delete_after=sys.float_info.min)

def setup(bot):
    bot.add_cog(Music(bot))