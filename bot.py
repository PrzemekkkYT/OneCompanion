import datetime
import logging
import json
import os
from pathlib import Path
import random

# from watchdog.observers import Observer

import discord
from discord.ext import commands, tasks
from typing import Literal

from utils.whitecord import Embed, EmbedField
from utils.translator import WhiteTranslator
from utils.cog_watcher import CogReloader
from utils.utils import pretty_traceback

logger = logging.getLogger("discord")

Path("logs").mkdir(exist_ok=True)
handler = logging.FileHandler(filename="logs/bot.log", encoding="utf-8", mode="a+")

bot_config = json.load(open("./config.json", "r+"))

logger.addHandler(logging.StreamHandler())


class MyClient(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(
            command_prefix="f!",
            intents=intents,
            status=discord.Status.idle,
            activity=discord.CustomActivity(name="ONE for all"),
        )

    async def tree_error_handler(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ):
        print(pretty_traceback(error))
        # logger.error(f"Error occurred: {error}")
        original = getattr(error, "original", error)
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=Embed(
                    translator=self.tree.translator,
                    locale=interaction.locale,
                    title="Error Occurred",
                    description="An error occurred while processing your request.",
                    fields=[
                        EmbedField(
                            name="Error", value=f"{type(original).__name__}: {original}"
                        ),
                    ],
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=Embed(
                    translator=self.tree.translator,
                    locale=interaction.locale,
                    title="Error Occurred",
                    description="An error occurred while processing your request.",
                    fields=[
                        EmbedField(
                            name="Error", value=f"{type(original).__name__}: {original}"
                        ),
                    ],
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

    async def setup_hook(self):
        await self.tree.set_translator(WhiteTranslator())
        self.tree.error(self.tree_error_handler)

        for filename in os.listdir("./extensions"):
            if filename.endswith(".py"):
                await self.load_extension(f"extensions.{filename[:-3]}")

        self.tree.copy_global_to(guild=discord.Object(id="575414543392702480"))
        self.tree.copy_global_to(guild=discord.Object(id="1398687376745828457"))
        self.tree.copy_global_to(guild=discord.Object(id="1332709233547939861"))
        await self.tree.sync()

    async def on_ready(self):
        change_status.start()
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("========== bot is ready ==========")


@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
async def change_status():
    await client.change_presence(
        status=discord.Status.idle,
        activity=discord.CustomActivity(name=random.choice(bot_config["statuses"])),
    )


if __name__ == "__main__":
    intents = discord.Intents.all()
    client = MyClient(intents=intents)

    # observer = Observer()
    # observer.schedule(CogReloader(client), "./extensions", recursive=False)
    # observer.start()

    client.run(bot_config["token"], log_handler=handler, log_level=logging.INFO)
    # try:
    #     client.run(bot_config["token"], log_handler=handler, log_level=logging.INFO)
    # finally:
    #     observer.stop()
    #     observer.join()


@client.command()
async def ping(ctx):
    await ctx.send("Pong!")


@client.tree.command()
@discord.app_commands.check(
    lambda i: i.user.id == 183242057882664961
)  # Replace with your user ID
async def reload(
    interaction: discord.Interaction,
    extension: Literal["all", "help", "schedule", "squads", "tests"] = "all",
):
    if extension == "all":
        for filename in os.listdir("./extensions"):
            if filename.endswith(".py"):
                await client.reload_extension(f"extensions.{filename[:-3]}")
        await interaction.response.send_message("All extensions reloaded.")
    else:
        await client.reload_extension(f"extensions.{extension}")
