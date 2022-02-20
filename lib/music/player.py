from abc import ABC, abstractmethod
from lib.menu import PlayerMenu
from lib.music.source import YTDLSource
from lib.util.asynctools import await_me_maybe
import asyncio
from contextlib import suppress
import pomice
from enum import Enum
import random
import itertools
import discord

class VoiceError(Exception):
    pass

class PlayerState(Enum):
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    WAITING = 3
    STALE = 4

class PlayerWindowState(Enum):
    NOT_CREATED=0
    ACTIVE=1
    STALE=2

class PlayerContext():
    TIMEOUT = 60

    def __init__(self, ctx, bot, lava_enabled=False):
        self._ctx = ctx
        self._bot = bot
        self.loop = bot.loop
        self.queue = SongQueue()
        self._next = asyncio.Event() #syncs player and player window
        
        self._run_player_task = None
        self._run_lock = asyncio.Lock()

        self._player = None
        self._player_window = None
        self.current = None

        self._song_skipped = False

        self.lava_enabled = lava_enabled

    @property
    def player(self):
        return self._player

    @property
    def is_stale(self):
        return self._player.state == PlayerState.STALE or self._player_window.state == PlayerWindowState.STALE

    async def skip(self):
        if self.current:
            self.current = None
            await self._player.skip()
            
    async def stop(self): 
        self.current = None
        self.queue.clear()
        await self._player.stop()

    async def play(self, source):
        song = Song(LavaSourceAdapter(source) if self.lava_enabled else YTDLSourceAdapter(source))
        await self.queue.put(song)

        if not self._run_player_task:
            self._player.state = PlayerState.WAITING
            self._run_player_task = self.loop.create_task(self._run())

    def _playback_finished(self, error=None):

        self.current = None

        if error:
            raise VoiceError(str(error))

        self._next.set()

    async def _run(self):
        async with self._run_lock:
            while 1:
                song = None if self.queue.empty() else await self.queue.get()
                    
                self.current = song

                self.loop.create_task(self._player.play_track(song, self._playback_finished if not self.lava_enabled else None))
                self.loop.create_task(self._player_window.player_window(song, PlayerContext.TIMEOUT))
                try:
                    if song:
                        await asyncio.wait_for(self._next.wait(), song.track.raw_duration)
                    else:
                        await asyncio.wait_for(self.queue.item_available(), PlayerContext.TIMEOUT)
                except asyncio.TimeoutError:
                    print("playercontext timeout")
                    await self._player.stale()
                    await self._player_window.stale()
                    break
                else:
                    if song:
                        print(f"Finished playing {song.track.title}")
                finally:
                    self._next.clear()


    @property
    def is_playing(self):
        if self._player:
            return self._player.state == PlayerState.PLAYING

    @property
    def player(self):
        return self._player
    
    @player.setter
    def player(self, voice_client):
        self._player = BasicPlayer(self._bot, voice_client) if not self.lava_enabled else LavaPlayer(self._bot, voice_client)
        self._player_window = PlayerWindow(self._bot, self._ctx)

class Song:
    __slots__ = ('track') #more mem efficent and faster than __dict__

    def __init__(self, track):
        self.track = track

    def create_embed(self):
        return (discord.Embed(title='```{0.track.title}\n```'.format(self), color=discord.Color.blurple())
        .set_image(url=self.track.thumbnail)
        #.add_field(name='Requested by', value=self.requester.mention)
        #.add_field(name='Uploader', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
        #.add_field(name='URL', value='[Click]({0.source.url})'.format(self))
        .set_author(name="Now playing")
        .set_footer(text="Duration - "+self.track.length))
    
    @staticmethod
    def create_empty_embed():
        return (discord.Embed(title='```No Current Songs In Queue\n```', color=discord.Color.blurple())
        .set_image(url='https://www.clipartmax.com/png/middle/307-3076576_song-clipart-music-bar-paper.png')
        .set_author(name="Now playing"))
class BaseSourceAdapter(ABC):
    
    @property
    @abstractmethod
    def thumbnail(self):
        ...

    @property
    @abstractmethod
    def length(self):
        ...

    @property
    @abstractmethod
    def raw_duration(self):
        ...

    @property
    @abstractmethod
    def title(self):
        ...

class YTDLSourceAdapter(BaseSourceAdapter):
    def __init__(self, source):
        self.source = source

    @property
    def thumbnail(self):
        return self.source.thumbnail

    @property
    def length(self):
        return self.source.duration
    
    @property
    def raw_duration(self):
        return self.source.raw_duration
    
    @property
    def title(self):
        return self.source.title

class LavaSourceAdapter(BaseSourceAdapter):
    def __init__(self, source) -> None:
        self.source = source
    
    def _toSeconds(self, ms):
        return int(ms/1000)

    @property
    def thumbnail(self):
        return self.source.thumbnail
    @property
    def length(self):
        return YTDLSource.parse_duration(self._toSeconds(self.source.length))
    
    @property
    def raw_duration(self):
        return self._toSeconds(self.source.length)
    
    @property
    def title(self):
        return self.source.title

        
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

    async def item_available(self):
        while 1:
            if not self.empty():
                return True

            await asyncio.sleep(.5) #try not to waste cpu cycles

class BasePlayer(ABC):
    def __init__(self) -> None:
        self.state = PlayerState.STOPPED
        self.current = None
    
    def stale(self):
        self.state = PlayerState.STALE
        self._stale()

    async def stop(self):
        self.state = PlayerState.STOPPED
        await await_me_maybe(self._stop)

    async def wait(self):
        self.state = PlayerState.WAITING
        await await_me_maybe(self._wait)

    async def skip(self):
        await await_me_maybe(self._skip)

    async def resume(self):
        self.state = PlayerState.PLAYING
        await await_me_maybe(self._resume)

    async def pause(self):
        self.state = PlayerState.PAUSED
        await await_me_maybe(self._pause)

    async def play_track(self, track, callback=None):
        if self.state == PlayerState.STALE:
            return
            
        if not track:
            await self.wait()
            return
        else:
            self.state = PlayerState.PLAYING

        if not self.state == PlayerState.STOPPED:
            self.current = track

            def iap(): #could prob just make lambda function or something
                return self._internal_audio_player(track, callback) if callback else self._internal_audio_player(track)

            await iap()

    @abstractmethod
    def _stale(self):
        ...

    @abstractmethod
    def _stop(self):
        ...

    @abstractmethod
    def _wait(self):
        ...

    @abstractmethod
    def _skip(self):
        ...

    @abstractmethod
    def _resume(self):
        ...

    @abstractmethod
    def _pause(self):
        ...

    @abstractmethod
    async def _internal_audio_player(self, track, callback):
        ...

class BasicPlayer(BasePlayer):
    def __init__(self, bot, voice_client):
        self.bot = bot
        self.voice = voice_client
        self.loop = bot.loop

        self.current = None
        super().__init__()

    def _stale(self):
        async def disconnect(self):
            await self.voice.disconnect()
        
        future = asyncio.ensure_future(disconnect(), loop=self.loop)


    def _stop(self):
        self.voice.stop()

    def _wait(self):
        self.voice.stop()

    def _skip(self):
        self._wait()

    def _resume(self):
        self.voice.resume()

    def _pause(self):
        self.voice.pause()

    async def _internal_audio_player(self, song, finished_callback):

        self.voice.play(song.track.source, after=finished_callback)

        self.state = PlayerState.PLAYING
            
class LavaPlayer(BasicPlayer):
    def __init__(self, bot, voice_client):
        super().__init__(bot, voice_client)

    def _stop(self):
        return self.voice.stop()

    def _wait(self):
        return self.voice.stop()

    def _skip(self):
        return self._wait()

    def _pause(self):
        
        return self.voice.set_pause(True)

    def _resume(self):

        return self.voice.set_pause(False)

    async def _internal_audio_player(self, song):

        await self.voice.play(song.track.source)

        self.state = PlayerState.PLAYING

class PlayerWindow():
    def __init__(self, bot, ctx):
        self.bot = bot
        self.loop = bot.loop
        self._ctx = ctx
        self.state = PlayerWindowState.NOT_CREATED
        self._current_window = None
        self._menu = None
    
    async def stale(self):
        self.state = PlayerWindowState.STALE
        await self._player_window.player_window.delete()
        self._menu = None

    async def player_window(self, song, timeout):
        if self.state == PlayerWindowState.STALE:
            return  

        create_player_embed = lambda current : current.create_embed() if current else Song.create_empty_embed()
        self.state = PlayerWindowState.ACTIVE

        

        if not self._menu or not self._current_window:
            self._menu = PlayerMenu(self.bot, song.track.raw_duration if song else timeout)
            await self._menu.send_initial_message(self._ctx, self._ctx.channel, create_player_embed(song))
            self._current_window = self._menu.message
        else:
            await self._current_window.edit(embed=create_player_embed(song))
            self._menu = PlayerMenu(self.bot, song.track.raw_duration if song else timeout, self._current_window)
            #restarts reaction menu when new song is added
            #self._menu = await PlayerMenu.construct_from_existing(self._current_window, self.bot, song.source.raw_duration if song else timeout)
        
        await self._menu.start(self._ctx)
  
                    



