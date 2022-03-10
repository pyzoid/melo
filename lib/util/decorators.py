from disnake.ext.commands.slash_core import InvokableSlashCommand
import inspect
from functools import wraps

#just injects player context into interaction object
def player_slash_command(**kwargs):
    
    def inner(func):
        #also has to inject function signature, so disnake knows what params to use for slash commands
        sig = inspect.signature(func)
        async def cmd(self, interaction, **kwargs):
            
            interaction.player_context = self.get_player_context(interaction)
            return await func(self, interaction, **kwargs)
       
        sig = sig.replace(parameters=tuple(sig.parameters.values()))
        cmd.__signature__ = sig
        return InvokableSlashCommand(cmd, **kwargs)
        
        
    return inner