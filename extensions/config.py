from datetime import datetime
from typing import Optional
import discord
from discord import ui
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

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
        logchannel: Optional[discord.TextChannel] = None,
    ):
        """Configure the bot settings for this server."""
        if logchannel is None:
            guild_config = GuildConfigs.get(guild_id=interaction.guild_id)
            view = ConfigView(
                interaction,
                logchannel=(
                    self.client.get_channel(guild_config.log_channel_id).name
                    if guild_config.log_channel_id
                    else None
                ),
            )

            await interaction.response.send_message(view=view)
            return

        if logchannel:
            if logchannel in interaction.guild.channels:
                if discord.Permissions(permissions=2048).is_subset(
                    logchannel.permissions_for(interaction.guild.me)
                ):
                    GuildConfigs.update(log_channel_id=logchannel.id).where(
                        GuildConfigs.guild_id == interaction.guild_id
                    ).execute()
                    msg = f"## Successfully updated the log channel.\n### New log channel: {logchannel.mention}"
                else:
                    msg = (
                        "## I do not have permission to send messages in that channel."
                    )
            else:
                msg = "## The specified channel is non existent. Please select a valid channel."

            view = ui.LayoutView()
            view.add_item(ui.Container(ui.TextDisplay(msg)))

            await interaction.response.send_message(view=view)


class ConfigView(ui.LayoutView):
    class ResetButton(ui.Button):
        def __init__(self, parent: "ConfigView"):
            super().__init__(
                style=discord.ButtonStyle.danger,
                label="Reset\nLog Channel",
                custom_id="config_reset_logchannel",
            )
            self.__parent = parent

        async def callback(self, button_interaction: discord.Interaction):
            await button_interaction.response.defer()
            updated_rows = (
                GuildConfigs.update(log_channel_id=None)
                .where(GuildConfigs.guild_id == self.__parent.interaction.guild_id)
                .execute()
            )
            if updated_rows > 0:
                await self.__parent.update_view()
            else:
                await button_interaction.followup.send(
                    content="Failed to reset the log channel. Please try again later.",
                    ephemeral=True,
                )

    @property
    def interaction(self) -> discord.Interaction:
        return self.__interaction

    def __init__(
        self, interaction: discord.Interaction, logchannel: Optional[str] = None
    ):
        super().__init__()
        self.__interaction = interaction

        container = self.create_container(logchannel)
        self.add_item(container)

    def create_container(self, logchannel: Optional[str] = None) -> ui.Container:
        container = ui.Container(
            ui.TextDisplay("# Bot Config"),
            ui.TextDisplay("### Log Channel"),
            (
                ui.Section(
                    ui.TextDisplay(logchannel),
                    accessory=self.ResetButton(self),
                )
                if logchannel
                else ui.TextDisplay("No log channel is currently set.")
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
