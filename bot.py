import logging
import json
import os
from pathlib import Path

import discord
from discord.ext import commands

from utils.translator import WhiteTranslator

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
            activity=discord.CustomActivity(name="Activity Here"),
        )

    async def setup_hook(self):
        await self.tree.set_translator(WhiteTranslator())

        for filename in os.listdir("./extensions"):
            if filename.endswith(".py"):
                await self.load_extension(f"extensions.{filename[:-3]}")

        self.tree.copy_global_to(guild=discord.Object(id="575414543392702480"))
        self.tree.copy_global_to(guild=discord.Object(id="1398687376745828457"))
        self.tree.copy_global_to(guild=discord.Object(id="1332709233547939861"))
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("========== bot is ready ==========")


if __name__ == "__main__":
    intents = discord.Intents.all()
    client = MyClient(intents=intents)

    @client.command()
    async def ping(ctx):
        await ctx.send("Pong!")

    client.run(bot_config["token"], log_handler=handler, log_level=logging.INFO)
