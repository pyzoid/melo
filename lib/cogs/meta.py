from disnake.ext.commands import Cog
from disnake.ext.commands import command
import disnake
#import openai

class Meta(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up(__file__.split("/")[-1][:-3].split("\\")[-1]) 

    @command(name="info", aliases=["about"])
    async def info(self, ctx):
        embed=disnake.Embed(title="melo", description="Next-Gen Music Bot \n \n by Meschdog18")
        await ctx.send(embed=embed)


    """
    @command(name="talk", aliases=["t"])
    async def talk(self, ctx, *, query):
        openai.api_key = ""
        response = openai.Completion.create(
            engine="text-davinci-001",
            prompt=f"I am Melo, a next generation disnake music bot. I was written in python and use lavalink and ffmpeg for streaming music. I currently support streaming for youtube. My main music commands consist of :play, pause, resume, shuffle, skip, volume. \n\nhuman: {query}\n",
            temperature=0.9,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0.09,
            presence_penalty=0.25
        )

        await ctx.send(response.choices[0].text)
    """
    

def setup(bot):
    bot.add_cog(Meta(bot))
    