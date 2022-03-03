from discord.ext import menus
from reactionmenu import ViewMenu, ViewButton
import disnake
import asyncio

class PlayerMenu(ViewMenu):
    def __init__(self, bot, ctx, embed, **kwargs) -> None:
        super().__init__(ctx=ctx, menu_type=ViewMenu.TypeEmbed, show_page_director=False, **kwargs)

        self.bot = bot
        self.add_page(embed)


        pause_resume_button = ViewButton(emoji='⏯️', custom_id=ViewButton.ID_CALLER, followup=ViewButton.Followup(details=ViewButton.Followup.set_caller_details(self.on_pause_resume)))
        shuffle_button = ViewButton(emoji='🔀', custom_id=ViewButton.ID_CALLER, followup=ViewButton.Followup(details=ViewButton.Followup.set_caller_details(self.on_shuffle)))
        loop_button = ViewButton(emoji='🔁', custom_id=ViewButton.ID_CALLER, followup=ViewButton.Followup(details=ViewButton.Followup.set_caller_details(self.on_loop)))
        skip_button = ViewButton(emoji='⏭️', custom_id=ViewButton.ID_CALLER, followup=ViewButton.Followup(details=ViewButton.Followup.set_caller_details(self.on_skip)))
        stop_button = ViewButton(emoji='⏹️', custom_id=ViewButton.ID_CALLER, followup=ViewButton.Followup(details=ViewButton.Followup.set_caller_details(self.on_stop)))

        self.add_buttons([pause_resume_button, shuffle_button, loop_button, skip_button, stop_button])
        #self.add_button(ViewButton(emoji="🗑️",custom_id=ViewButton.ID_END_SESSION))
        #self.add_button(ViewButton.end_session())

    async def on_pause_resume(self):
        await self._ctx.invoke(self.bot.get_command("_play_pause"))

    async def on_shuffle(self):
        await self._ctx.invoke(self.bot.get_command("shuffle"))

    async def on_loop(self):
        await self._ctx.invoke(self.bot.get_command("loop"))

    async def on_skip(self):
        await self._ctx.invoke(self.bot.get_command('skip'))

    async def on_stop(self):
        await self._ctx.invoke(self.bot.get_command('stop'))

    async def restart(self, timeout):
        self._menu_timed_out = False
        self.__timeout = timeout
  
        if ViewMenu._sessions_limited:
            can_proceed = await self._handle_session_limits()
            if not can_proceed:
                return
       
        self._is_running = True
        ViewMenu._active_sessions.append(self)

        await self.refresh_menu_buttons()
    

    
