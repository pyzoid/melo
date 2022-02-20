from discord import slash_command
from discord.ext.commands import Cog
from discord.ext.commands import command

class Fun(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3].split("\\")[-1]) 

    @command(name="ping")
    async def ping(self, ctx):
        await ctx.send("Pong! {}s".format(round(self.bot.latency, 2))) 

    @command(name="echo", aliases=["say"])
    async def echo_message(self, ctx, *, message):
        await ctx.message.delete()
        await ctx.send(message)

    @slash_command(guild_ids=["678809641597140992"])
    async def test(self, ctx):
        await ctx.respond("g")

def setup(bot):
    bot.add_cog(Fun(bot))
    