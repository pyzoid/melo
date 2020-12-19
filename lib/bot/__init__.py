from glob import glob
from asyncio import sleep
from discord.ext.commands import Bot as BotBase
from discord.ext.commands import CommandNotFound, Context, MissingRequiredArgument
from discord.http import HTTPException, Forbidden

from apscheduler.schedulers.asyncio import AsyncIOScheduler
PREFIX = "?"
OWNER_IDS = [226939988070236161]
COGS = [path.split("/")[-1][:-3] for path in glob("./lib/cogs/*.py")]

class CogReady(object):
    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        print(f"{cog} cog ready".capitalize())

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])

class Bot(BotBase):
    def __init__(self):
        self.PREFIX = PREFIX
        self.ready = False
        self.cogs_ready = CogReady()
        self.scheduler = AsyncIOScheduler()
        super().__init__(command_prefix=PREFIX, owner_ids=OWNER_IDS)

    def setup(self):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}")
            print(f"{cog} cog loaded".capitalize())
    def run(self, version):
        self.VERSION = version

        print("Setup running...")
        self.setup()
        with open("./lib/bot/token", "r", encoding="utf-8") as f:
            self.TOKEN = f.read()

        print("Bot starting...")
        super().run(self.TOKEN, reconnect=True)

    async def on_connect(self):
        print("Bot connected!")

    async def on_disconnect(self):
        print("Bot disconnected :(")

    async def on_error(self, err, *args, **kwargs):
        if err == "on_command_error":
            await args[0].send("Something went wrong.")
        raise

    async def on_command_error(self, ctx, exc):
        if isinstance(exc, CommandNotFound):
            pass
        elif isinstance(exc, HTTPException):
            await ctx.send("Unable to send message")
        elif isinstance(exc, Forbidden):
            await ctx.send("Invalid permissions to preform action")
        elif isinstance(exc, MissingRequiredArgument):
            await ctx.send("Missing required arguments for command")
        else:
            raise exc
          
    async def on_ready(self):
        if not self.ready:
            while not self.cogs_ready.all_ready():
                await sleep(0.5)
            self.ready = True
            print("Bot ready")
            
        else:
            print("Bot reconnected")

    async def on_message(self, message):
        if message.author.bot: return
        await self.process_commands(message)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)
        if ctx.command is not None and ctx.guild is not None:
            if self.ready:
                await self.invoke(ctx)
            else:
                await ctx.send("Bot still starting, please wait a few moments...")
bot = Bot()