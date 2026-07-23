from datetime import datetime
from typing import Optional
import discord
from discord import ui
from discord import app_commands
from discord.ext import commands

from orms.configs import GuildConfigs
from utils.whitecord import Embed


class Config(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.translator = self.client.tree.translator

    @app_commands.command(
        name="config", description="Configure the bot settings for this server."
    )
    async def config(
        self,
        interaction: discord.Interaction,
        translator_enabled: Optional[bool] = None,
    ):
        """Configure the bot settings for this server."""
        if translator_enabled is None:
            guild_config: GuildConfigs = GuildConfigs.get(guild_id=interaction.guild_id)
            view = ConfigView(
                interaction,
                translator_enabled=guild_config.translator_enabled,
            )

            await interaction.response.send_message(view=view)
            return

        if translator_enabled is not None:
            GuildConfigs.update(translator_enabled=translator_enabled).where(
                GuildConfigs.guild_id == interaction.guild_id
            ).execute()

            view = ui.LayoutView()
            view.add_item(
                ui.Container(
                    ui.TextDisplay(
                        f"## Successfully {'enabled' if translator_enabled else 'disabled'} the translator."
                    )
                )
            )

            await interaction.response.send_message(view=view)


class ConfigView(ui.LayoutView):
    @property
    def interaction(self) -> discord.Interaction:
        return self.__interaction

    def __init__(
        self,
        interaction: discord.Interaction,
        translator_enabled: Optional[bool] = False,
    ):
        super().__init__()
        self.__interaction = interaction

        container = self.create_container(translator_enabled)
        self.add_item(container)

    def create_container(
        self,
        translator_enabled: Optional[bool] = False,
    ) -> ui.Container:
        container = ui.Container(
            ui.TextDisplay("# Bot Config"),
            ui.TextDisplay("### Translator"),
            ui.TextDisplay(
                f"Translator status: {'enabled' if translator_enabled else 'disabled'}"
            ),
        )
        return container

    async def update_view(self):
        self.clear_items()
        container = self.create_container()
        self.add_item(container)
        await self.__interaction.edit_original_response(view=self)


async def setup(client: commands.Bot):
    await client.add_cog(Config(client))
