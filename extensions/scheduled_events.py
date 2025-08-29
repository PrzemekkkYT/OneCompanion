from datetime import datetime, timezone, timedelta
from math import ceil
from typing import Optional, Literal
from peewee import IntegrityError

import discord
from discord import ui
from discord import app_commands
from discord.ext import commands, tasks
from discord.app_commands import locale_str

from orms.schedules import ScheduledEventNotifications, ScheduledEventRecurrence

from utils.utils import (
    parse_interval,
    timestamp,
    from_interval,
    small_traceback,
    interval_str_to_words,
)
from utils.whitecord import LVPagination, LVPage, Select, Button


class ScheduledEvents(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.translator = self.client.tree.translator
        self.post_notification.start()

    @tasks.loop(minutes=1)
    async def post_notification(self):
        for guild in self.client.guilds:
            notifications = ScheduledEventNotifications.select().where(
                ScheduledEventNotifications.guild_id == guild.id
            )
            for notification in notifications:
                event = guild.get_scheduled_event(notification.event_id)
                if not event:
                    continue
                now_ts = timestamp(datetime.now(tz=timezone.utc))
                noti_values = [
                    notification.noti_5m,
                    notification.noti_15m,
                    notification.noti_30m,
                    notification.noti_1h,
                    notification.noti_custom,
                ]

                noti_diffs = {n: abs(now_ts - n) for n in noti_values if n is not None}
                # Find the notification time with the lowest difference (closest to now)
                if not noti_diffs:
                    continue
                lowest_noti_diff = min(noti_diffs.items(), key=lambda x: x[1])
                # lowest_noti_diff is a tuple (noti_value, diff)
                if lowest_noti_diff[1] < 50:
                    channel = guild.get_channel(notification.channel_id)
                    if notification.role_id:
                        if notification.role_id != guild.id:
                            role_mention = f"<@&{notification.role_id}>"
                        else:
                            role_mention = "@everyone"
                    else:
                        role_mention = ""

                    interval_str = from_interval(
                        timestamp(event.start_time) - lowest_noti_diff[0]
                    )
                    await channel.send(
                        f"{role_mention}\n{event.name} starts in {interval_str_to_words(interval_str)}"
                    )

    @post_notification.before_loop
    async def before_post_notification(self):
        await self.client.wait_until_ready()

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        recurrence: ScheduledEventRecurrence | None = (
            ScheduledEventRecurrence.get_or_none(event_id=event.id)
        )
        if recurrence:
            recurrence.delete_instance()

    @commands.Cog.listener()
    async def on_scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ):
        if after.status in [discord.EventStatus.completed, discord.EventStatus.ended]:
            # print(f"Event {after.name} completed")

            recurrence: ScheduledEventRecurrence | None = (
                ScheduledEventRecurrence.get_or_none(event_id=after.id)
            )

            if recurrence:
                recurrence_interval = parse_interval(recurrence.recurrence_rule)

                new_event: discord.ScheduledEvent = (
                    await after.guild.create_scheduled_event(
                        name=after.name,
                        description=after.description,
                        start_time=after.start_time
                        + timedelta(seconds=recurrence_interval),
                        end_time=(
                            after.end_time + timedelta(seconds=recurrence_interval)
                            if after.end_time
                            else None
                        ),
                        channel=(
                            after.channel if after.channel else discord.utils.MISSING
                        ),
                        privacy_level=discord.PrivacyLevel.guild_only,
                        entity_type=after.entity_type,
                        location=(
                            after.location if after.location else discord.utils.MISSING
                        ),
                        image=(
                            await after.cover_image.read()
                            if after.cover_image
                            else discord.utils.MISSING
                        ),
                    )
                )

                ScheduledEventRecurrence.update(event_id=new_event.id).where(
                    ScheduledEventRecurrence.event_id == recurrence.event_id
                ).execute()

                notification: ScheduledEventNotifications = (
                    ScheduledEventNotifications.get_or_none(event_id=after.id)
                )

                if notification:
                    new_event_starttime = timestamp(new_event.start_time)
                    noti_custom_interval = (
                        notification.event_time - notification.noti_custom
                        if notification.noti_custom
                        else None
                    )

                    notification.event_id = new_event.id
                    notification.event_time = new_event_starttime
                    notification.noti_5m = (
                        new_event_starttime - parse_interval("5m")
                        if notification.noti_5m
                        else None
                    )
                    notification.noti_15m = (
                        new_event_starttime - parse_interval("15m")
                        if notification.noti_15m
                        else None
                    )
                    notification.noti_30m = (
                        new_event_starttime - parse_interval("30m")
                        if notification.noti_30m
                        else None
                    )
                    notification.noti_1h = (
                        new_event_starttime - parse_interval("1h")
                        if notification.noti_1h
                        else None
                    )
                    notification.noti_custom = (
                        new_event_starttime - noti_custom_interval
                    )

    events_group = app_commands.Group(
        name="event", description=locale_str("event_description")
    )
    events_group.default_permissions = discord.Permissions(manage_events=True)

    @events_group.command()
    async def notification(self, interaction: discord.Interaction):
        events = interaction.guild.scheduled_events
        now = datetime.now(tz=timezone.utc)
        upcoming_events: list[discord.ScheduledEvent] = [
            event
            for event in events
            if event.start_time and 0 < (event.start_time - now).total_seconds()
        ]

        async def select_event(button_interaction: discord.Interaction):
            await button_interaction.response.defer()
            event_id = int(button_interaction.data["custom_id"].split("__")[-1])
            selected_event = button_interaction.guild.get_scheduled_event(event_id)

            print(selected_event.id)

            view = ReminderOffsetSetter(
                event=selected_event,
                interaction=interaction,
            )

            await interaction.edit_original_response(view=view)

        pages = [
            LVPage(
                container=discord.ui.Container(
                    *(
                        ui.Section(
                            ui.TextDisplay(
                                f"### {event.name}\n└ {event.start_time.strftime('%d-%m-%Y %H:%M UTC')}"
                            ),
                            accessory=Button(
                                label="Set Reminders",
                                custom_id=f"set_reminders__{event.id}",
                                style=discord.ButtonStyle.secondary,
                                callback=select_event,
                            ),
                        )
                        for event in page
                    )
                )
            )
            for page in [
                upcoming_events[i : i + 5] for i in range(0, len(upcoming_events), 5)
            ]
        ]

        if not upcoming_events:
            await interaction.followup.send(
                content=await interaction.translate(
                    locale=interaction.locale,
                    string=locale_str("schedule_no_upcoming_events"),
                )
            )
            return

        async def on_page_timeout():
            try:
                await interaction.delete_original_response()
                await interaction.followup.send(content="The pagination has timed out.")
            except:
                pass

        pagination = LVPagination(
            pages=pages, interaction=interaction, on_timeout=on_page_timeout
        )
        await pagination.send_paginator()

    @events_group.command()
    async def recurrence(self, interaction: discord.Interaction):
        events = interaction.guild.scheduled_events
        now = datetime.now(tz=timezone.utc)
        upcoming_events: list[discord.ScheduledEvent] = [
            event
            for event in events
            if event.start_time and 0 < (event.start_time - now).total_seconds()
        ]

        async def select_event(button_interaction: discord.Interaction):
            # await button_interaction.response.defer()
            event_id = int(button_interaction.data["custom_id"].split("__")[-1])
            selected_event = button_interaction.guild.get_scheduled_event(event_id)

            print(selected_event.id)

            modal = ReminderRecurrenceSetter(interaction, selected_event)

            await button_interaction.response.send_modal(modal)

        print([event.id for event in upcoming_events])

        recurrences_model = ScheduledEventRecurrence.select().where(
            ScheduledEventRecurrence.event_id << [event.id for event in upcoming_events]
        )
        recurrences = {r.event_id: r.recurrence_rule for r in recurrences_model}

        pages = [
            LVPage(
                container=discord.ui.Container(
                    *(
                        ui.Section(
                            ui.TextDisplay(
                                f"### {event.name}\n└ {event.start_time.strftime('%d-%m-%Y %H:%M UTC')}\n└ Recurrence rule: `{recurrences.get(event.id, 'No recurrence')}`"
                            ),
                            accessory=Button(
                                label="Set Recurrence",
                                custom_id=f"set_recurrence__{event.id}",
                                style=discord.ButtonStyle.secondary,
                                callback=select_event,
                            ),
                        )
                        for event in page
                    )
                )
            )
            for page in [
                upcoming_events[i : i + 5] for i in range(0, len(upcoming_events), 5)
            ]
        ]

        if not upcoming_events:
            await interaction.followup.send(
                content=await interaction.translate(
                    locale=interaction.locale,
                    string=locale_str("schedule_no_upcoming_events"),
                )
            )
            return

        async def on_page_timeout():
            try:
                await interaction.delete_original_response()
                await interaction.followup.send(content="The pagination has timed out.")
            except:
                pass

        pagination = LVPagination(
            pages=pages, interaction=interaction, on_timeout=on_page_timeout
        )
        await pagination.send_paginator()

    @events_group.command()
    async def create(
        self,
        interaction: discord.Interaction,
        template: Literal[
            "fortress",
            "stronghold",
            "foundry",
            "canyon_clash",
            "sunfire_castle",
            "crazy_joe",
            "mercenary_prestige",
        ],
        datetime: str,
        info: str,
    ):
        pass


class ReminderOffsetSetter(ui.LayoutView):
    @property
    def event(self):
        return self.__event

    @property
    def selected_reminders(self):
        return self.__selected_reminders

    @property
    def interaction(self):
        return self.__interaction

    def __init__(
        self,
        event: discord.ScheduledEvent,
        interaction: discord.Interaction,
    ):
        super().__init__()
        self.__interaction = interaction
        self.__event = event

        self.existing_notification: ScheduledEventNotifications | None = (
            ScheduledEventNotifications.get_or_none(
                guild_id=interaction.guild.id, event_id=event.id
            )
        )

        self.__selected_reminders: dict[str, int | bool] = {
            "5m": False,
            "10m": False,
            "15m": False,
            "30m": False,
            "1h": False,
            "Custom": 0,
        }

        self.selected_channel: discord.abc.GuildChannel | None = (
            interaction.guild.get_channel(self.existing_notification.channel_id)
            if self.existing_notification
            else None
        )
        self.selected_role: discord.Role | None = (
            interaction.guild.get_role(self.existing_notification.role_id)
            if self.existing_notification
            else None
        )

        self.title = ui.TextDisplay(f"# Set Reminder Offsets\n## {event.name}")
        self.description = ui.TextDisplay(
            f"Using the button underneath, select when the event reminder should be send,\nthen click 'Confirm' to save\n*eg. 5m means 5 minutes before the event*"
        )

        self.error_message = ui.TextDisplay("​")

        self.guild_channel_select = ReminderChannelSelect(self).new(
            self.existing_notification
        )
        self.guild_role_select = ReminderRoleSelect(self).new(
            self.existing_notification
        )

        self.offset_buttons = ReminderOffsetButtons(
            self, interaction, self.existing_notification
        )
        self.control_buttons = ReminderOffsetControlButtons(self, interaction)

        if event.cover_image:
            self.image = discord.MediaGalleryItem(
                media=event.cover_image.with_size(512).url
            )
        else:
            self.image = None

        self.container = ui.Container(
            self.title,
            *([ui.MediaGallery(self.image)] if self.image else []),
            self.description,
            self.error_message,
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            self.guild_channel_select,
            self.guild_role_select,
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            self.offset_buttons,
            self.control_buttons,
        )
        self.add_item(self.container)

    async def on_timeout(self) -> None:
        try:
            await self.__interaction.delete_original_response()
            await self.__interaction.followup.send(
                content="The reminder configuration has timed out."
            )
        except Exception as e:
            print(f"Error editing response: {e}")

    async def update_view(
        self,
        title: ui.TextDisplay | None = None,
        image: discord.MediaGalleryItem | None = None,
        description: ui.TextDisplay | None = None,
        error_message: ui.TextDisplay | None = None,
        channel_select: ui.Section | ui.ChannelSelect | None = None,
        role_select: ui.Section | ui.RoleSelect | None = None,
        offset_buttons: ui.ActionRow | None = None,
        control_buttons: ui.ActionRow | None = None,
    ):
        self.clear_items()
        self.title = title if title else self.title
        self.image = image if image else self.image
        self.description = description if description else self.description
        self.error_message = error_message if error_message else self.error_message
        self.guild_channel_select = (
            channel_select if channel_select else self.guild_channel_select
        )
        self.guild_role_select = role_select if role_select else self.guild_role_select
        self.offset_buttons = offset_buttons if offset_buttons else self.offset_buttons
        self.control_buttons = (
            control_buttons if control_buttons else self.control_buttons
        )

        self.container = ui.Container(
            self.title,
            *([ui.MediaGallery(self.image)] if self.image else []),
            self.description,
            self.error_message,
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            self.guild_channel_select,
            self.guild_role_select,
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            self.offset_buttons,
            self.control_buttons,
        )

        self.add_item(self.container)

        await self.__interaction.edit_original_response(view=self)

    async def set_error(self, error_message: str):
        self.error_message.content = f"## Error: `{error_message}`"
        await self.__interaction.edit_original_response(view=self)


class ReminderOffsetButtons(ui.ActionRow):
    class ReminderOffsetButton(ui.Button):
        def __init__(self, parent: "ReminderOffsetButtons", **kwargs):
            self.__parent: ReminderOffsetButtons = parent
            super().__init__(**kwargs)

        async def callback(self, button_interaction: discord.Interaction):
            if button_interaction.data["custom_id"] == "event_remind_custom":
                if self.label == "Custom":
                    modal = ReminderOffsetModal(
                        self.__parent.interaction, self.__parent, self
                    )
                    await button_interaction.response.send_modal(modal)
                else:
                    await button_interaction.response.defer()
                    self.__parent.view.selected_reminders["Custom"] = 0
                    self.label = "Custom"
                    self.style = discord.ButtonStyle.secondary
            else:
                await button_interaction.response.defer()
                reminder = button_interaction.data["custom_id"].replace(
                    "event_remind_", ""
                )

                if self.__parent.view.selected_reminders[reminder]:
                    self.__parent.view.selected_reminders[reminder] = False
                    self.style = discord.ButtonStyle.secondary
                else:
                    self.__parent.view.selected_reminders[reminder] = True
                    self.style = discord.ButtonStyle.primary
            # await self.__parent.interaction.edit_original_response(
            #     view=self.__parent.view
            # )
            await self.__parent.view.update_view(offset_buttons=self.__parent)

    @property
    def view(self):
        return self.__view

    @property
    def interaction(self):
        return self.__interaction

    def __init__(
        self,
        view: ReminderOffsetSetter,
        interaction: discord.Interaction,
        existing_notification: ScheduledEventNotifications | None,
    ):
        self.__view = view
        self.__interaction = interaction

        # existing_notifications_select = ScheduledEventNotifications.select().where(
        #     (ScheduledEventNotifications.guild_id == interaction.guild.id)
        #     & (ScheduledEventNotifications.event_id == view.event.id)
        # )

        noti_5m = existing_notification.noti_5m if existing_notification else None
        noti_15m = existing_notification.noti_15m if existing_notification else None
        noti_30m = existing_notification.noti_30m if existing_notification else None
        noti_1h = existing_notification.noti_1h if existing_notification else None
        custom_interval = (
            existing_notification.noti_custom if existing_notification else None
        )
        custom = (
            from_interval(timestamp(self.__view.event.start_time) - custom_interval)
            if custom_interval
            else None
        )

        self.__view.selected_reminders["5m"] = bool(noti_5m)
        self.__view.selected_reminders["15m"] = bool(noti_15m)
        self.__view.selected_reminders["30m"] = bool(noti_30m)
        self.__view.selected_reminders["1h"] = bool(noti_1h)
        self.__view.selected_reminders["Custom"] = custom if custom else 0

        # TODO
        # Wyjebać odpowiednie interwały przy odznaczeniu ich.
        self.buttons = [
            self.ReminderOffsetButton(
                self,
                label="5m",
                custom_id="event_remind_5m",
                style=(
                    discord.ButtonStyle.primary
                    if noti_5m
                    else discord.ButtonStyle.secondary
                ),
            ),
            self.ReminderOffsetButton(
                self,
                label="15m",
                custom_id="event_remind_15m",
                style=(
                    discord.ButtonStyle.primary
                    if noti_15m
                    else discord.ButtonStyle.secondary
                ),
            ),
            self.ReminderOffsetButton(
                self,
                label="30m",
                custom_id="event_remind_30m",
                style=(
                    discord.ButtonStyle.primary
                    if noti_30m
                    else discord.ButtonStyle.secondary
                ),
            ),
            self.ReminderOffsetButton(
                self,
                label="1h",
                custom_id="event_remind_1h",
                style=(
                    discord.ButtonStyle.primary
                    if noti_1h
                    else discord.ButtonStyle.secondary
                ),
            ),
            self.ReminderOffsetButton(
                self,
                label=(custom if custom else "Custom"),
                custom_id="event_remind_custom",
                style=(
                    discord.ButtonStyle.primary
                    if custom_interval
                    else discord.ButtonStyle.secondary
                ),
            ),
        ]

        super().__init__(*self.buttons)


class ReminderOffsetModal(ui.Modal):
    def __init__(
        self,
        interaction: discord.Interaction,
        actionrow: ReminderOffsetButtons,
        button: discord.ui.Button,
    ):
        super().__init__(title="Custom Reminder Offset")
        self.__interaction = interaction
        self.actionrow = actionrow
        self.button = button

    offset = ui.TextInput(
        label="Reminder Offset",
        placeholder="1w 2d 3h 4m",
        required=True,
    )

    async def on_submit(self, submit_interaction: discord.Interaction):
        await submit_interaction.response.defer()
        _offset = self.offset.value
        interval = parse_interval(_offset)
        if not interval:
            self.actionrow.view.error_message.content = (
                "## Error: `Invalid time format. Please use the format: 1w 2d 3h 4m`"
            )
        else:
            self.actionrow.view.error_message.content = "​"
            if self.actionrow.view.selected_reminders["Custom"]:
                self.actionrow.view.selected_reminders["Custom"] = 0
                self.button.style = discord.ButtonStyle.secondary
                self.button.label = "Custom"
            else:
                self.actionrow.view.selected_reminders["Custom"] = _offset
                self.button.style = discord.ButtonStyle.primary
                self.button.label = _offset

        print(self.actionrow.view.selected_reminders)
        await self.actionrow.view.update_view(offset_buttons=self.actionrow)


class ReminderOffsetControlButtons(ui.ActionRow):
    def __init__(self, view: ReminderOffsetSetter, interaction: discord.Interaction):
        self.__view = view
        self.__interaction = interaction
        super().__init__()

    @ui.button(
        custom_id="event_remind_confirm",
        label="Confirm",
        style=discord.ButtonStyle.green,
    )
    async def event_remind_confirm(
        self, button_interaction: discord.Interaction, button: discord.ui.Button
    ):
        await button_interaction.response.defer()
        event_starttime = timestamp(self.__view.event.start_time)

        # print(f"{self.__view.guild_channel_select.values=}")
        # print(f"{self.__view.guild_role_select.values=}")

        if not self.__view.selected_channel:
            await self.__view.set_error("Please select a channel.")
            return

        notification: ScheduledEventNotifications | None = (
            ScheduledEventNotifications.get_or_none(
                guild_id=self.__interaction.guild.id,
                event_id=self.__view.event.id,
            )
        )

        if notification:
            notification.channel_id = self.__view.selected_channel.id
            notification.role_id = (
                self.__view.selected_role.id if self.__view.selected_role else None
            )

            notification.noti_5m = (
                event_starttime - parse_interval("5m")
                if self.__view.selected_reminders["5m"]
                else None
            )
            notification.noti_15m = (
                event_starttime - parse_interval("15m")
                if self.__view.selected_reminders["15m"]
                else None
            )
            notification.noti_30m = (
                event_starttime - parse_interval("30m")
                if self.__view.selected_reminders["30m"]
                else None
            )
            notification.noti_1h = (
                event_starttime - parse_interval("1h")
                if self.__view.selected_reminders["1h"]
                else None
            )
            notification.noti_custom = (
                event_starttime
                - parse_interval(self.__view.selected_reminders["Custom"])
                if self.__view.selected_reminders["Custom"]
                else None
            )
            notification.save()
        else:

            notification = ScheduledEventNotifications.create(
                event_id=self.__view.event.id,
                guild_id=self.__interaction.guild.id,
                event_time=event_starttime,
                channel_id=self.__view.selected_channel.id,
                role_id=(
                    self.__view.selected_role.id if self.__view.selected_role else None
                ),
                noti_5m=(
                    event_starttime - parse_interval("5m")
                    if self.__view.selected_reminders["5m"]
                    else None
                ),
                noti_15m=(
                    event_starttime - parse_interval("15m")
                    if self.__view.selected_reminders["15m"]
                    else None
                ),
                noti_30m=(
                    event_starttime - parse_interval("30m")
                    if self.__view.selected_reminders["30m"]
                    else None
                ),
                noti_1h=(
                    event_starttime - parse_interval("1h")
                    if self.__view.selected_reminders["1h"]
                    else None
                ),
                noti_custom=(
                    event_starttime
                    - parse_interval(self.__view.selected_reminders["Custom"])
                    if self.__view.selected_reminders["Custom"]
                    else None
                ),
            )
            notification.save()
            print(
                f"Set reminders for event {self.__view.event.name} ({self.__view.event.id}) in guild {self.__interaction.guild.name} ({self.__interaction.guild.id})\n"
                + ", ".join(
                    [
                        reminder
                        for reminder, value in self.__view.selected_reminders.items()
                        if value
                    ]
                )
            )
        confirmation_view = discord.ui.LayoutView()
        confirmation_view.add_item(
            ui.Container(
                ui.TextDisplay(
                    f"## Reminders set for event {self.__view.event.name}:\n"
                    + "\n".join(
                        [
                            f"- {reminder} before ({parse_interval(reminder)} seconds)"
                            for reminder, value in self.__view.selected_reminders.items()
                            if value and parse_interval(reminder) is not None
                        ]
                    )
                    + (
                        f"\n- Custom {self.__view.selected_reminders['Custom']} before ({parse_interval(self.__view.selected_reminders['Custom'])} seconds)"
                        if self.__view.selected_reminders["Custom"]
                        else ""
                    )
                ),
                ui.TextDisplay(
                    f"### Selected Channel: {self.__view.selected_channel.mention}"
                ),
                *(
                    [
                        ui.TextDisplay(
                            f"### Selected Role: {self.__view.selected_role.mention}"
                        )
                    ]
                    if self.__view.selected_role
                    else []
                ),
            )
        )
        await self.__interaction.edit_original_response(view=confirmation_view)

    @ui.button(
        custom_id="event_remind_cancel", label="Cancel", style=discord.ButtonStyle.red
    )
    async def event_remind_cancel(
        self, button_interaction: discord.Interaction, button: discord.ui.Button
    ):
        await button_interaction.response.defer()
        print("Cancelling reminders")
        await self.__interaction.delete_original_response()
        await self.__interaction.followup.send(
            "Reminders config cancelled.", ephemeral=True
        )


class ReminderChannelSelect:
    class Resetter(ui.Section):
        class ResetButton(ui.Button):
            def __init__(self, parent: "ReminderChannelSelect.Resetter"):
                self.__parent = parent
                super().__init__(label="Reset Channel", style=discord.ButtonStyle.red)

            async def callback(self, button_interaction: discord.Interaction):
                await button_interaction.response.defer()
                print("Resetting channel selection")
                await self.__parent.parent.reset_selection()

        @property
        def parent(self):
            return self.__parent

        def __init__(self, parent: "ReminderChannelSelect"):
            self.__parent = parent
            super().__init__(
                ui.TextDisplay(
                    f"## Selected Channel: {self.__parent.selected_channel.mention}"
                ),
                accessory=self.ResetButton(self),
            )

    class ChannelSelectActionRow(ui.ActionRow):
        class ChannelSelect(ui.ChannelSelect):
            def __init__(self, parent: "ReminderChannelSelect"):
                self.__parent = parent
                super().__init__(placeholder="Select a channel")

            async def callback(self, select_interaction: discord.Interaction):
                await select_interaction.response.defer()
                channel = select_interaction.guild.get_channel(
                    int(select_interaction.data["values"][0])
                )
                print(channel.mention)
                await self.__parent.select_channel(channel)

        def __init__(self, parent: "ReminderChannelSelect"):
            super().__init__(self.ChannelSelect(parent))

    @property
    def view(self):
        return self.__view

    @property
    def selected_channel(self) -> Optional[discord.abc.GuildChannel]:
        return self.__view.selected_channel

    def __init__(self, view: ReminderOffsetSetter):
        self.__view = view
        # return self.ChannelSelectActionRow(self)

    def new(self, existing_notification: ScheduledEventNotifications | None):
        if existing_notification and existing_notification.channel_id:
            return self.Resetter(self)
        return self.ChannelSelectActionRow(self)

    async def select_channel(self, channel: discord.abc.GuildChannel):
        self.__view.selected_channel = channel
        resetter = self.Resetter(self)
        self.__view.guild_channel_select = resetter
        await self.__view.update_view(channel_select=resetter)

    async def reset_selection(self):
        self.__view.selected_channel = None
        await self.__view.update_view(channel_select=self.ChannelSelectActionRow(self))


class ReminderRoleSelect:
    class Resetter(ui.Section):
        class ResetButton(ui.Button):
            def __init__(self, parent: "ReminderRoleSelect.Resetter"):
                self.__parent = parent
                super().__init__(label="Reset Role", style=discord.ButtonStyle.red)

            async def callback(self, button_interaction: discord.Interaction):
                await button_interaction.response.defer()
                print("Resetting role selection")
                await self.__parent.parent.reset_selection()

        @property
        def parent(self):
            return self.__parent

        def __init__(self, parent: "ReminderRoleSelect"):
            self.__parent = parent
            super().__init__(
                ui.TextDisplay(f"## Selected Role: {self.__parent.selected_role.name}"),
                accessory=self.ResetButton(self),
            )

    class RoleSelectActionRow(ui.ActionRow):
        class RoleSelect(ui.Select):
            def __init__(self, parent: "ReminderRoleSelect"):
                self.__parent = parent
                super().__init__(
                    placeholder="Select a role",
                    options=[
                        discord.SelectOption(label="everyone", value="-1"),
                        *[
                            discord.SelectOption(label=role.name, value=str(role.id))
                            for role in parent.view.interaction.guild.roles[:25]
                            if role.mentionable
                            and role != parent.view.interaction.guild.default_role
                        ],
                    ],
                )

            async def callback(self, select_interaction: discord.Interaction):
                await select_interaction.response.defer()
                role_id = int(select_interaction.data["values"][0])

                if role_id != -1:
                    role = select_interaction.guild.get_role(role_id)
                else:
                    role = select_interaction.guild.default_role

                await self.__parent.select_role(role)

        def __init__(self, parent: "ReminderRoleSelect"):
            super().__init__(self.RoleSelect(parent))

    @property
    def view(self):
        return self.__view

    @property
    def selected_role(self) -> Optional[discord.abc.Role]:
        return self.__view.selected_role

    def __init__(self, view: ReminderOffsetSetter):
        self.__view = view
        # return self.ChannelSelectActionRow(self)

    def new(self, existing_notification: ScheduledEventNotifications | None):
        if existing_notification and existing_notification.role_id:
            return self.Resetter(self)
        return self.RoleSelectActionRow(self)

    async def select_role(self, role: discord.abc.Role):
        self.__view.selected_role = role
        resetter = self.Resetter(self)
        self.__view.guild_role_select = resetter
        await self.__view.update_view(role_select=resetter)

    async def reset_selection(self):
        self.__view.selected_role = None
        await self.__view.update_view(role_select=self.RoleSelectActionRow(self))


class ReminderRecurrenceSetter(ui.Modal):
    def __init__(self, interaction: discord.Interaction, event: discord.ScheduledEvent):
        self.__interaction = interaction
        self.__event = event

        super().__init__(title="Set Reminder Recurrence")

    recurrence_rule = ui.Label(
        text="Set the recurrence rule for this reminder.",
        description="Use the format '1w 2d 3h 4m'. \n(w - week, d - day, h - hour, m - minute)",
        component=ui.TextInput(placeholder="1w 2d 3h 4m", required=True),
    )

    async def on_submit(self, modal_interaction: discord.Interaction):
        await modal_interaction.response.defer()
        rule = self.recurrence_rule.component.value

        try:
            recurrence: ScheduledEventRecurrence = ScheduledEventRecurrence.create(
                event_id=self.__event.id, recurrence_rule=rule
            )
            text = f"### Recurrence rule has been set to {rule}"
        except IntegrityError:
            recurrence = ScheduledEventRecurrence.get(event_id=self.__event.id)
            old_rule = recurrence.recurrence_rule
            recurrence.recurrence_rule = rule
            recurrence.save()
            text = f"### Recurrence rule has been updated from `{old_rule}` to `{rule}`"
        except Exception as e:
            text = f"### Failed to set recurrence rule.\nError: {small_traceback(e)}"

        view = ui.LayoutView()
        container = ui.Container(ui.TextDisplay(f"## {self.__event.name}\n{text}"))
        view.add_item(container)

        await self.__interaction.edit_original_response(view=view)


async def setup(client: commands.Bot):
    await client.add_cog(ScheduledEvents(client))
