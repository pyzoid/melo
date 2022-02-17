from lib.menu import PlayerMenu
from lib.music.source import YTDLSource
import asyncio
from contextlib import suppress

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

    def __init__(self, ctx, bot):
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

    @property
    def player(self):
        return self._player

    @property
    def is_stale(self):
        return self._player.state == PlayerState.STALE or self._player_window.state == PlayerWindowState.STALE

    def skip(self):
        if self.current:
            self.current = None
            self._player.skip()
            
    def stop(self):
        self.current = None
        self.queue.clear()
        self._player.stop()

    async def play(self, song):
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

                self.loop.create_task(self._player.audio_player(song, self._playback_finished))
                self.loop.create_task(self._player_window.player_window(song, PlayerContext.TIMEOUT))
                try:
                    if song:
                        await asyncio.wait_for(self._next.wait(), song.source.raw_duration)
                    else:
                        await asyncio.wait_for(self.queue.item_available(), PlayerContext.TIMEOUT)
                except asyncio.TimeoutError:
                    print("playercontext timeout")
                    await self._player.stale()
                    await self._player_window.stale()
                    break
                else:
                    if song:
                        print(f"Finished playing {song.source.title}")
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
        self._player = Player(self._bot, voice_client)
        self._player_window = PlayerWindow(self._bot, self._ctx)

class Song:
    __slots__ = ('source', 'requester') #more mem efficent and faster than __dict__

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        return (discord.Embed(title='```{0.source.title}\n```'.format(self), color=discord.Color.blurple())
        .set_image(url=self.source.thumbnail)
        #.add_field(name='Requested by', value=self.requester.mention)
        #.add_field(name='Uploader', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
        #.add_field(name='URL', value='[Click]({0.source.url})'.format(self))
        .set_author(name="Now playing")
        .set_footer(text="Duration - "+self.source.duration))
    
    @staticmethod
    def create_empty_embed():
        return (discord.Embed(title='```No Current Songs In Queue\n```', color=discord.Color.blurple())
        .set_image(url='https://www.clipartmax.com/png/middle/307-3076576_song-clipart-music-bar-paper.png')
        .set_author(name="Now playing"))

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

            

class Player(): #rename AudioPlayer
    def __init__(self, bot, voice_client):
        self.state = PlayerState.STOPPED
        self.bot = bot
        self.voice = voice_client
        self.loop = bot.loop

        self.current = None


    async def stale(self):
        self.state = PlayerState.STALE
        await self.voice.disconnect()

    def stop(self):
        self.state = PlayerState.STOPPED
        self.voice.stop()

    def wait(self):
        self.state = PlayerState.WAITING
        self.voice.stop()

    def skip(self):
        self.wait()

    def resume(self):
        self.state = PlayerState.PLAYING
        self.voice.resume()

    def pause(self):
        self.state = PlayerState.PAUSED
        self.voice.pause()

    async def audio_player(self, song, finished_callback):

        if self.state == PlayerState.STALE:
            return
            
        if not song:
            self.wait()
            return
        else:
            self.state = PlayerState.PLAYING

        if not self.state == PlayerState.STOPPED:
                    
            self.current = song

            self.voice.play(song.source, after=finished_callback)

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
            self._menu = PlayerMenu(self.bot, song.source.raw_duration if song else timeout)
            await self._menu.send_initial_message(self._ctx, self._ctx.channel, create_player_embed(song))
            self._current_window = self._menu.message
        else:
            await self._current_window.edit(embed=create_player_embed(song))
            self._menu = PlayerMenu(self.bot, song.source.raw_duration if song else timeout, self._current_window)
            #restarts reaction menu when new song is added
            #self._menu = await PlayerMenu.construct_from_existing(self._current_window, self.bot, song.source.raw_duration if song else timeout)
        
        await self._menu.start(self._ctx)
  
                    



