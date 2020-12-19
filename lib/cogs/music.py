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

#inspired heavily by https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
    }

    ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }   
    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    def __init__(self, ctx:commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume=0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')


    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.ffmpeg_options), data=info)

class Song:
    __slots__ = ('source', 'requester') #more mem efficent and faster than __dict__

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]

class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx
        self.current = None
        self.voice = None
        self.dead = False
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()
        self.audio_player = bot.loop.create_task(self.audio_player_task())
    
    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        if self.voice:
            return self.voice.is_playing()
        else:
            return False

    async def audio_player_task(self):
        while 1:
            self.next.clear()
            self.current = None
            if not self.loop:
                #waits 3 mins for new song, else disconnects
                try:
                    async with timeout(180):
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.dead = True
                    return
            
            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after=self.play_next_song)
            await self.current.source.channel.send(f"Now Playing {self.current.source.title}")

            await self.next.wait()
    
    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None

class Music(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state or state.dead:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state
        
        return state

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3]) 

    @command(name="play")
    async def _play(self, ctx, *, query):
        channel = None
        try:
            channel = ctx.message.author.voice.channel
        except:
            pass

        if not channel:
            await ctx.send("You must join a voice channel first")
            return

        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(channel)
        else:
            ctx.voice_state.voice = await channel.connect() 

        try:
            source = await YTDLSource.create_source(ctx, query, loop=self.bot.loop)
        except YTDLError as e:
            await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
        else:
            song = Song(source)

            await ctx.voice_state.songs.put(song)
            await ctx.send("Added to queue")
    
    @commands.command(name="pause")
    async def _pause(self, ctx: commands.Context):
        
        if ctx.voice_state.is_playing and ctx.voice_state.voice:
            ctx.voice_state.voice.pause()
            await ctx.send("Paused")
    
    @commands.command(name="resume")
    async def _resume(self, ctx: commands.Context):
        
        if not ctx.voice_state.is_playing and ctx.voice_state.voice:
            ctx.voice_state.voice.resume()
            await ctx.send("Resumed")
    
    @commands.command(name='stop')
    async def _stop(self, ctx: commands.Context):

        ctx.voice_state.songs.clear()

        if ctx.voice_state.current:
            ctx.voice_state.voice.stop()

def setup(bot):
    bot.add_cog(Music(bot))