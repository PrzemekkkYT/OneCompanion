import json
from typing import Callable, Optional, Union, List, Any
from datetime import datetime

import discord
from discord import ui
from discord.app_commands import TranslationContextTypes, Translator, locale_str
from discord.app_commands.translator import OtherTranslationContext
from discord.types.embed import EmbedType
from discord import ButtonStyle, Emoji, PartialEmoji
from discord.enums import Locale

UNSET: Any = object()


class EmbedError(Exception): ...


class WhiteTranslator(Translator):
    def __init__(self):
        self.translations_path = "./langs.json"
        self.translations = None

    async def load(self) -> None:
        print("load translation")
        with open(self.translations_path, "r", encoding="utf-8") as f:
            self.translations = json.load(f)

    async def unload(self) -> None:
        self.translations = None

    async def translate(
        self,
        string: locale_str,
        locale: Locale = Locale.american_english,
        context: Optional[TranslationContextTypes] = OtherTranslationContext,
    ):
        return self.translate_sync(string=string, locale=locale, context=context)

    def translate_sync(
        self,
        string: locale_str,
        locale: Locale = Locale.american_english,
        context: Optional[TranslationContextTypes] = OtherTranslationContext,
    ) -> Optional[str]:
        if self.translations is None:
            return str(string)

        if str(locale) not in self.translations:
            locale = Locale.american_english

        if str(string) not in self.translations[str(locale)]:
            return str(string)

        ret_string = self.translations[str(locale)][str(string)]
        for arg, val in string.extras.items():
            ret_string = ret_string.replace(f"{{{arg}}}", val)

        return ret_string


class EmbedField:
    def __init__(self, name: str, value: str, inline: bool = False):
        self.name = name
        self.value = value
        self.inline = inline


class EmbedAuthor:
    def __init__(
        self, name: str, icon_url: Optional[str] = None, url: Optional[str] = None
    ):
        self.name = name
        self.icon_url = icon_url
        self.url = url


class Embed(discord.Embed):
    """
    author: dict("name", Optional["icon_url"], Optional["url"])
    fields: list(dict("name", "value", "inline"))
    """

    def __init__(
        self,
        *,
        translator: WhiteTranslator,
        locale: Optional[Union[str, Locale]] = Locale.american_english,
        colour: Optional[Union[int, discord.Colour]] = None,
        color: Optional[Union[int, discord.Colour]] = None,
        title: Optional[Any] = None,
        embed_type: EmbedType = "rich",
        url: Optional[Any] = None,
        description: Optional[Any] = None,
        timestamp: Optional[datetime] = None,
        fields: Optional[List[EmbedField]] = None,
        thumbnail: Optional[Any] = None,
        footer: Optional[Any] = None,
        author: Optional[EmbedAuthor] = None,
        image: Optional[Any] = None,
    ):
        if not translator or not getattr(translator, "translations", None):
            raise EmbedError
        self.translator = translator
        self.locale = str(locale)

        super().__init__(
            colour=colour,
            color=color,
            title=translator.translate_sync(title, locale=locale),
            type=embed_type,
            url=url,
            description=translator.translate_sync(description, locale=locale),
            timestamp=timestamp,
        )
        if fields:
            for field in fields:
                _name = translator.translate_sync(field.name, locale=locale)
                _value = translator.translate_sync(field.value, locale=locale)

                self.add_field(name=_name, value=_value, inline=field.inline)

                # self.add_field(
                #     name=field["name"], value=field["value"], inline=field["inline"]
                # )
        if thumbnail:
            self.set_thumbnail(url=thumbnail)
        if footer:
            self.set_footer(text=translator.translate_sync(footer, locale=locale))
        if author:
            self.set_author(
                name=translator.translate_sync(author.name, locale=locale),
                icon_url=author.icon_url,
                url=author.url,
            )
        if image:
            self.set_image(url=image)


class View(discord.ui.View):
    def __init__(
        self,
        translator: WhiteTranslator,
        locale: Optional[Union[str, Locale]] = Locale.american_english,
        timeout: float | None = 180,
    ):
        self.translator = translator
        self.locale = locale

        super().__init__(timeout=timeout)


class Button(discord.ui.Button):
    def __init__(
        self,
        label: str = None,
        custom_id: Optional[str] = None,
        disabled: bool = False,
        style: ButtonStyle = ButtonStyle.secondary,
        emoji: Optional[Union[str, Emoji, PartialEmoji]] = None,
        row: Optional[int] = None,
        callback: Optional[Any] = None,
    ):
        if callback:
            self.callback = callback

        super().__init__(
            label=label,
            custom_id=custom_id,
            disabled=disabled,
            style=style,
            emoji=emoji,
            row=row,
        )


class Select(discord.ui.Select):
    def __init__(
        self,
        *,
        custom_id: str,
        options: List[discord.SelectOption],
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        row: Optional[int] = None,
        callback=None,
    ):
        if callback:
            self.callback = callback

        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            disabled=disabled,
            row=row,
        )


class Page:
    def __init__(
        self,
        name: str,
        embed: discord.Embed,
        page_items: List[discord.ui.Item] = [],
    ) -> None:

        self.name = name
        self.embed = embed
        self.page_id_num = 0
        self.page_items = page_items

    @property
    def page_id(self):
        return f"page_{self.page_id_num}"


class Pagination:
    class Page_Button(discord.ui.Button):
        def __init__(
            self,
            *,
            style: ButtonStyle = ButtonStyle.secondary,
            label: str | None = None,
            disabled: bool = False,
            custom_id: str | None = None,
            url: str | None = None,
            emoji: str | Emoji | PartialEmoji | None = None,
            row: int | None = None,
            paginator,
        ):
            self.paginator = paginator
            super().__init__(
                style=style,
                label=label,
                disabled=disabled,
                custom_id=custom_id,
                url=url,
                emoji=emoji,
                row=row,
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            await self.paginator.set_page(self.custom_id)

    def __init__(
        self,
        pages: List[Page],
        translator: WhiteTranslator,
        locale: Optional[Union[str, Locale]] = Locale.american_english,
        additional_items: List[discord.ui.Item] = [],
    ) -> None:
        self.pages = pages
        self.current_page = 0
        self.additional_items = additional_items

        self.translator = translator
        self.locale = locale

        self.interaction: discord.Interaction
        self.message: discord.Message

    async def build_view(self):
        view = discord.ui.View(timeout=None)

        view.add_item(
            self.Page_Button(
                custom_id="first_page",
                label="<<",
                disabled=self.current_page == 0,
                style=ButtonStyle.primary,
                paginator=self,
                row=0,
            )
        )
        view.add_item(
            self.Page_Button(
                custom_id="prev_page",
                label="<",
                disabled=self.current_page == 0,
                style=ButtonStyle.primary,
                paginator=self,
                row=0,
            )
        )
        view.add_item(
            self.Page_Button(
                custom_id="page_num",
                label=f"{self.current_page + 1} / {len(self.pages)}",
                disabled=True,
                style=ButtonStyle.secondary,
                paginator=self,
                row=0,
            )
        )
        view.add_item(
            self.Page_Button(
                custom_id="next_page",
                label=">",
                disabled=self.current_page == len(self.pages) - 1,
                style=ButtonStyle.primary,
                paginator=self,
                row=0,
            )
        )
        view.add_item(
            self.Page_Button(
                custom_id="last_page",
                label=">>",
                disabled=self.current_page == len(self.pages) - 1,
                style=ButtonStyle.primary,
                paginator=self,
                row=0,
            )
        )

        for item in self.additional_items:
            view.add_item(item)

        for page_item in self.pages[self.current_page].page_items:
            view.add_item(page_item)

        return view

    async def create(self):
        return self.pages[self.current_page].embed, await self.build_view()

    async def set_page(self, page_id):
        if page_id in ["prev_page", "next_page"]:
            if page_id == "prev_page":
                self.current_page -= 1
            else:
                self.current_page += 1
            page = self.pages[self.current_page]
        elif page_id in ["first_page", "last_page"]:
            if page_id == "first_page":
                self.current_page = 0
            else:
                self.current_page = len(self.pages) - 1
            page = self.pages[self.current_page]
        else:
            page = next(p for p in self.pages if p.page_id == page_id)

            self.current_page = page.page_id_num
        # try:
        #     await self.interaction.delete_original_response()
        # except discord.errors.NotFound:
        #     await self.message.delete()
        # self.message = await self.interaction.followup.send(
        #     embed=page.embed, view=await self.build_view(), ephemeral=True
        # )
        # self.message = await self.interaction.response.edit_message(
        #     embed=page.embed, view=await self.build_view()
        # )
        # msg = await self.interaction.original_response()
        # self.message = await msg.edit(embed=page.embed, view=await self.build_view())
        # self.message = await self.message.edit(
        #     embed=page.embed, view=await self.build_view()
        # )
        self.message = await self.interaction.edit_original_response(
            embed=page.embed, view=await self.build_view()
        )


class LVPage:
    def __init__(self, container: discord.ui.Container):
        self.container = container


class LVPagination:
    class LVPage_Button(discord.ui.Button):
        def __init__(
            self,
            paginator: "LVPagination",
            custom_id: str,
            label: str,
            style=ButtonStyle.primary,
            disabled: bool = False,
        ):
            super().__init__(
                custom_id=custom_id, label=label, style=style, disabled=disabled
            )
            self.paginator = paginator

        async def callback(self, button_interaction: discord.Interaction):
            await button_interaction.response.defer()
            await self.paginator.set_page(self.custom_id)

    class LVPage_ControlButtons(discord.ui.ActionRow):
        def __init__(self, paginator: "LVPagination") -> None:
            self.paginator = paginator

            buttons = [
                self.paginator.LVPage_Button(
                    paginator=self.paginator,
                    custom_id="first_page",
                    label="<<",
                    disabled=True,
                ),
                self.paginator.LVPage_Button(
                    paginator=self.paginator,
                    custom_id="prev_page",
                    label="<",
                    disabled=True,
                ),
                self.paginator.LVPage_Button(
                    paginator=self.paginator,
                    custom_id="current_page",
                    label=f"{self.paginator.current_page + 1} / {len(self.paginator.pages)}",
                    style=ButtonStyle.secondary,
                    disabled=True,
                ),
                self.paginator.LVPage_Button(
                    paginator=self.paginator,
                    custom_id="next_page",
                    label=">",
                    disabled=(len(self.paginator.pages) == 1),
                ),
                self.paginator.LVPage_Button(
                    paginator=self.paginator,
                    custom_id="last_page",
                    label=">>",
                    disabled=(len(self.paginator.pages) == 1),
                ),
            ]

            super().__init__(*buttons)

        def update_buttons(self):
            for button in self.children:
                match button.custom_id:
                    case "first_page" | "prev_page":
                        button.disabled = self.paginator.current_page == 0
                    case "next_page" | "last_page":
                        button.disabled = (
                            self.paginator.current_page == len(self.paginator.pages) - 1
                        )
                    case "current_page":
                        button.label = f"{self.paginator.current_page + 1} / {len(self.paginator.pages)}"

    def __init__(
        self,
        pages: List[LVPage],
        interaction: discord.Interaction,
        timeout: int = 180,
        on_timeout: Callable[[], None] = None,
    ):
        self.__pages = pages
        self.__interaction = interaction

        self.timeout = timeout
        self.on_timeout = on_timeout

        self.current_page = 0

        self.control_buttons = self.LVPage_ControlButtons(self)

    @property
    def pages(self):
        return self.__pages

    async def send_paginator(self):
        await self.__interaction.response.send_message(view=await self.build_view())

    async def build_view(self):
        container = self.__pages[self.current_page].container.copy()
        container.add_item(discord.ui.Separator())
        container.add_item(self.control_buttons)
        view = discord.ui.LayoutView(timeout=self.timeout)
        view.on_timeout = self.on_timeout
        view.add_item(container)
        return view

    async def set_page(self, page_id: str):
        match page_id:
            case "first_page":
                self.current_page = 0
            case "prev_page":
                self.current_page -= 1
            case "next_page":
                self.current_page += 1
            case "last_page":
                self.current_page = len(self.__pages) - 1

        self.control_buttons.update_buttons()

        self.message = await self.__interaction.edit_original_response(
            view=await self.build_view()
        )


class WhiteView(ui.LayoutView):
    @property
    def interaction(self):
        return self.__interaction

    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.__interaction = interaction

        self.__title: ui.TextDisplay | str | None = None
        self.__subtitle: ui.TextDisplay | str | None = None
        self.__content: ui.TextDisplay | str | None = None
        self.__error: ui.TextDisplay | str | None = None
        self.__control_buttons: ui.ActionRow | None = None

        self.__container_color: discord.Colour | int | None = None

        self.add_item(self._build_container())

    async def on_timeout(self):
        await self.update_view(control_buttons=None, error="Timed out")
        return super().on_timeout()

    def _build_container(self):
        items: list[ui.Item] = []
        for value in (self.__title, self.__subtitle, self.__content, self.__error):
            if value is None:
                continue
            items.append(ui.TextDisplay(value) if isinstance(value, str) else value)
        items.append(ui.Separator())
        if self.__control_buttons is not None:
            items.append(self.__control_buttons)

        return ui.Container(*items, accent_color=self.__container_color)

    async def update_view(
        self,
        title: ui.TextDisplay | str | None | Any = UNSET,
        subtitle: ui.TextDisplay | str | None | Any = UNSET,
        content: ui.TextDisplay | str | None | Any = UNSET,
        error: ui.TextDisplay | str | None | Any = UNSET,
        control_buttons: ui.ActionRow | None | Any = UNSET,
        container_color: discord.Colour | int | None | Any = UNSET,
    ):
        # If *UNSET: parameter omitted -> keep current value
        # If None: explicitly clear/reset
        if title is not UNSET:
            self.__title = title
        if subtitle is not UNSET:
            self.__subtitle = subtitle
        if content is not UNSET:
            self.__content = content
        if error is not UNSET:
            self.__error = error
        if control_buttons is not UNSET:
            self.__control_buttons = control_buttons
        if container_color is not UNSET:
            self.__container_color = container_color

        # Rebuild the container with updated items
        self.clear_items()
        self.add_item(self._build_container())

        await self.__interaction.edit_original_response(view=self)
        return self
