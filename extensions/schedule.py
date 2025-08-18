from datetime import datetime, timezone
from typing import Optional
from math import ceil

import discord
from discord import app_commands, TextChannel
from discord.ext import commands, tasks
from discord.app_commands import locale_str

from orms.schedules import Messages, ScheduledForToday
from utils.utils import parse_datetime, parse_interval, timestamp, from_interval
from utils.whitecord import Embed, EmbedField, EmbedAuthor, Pagination, Page


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
                content = ""
                if message.mention:
                    if message.mention == -1:
                        content = "@everyone"
                    else:
                        content = f"<@&{message.mention}>"
                await channel.send(
                    content=content,
                    embed=embed,
                )

                message.next_post = message.next_post + message.interval
                message.save()

    @post_schedule.before_loop
    async def before_post_schedule(self):
        await self.client.wait_until_ready()

    schedule_group = app_commands.Group(
        name="schedule", description=locale_str("schedule_description")
    )
    schedule_group.default_permissions = discord.Permissions(manage_messages=True)

    @schedule_group.command(
        name=locale_str("schedule_plan"),
        description=locale_str("schedule_plan_description"),
    )
    @app_commands.rename(
        title=locale_str("schedule_plan_title"),
        interval=locale_str("schedule_plan_interval"),
        content=locale_str("schedule_plan_content"),
        channel=locale_str("schedule_plan_channel"),
        initial_datetime_str=locale_str("schedule_plan_initialdatetime"),
        image=locale_str("schedule_plan_image"),
        mention=locale_str("schedule_plan_mention"),
    )
    @app_commands.describe(
        title=locale_str("schedule_plan_title_description"),
        interval=locale_str("schedule_plan_interval_description"),
        content=locale_str("schedule_plan_content_description"),
        channel=locale_str("schedule_plan_channel_description"),
        initial_datetime_str=locale_str("schedule_plan_initialdatetime_description"),
        image=locale_str("schedule_plan_image_description"),
        mention=locale_str("schedule_plan_mention_description"),
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

        if not any(unit in interval for unit in ("w", "d", "h", "m")):
            await interaction.response.send_message(
                await self.translator.translate(
                    string=locale_str("schedule_interval_error"),
                    locale=interaction.locale,
                ),
                ephemeral=True,
            )
            return

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

        if initial_datetime < interaction.created_at:
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

    @schedule_group.command(
        name=locale_str("schedule_list"),
        description=locale_str("schedule_list_description"),
    )
    @app_commands.rename(show_ids=locale_str("schedule_list_show_ids"))
    @app_commands.describe(show_ids=locale_str("schedule_list_show_ids_description"))
    async def schedule_list(
        self, interaction: discord.Interaction, show_ids: bool = False
    ):
        schedules = Messages.select().where(
            Messages.guild_id == interaction.guild.id,
        )

        pages = []

        for i in range(ceil(len(schedules) / 5)):
            page = Page(
                name=f"Page {i + 1}",
                embed=Embed(
                    translator=self.translator,
                    locale=interaction.locale,
                    title=locale_str("schedule_list"),
                    timestamp=datetime.now(),
                    color=discord.Color.green(),
                    thumbnail=self.client.user.display_avatar.url,
                    fields=[
                        EmbedField(
                            name=(
                                f"{schedule.title} | {schedule.id}"
                                if show_ids
                                else schedule.title
                            ),
                            value=f"• Next post: <t:{schedule.next_post}:f>\n•Every: {from_interval(schedule.interval)}\n•Channel: <#{schedule.channel_id}>\nActive: {'Yes' if schedule.is_active else 'No'}",
                            inline=False,
                        )
                        for schedule in schedules[i * 5 : (i + 1) * 5]
                    ],
                ),
            )
            pages.append(page)

        pagination = Pagination(
            pages=pages,
            translator=self.translator,
            locale=interaction.locale,
        )
        pagination.interaction = interaction

        embed, view = await pagination.create()

        pagination.message = await interaction.response.send_message(
            embed=embed,
            view=view,
        )

    @schedule_group.command(
        name=locale_str("schedule_delete"),
        description=locale_str("schedule_delete_description"),
    )
    @app_commands.rename(schedule_id=locale_str("schedule_delete_schedule_id"))
    @app_commands.describe(
        schedule_id=locale_str("schedule_delete_schedule_id_description")
    )
    async def schedule_delete(self, interaction: discord.Interaction, schedule_id: int):
        schedule = Messages.get_or_none(Messages.id == schedule_id)

        if not schedule:
            await interaction.response.send_message(
                content=await self.translator.translate(
                    locale=interaction.locale, string=locale_str("schedule_not_found")
                )
            )
            return

        schedule.delete_instance()

        await interaction.response.send_message(
            content=await self.translator.translate(
                locale=interaction.locale, string=locale_str("schedule_deleted")
            )
        )

    @schedule_group.command(
        name=locale_str("schedule_toggle"),
        description=locale_str("schedule_toggle_description"),
    )
    @app_commands.rename(schedule_id=locale_str("schedule_toggle_schedule_id"))
    @app_commands.describe(
        schedule_id=locale_str("schedule_toggle_schedule_id_description")
    )
    async def schedule_toggle(self, interaction: discord.Interaction, schedule_id: int):
        schedule = Messages.get_or_none(Messages.id == schedule_id)

        if not schedule:
            await interaction.response.send_message(
                content=await self.translator.translate(
                    locale=interaction.locale, string=locale_str("schedule_not_found")
                )
            )
            return

        schedule.is_active = int(not schedule.is_active)
        schedule.save()

        await interaction.response.send_message(
            content=await self.translator.translate(
                locale=interaction.locale,
                string=locale_str(
                    "schedule_toggled",
                    active=await self.translator.translate(
                        locale=interaction.locale,
                        string=locale_str(
                            "activated" if schedule.is_active else "deactivated"
                        ),
                    ),
                ),
            )
        )


async def setup(client):
    await client.add_cog(Schedule(client))
