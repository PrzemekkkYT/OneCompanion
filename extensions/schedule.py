from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands, TextChannel
from discord.ext import commands, tasks
from discord.app_commands import locale_str

from orms.schedules import Messages, ScheduledForToday
from utils.utils import parse_datetime, parse_interval, timestamp
from utils.whitecord import Embed, EmbedField, EmbedAuthor


class Schedule(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.translator = self.client.tree.translator
        self.post_schedule.start()

    @tasks.loop(minutes=1)
    async def post_schedule(self):
        for schedule in ScheduledForToday.select().where(
            ScheduledForToday.is_active == 1
        ):
            message = Messages.get_by_id(schedule.id)
            channel = self.client.get_channel(message.channel_id)

            if not channel:
                continue

            next_post = schedule.next_post
            if next_post <= timestamp(datetime.now(tz=timezone.utc)):
                embed = Embed(
                    translator=self.translator,
                    locale=discord.Locale.american_english,
                    title=message.title,
                    description=message.content,
                    color=discord.Color.blue(),
                    timestamp=datetime.fromtimestamp(next_post, tz=timezone.utc),
                    image=message.image,
                    author=EmbedAuthor(
                        name=self.client.user.name,
                        icon_url=self.client.user.display_avatar.url,
                    ),
                )
                content = (
                    f"<@&{message.mention}>"
                    if message.mention
                    else "@everyone" if message.mention == -1 else None
                )
                await channel.send(
                    content=content,
                    embed=embed,
                )

                message.next_post = message.next_post + message.interval
                message.save()

    @post_schedule.before_loop
    async def before_post_schedule(self):
        await self.client.wait_until_ready()

    @app_commands.command(
        name=locale_str("schedule"), description=locale_str("schedule_description")
    )
    @app_commands.rename(
        title=locale_str("schedule_title"),
        interval=locale_str("schedule_interval"),
        content=locale_str("schedule_content"),
        channel=locale_str("schedule_channel"),
        initial_datetime_str=locale_str("schedule_initialdatetime"),
        image=locale_str("schedule_image"),
        mention=locale_str("schedule_mention"),
    )
    @app_commands.describe(
        title=locale_str("schedule_title_description"),
        interval=locale_str("schedule_interval_description"),
        content=locale_str("schedule_content_description"),
        channel=locale_str("schedule_channel_description"),
        initial_datetime_str=locale_str("schedule_initialdatetime_description"),
        image=locale_str("schedule_image_description"),
        mention=locale_str("schedule_mention_description"),
    )
    @app_commands.default_permissions(manage_messages=True)
    async def schedule(
        self,
        interaction: discord.Interaction,
        title: str,
        interval: str,
        content: Optional[str] = None,
        channel: Optional[TextChannel] = None,
        initial_datetime_str: Optional[str] = None,
        image: Optional[str] = None,
        mention: Optional[discord.Role] = None,
    ):
        if not channel:
            channel = interaction.channel

        if not initial_datetime_str:
            initial_datetime = interaction.created_at
            next_post = timestamp(initial_datetime) + parse_interval(interval)
        else:
            initial_datetime = parse_datetime(initial_datetime_str)
            next_post = (
                timestamp(initial_datetime)
                if initial_datetime > datetime.now(tz=timezone.utc)
                else timestamp(initial_datetime) + parse_interval(interval)
            )

        if initial_datetime < datetime.now(tz=timezone.utc):
            await interaction.response.send_message(
                await self.translator.translate(
                    string=locale_str("schedule_initialdatetime_error"),
                    locale=interaction.locale,
                ),
                ephemeral=True,
            )
            return

        message = Messages.create(
            title=title,
            interval=parse_interval(interval),
            content=content,
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            initial_datetime=timestamp(initial_datetime),
            image=image,
            mention=(
                None
                if not mention
                else mention.id if mention != interaction.guild.default_role else -1
            ),
            next_post=next_post,
            is_active=1,
        )

        await interaction.response.send_message(
            content=await self.translator.translate(
                locale=interaction.locale, string=locale_str("schedule_success")
            ),
            embed=Embed(
                translator=self.translator,
                title=title,
                description=content,
                color=discord.Color.green(),
                timestamp=datetime.now(),
                image=image,
                thumbnail=self.client.user.display_avatar.url,
                fields=[
                    EmbedField(
                        name=locale_str("schedule_field_channel"),
                        value=channel.mention,
                        inline=True,
                    ),
                    EmbedField(
                        name=locale_str("schedule_field_initialdatetime"),
                        value=f"<t:{next_post}:f>\n<t:{next_post}:R>",
                        inline=True,
                    ),
                    EmbedField(
                        name=locale_str("schedule_field_interval"),
                        value=f"Every {interval}",
                        inline=True,
                    ),
                ],
            ),
        )


async def setup(client):
    await client.add_cog(Schedule(client))
