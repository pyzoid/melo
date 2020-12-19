from discord.ext.commands import Cog
from discord.ext.commands import command
class Meta(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3]) 

    @command(name="info", aliases=["about"])
    async def info(self, ctx, *, message):
        embed=discord.Embed(title="music-man", description="by badcode6 and Meschdog18")
        await ctx.send(embed=embed)

    

def setup(bot):
    bot.add_cog(Meta(bot))
    