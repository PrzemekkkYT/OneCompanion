from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands

from utils.whitecord import Embed, EmbedField, EmbedAuthor


class Squads(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.translator = self.client.tree.translator

    @app_commands.command(name="squads", description="Manage squads")
    async def squads(
        self,
        interaction: discord.Interaction,
        infantry: int,
        lancer: int,
        marksman: int,
        own_squad_size: int,
        joiner_squad_size: int,
        march_count: int,
        own_march_rule: Literal[
            "10:20:70", "10:20:80", "20:30:50", "33:33:33"
        ] = "10:20:70",
        joiner_march_rule: Literal["1k:fill:max", "10:20:70", "1:9:90"] = "1k:fill:max",
    ):
        infantry_left = infantry
        lancer_left = lancer
        marksman_left = marksman

        match own_march_rule:
            case "10:20:70":
                own_squad = {
                    "infantry": own_squad_size * 0.1,
                    "lancer": own_squad_size * 0.2,
                    "marksman": own_squad_size * 0.7,
                }
            case "10:20:80":
                own_squad = {
                    "infantry": own_squad_size * 0.1,
                    "lancer": own_squad_size * 0.2,
                    "marksman": own_squad_size * 0.8,
                }
            case "20:30:50":
                own_squad = {
                    "infantry": own_squad_size * 0.2,
                    "lancer": own_squad_size * 0.3,
                    "marksman": own_squad_size * 0.5,
                }
            case "33:33:33":
                own_squad = {
                    "infantry": own_squad_size / 3,
                    "lancer": own_squad_size / 3,
                    "marksman": own_squad_size / 3,
                }

        infantry_left -= own_squad["infantry"]
        lancer_left -= own_squad["lancer"]
        marksman_left -= own_squad["marksman"]

        match joiner_march_rule:
            case "1k:fill:max":
                joiner_marksman = marksman_left / march_count
                joiner_squad = {
                    "infantry": 1000,
                    "lancer": joiner_squad_size - 1000 - joiner_marksman,
                    "marksman": joiner_marksman,
                }
            case "10:20:70":
                joiner_squad = {
                    "infantry": joiner_squad_size * 0.1,
                    "lancer": joiner_squad_size * 0.2,
                    "marksman": joiner_squad_size * 0.7,
                }
            case "1:9:90":
                joiner_squad = {
                    "infantry": joiner_squad_size * 0.01,
                    "lancer": joiner_squad_size * 0.09,
                    "marksman": joiner_squad_size * 0.9,
                }

        embed = Embed(
            author=EmbedAuthor(
                name=interaction.user.name, icon_url=interaction.user.avatar.url
            ),
            title="Squad Composition",
            description="Here is the composition of your squad:",
            fields=[
                EmbedField(
                    name="Own Squad",
                    value=f"Infantry: {round(own_squad['infantry'])}\nLancer: {round(own_squad['lancer'])}\nMarksman: {round(own_squad['marksman'])}",
                ),
                EmbedField(
                    name="Joiner Squad",
                    value=f"Infantry: {round(joiner_squad['infantry'])}\nLancer: {round(joiner_squad['lancer'])}\nMarksman: {round(joiner_squad['marksman'])}",
                ),
            ],
        )


async def setup(client):
    await client.add_cog(Squads(client))
