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

        self.nlp = None
        self.model = None
        self.matcher = None

        super().__init__(command_prefix=PREFIX, owner_ids=OWNER_IDS)

    def setup(self, enable_ml):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}")
            print(f"{cog} cog loaded".capitalize())

        if enable_ml:
            import stanza
            from spacy_stanza import StanzaLanguage
            from spacy.matcher import Matcher

            from model import intent_model
            
            snlp = stanza.Pipeline(lang='en')
            self.nlp = StanzaLanguage(snlp)
            self.model = intent_model()

            self.matcher = Matcher(self.nlp.vocab)

    def run(self, version, enable_ml):
        self.VERSION = version

        print("Setup running...")
        self.setup(enable_ml)
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
        elif message.author.id in OWNER_IDS:
            if not self.model:
                return


            intent = self.model.intent(message.content)[-1]
            
            if intent == "PlayMusic":
                pattern = [[{"POS": "VERB"},{"OP": "?"}, {"OP": "?"},{"OP": "?"}, {"LOWER": "by"},{"OP": "?"},  {"OP": "?"}],
                [{"POS": "VERB"},{"OP": "?"}, {"OP": "?"},{"OP": "?"}]
                ]
                
                self.matcher.add("songbypattern", pattern)

                doc = self.nlp(message.content)
                matches = self.matcher(doc)
                #for letter, token in zip(message.content.split(" "), doc):
                #    print(f"{letter}:{token.pos_}-{token.ent_type_}")
                if len(matches) == 0:
                    return

                diff = [ match[-1] - match[-2] for match in matches ]
                idx = diff.index(max(diff)) #finds biggest match
                _, start, end = matches[idx]
                span = doc[start:end]

                cmd = " ".join(span.text.split(" ")[1:]) #just removes the verb, like "play" from the search query
                
                for word, token in zip(message.content.split(" "), doc):

                    if token.pos_ == "VERB" and word in cmd:
                        cmd = cmd.replace(word, "")[1:]
                        break
                
                await ctx.invoke(self.get_command('play'), query=cmd)
bot = Bot()