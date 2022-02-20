from discord.ext.commands import Cog
from discord.ext.commands import command
import discord
class Meta(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3].split("\\")[-1]) 

    @command(name="info", aliases=["about"])
    async def info(self, ctx):
        embed=discord.Embed(title="melo", description="Next-Gen Music Bot \n \n by Meschdog18")
        await ctx.send(embed=embed)

    

def setup(bot):
    bot.add_cog(Meta(bot))
    