from typing import Literal
import json

import discord
from discord import ui
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

from utils.whitecord import Embed, EmbedField, EmbedAuthor
from utils.translator import WhiteTranslator


class Help(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.translator: WhiteTranslator = self.client.tree.translator

    @app_commands.command(name="help", description="Show help information")
    async def help(
        self,
        interaction: discord.Interaction,
        command: Literal[
            "schedule plan",
            "schedule list",
            "schedule toggle",
            "schedule delete",
            "squads",
            "event/notification",
            "event/recurrence",
        ],
    ):
        with open(
            f"data/help_docs/{command.replace(' ', '_').replace('/', '__')}.json",
            "r",
            encoding="utf-8",
        ) as f:
            help_data = json.load(f)

        view = ui.LayoutView()
        container = ui.Container(
            ui.TextDisplay(
                f"# {help_data['title']}\n### {help_data['command']}\n{help_data['description']}"
            ),
            *(
                [
                    ui.TextDisplay(
                        "\n".join(
                            [
                                f"**{option['name']}** ({option['type']}) {'**Required**' if option['required'] else ''}\n└Description: {option['description']}"
                                for option in help_data["options"]
                            ]
                        )
                    )
                ]
                if "options" in help_data
                else []
            ),
        )
        view.add_item(container)

        await interaction.response.send_message(view=view)


async def setup(client):
    await client.add_cog(Help(client))
