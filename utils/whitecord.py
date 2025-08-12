from typing import Optional, Union, List, Any
from datetime import datetime

import discord
from discord.app_commands import Translator, locale_str
from discord.types.embed import EmbedType
from discord import ButtonStyle, Emoji, PartialEmoji
from discord.enums import Locale


class EmbedError(Exception): ...


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
        translator: Translator,
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
            title=self.str_translate(title),
            type=embed_type,
            url=url,
            description=self.str_translate(description),
            timestamp=timestamp,
        )
        if fields:
            for field in fields:
                _name = self.str_translate(field.name)
                _value = self.str_translate(field.value)

                self.add_field(name=_name, value=_value, inline=field.inline)

                # self.add_field(
                #     name=field["name"], value=field["value"], inline=field["inline"]
                # )
        if thumbnail:
            self.set_thumbnail(url=thumbnail)
        if footer:
            self.set_footer(text=self.str_translate(footer))
        if author:
            self.set_author(
                name=self.str_translate(author.name),
                icon_url=author.icon_url,
                url=author.url,
            )
        if image:
            self.set_image(url=image)

    def str_translate(self, string: Union[str, locale_str]):
        if isinstance(string, locale_str):
            msg = self.translator.translations[
                (
                    str(self.locale)
                    if str(self.locale) in self.translator.translations
                    else str(Locale.american_english)
                )
            ][string.message]

            return (
                msg.format(*string.extras["format"])
                if "format" in string.extras
                else msg
            )
        else:
            return string


class View(discord.ui.View):
    def __init__(
        self,
        translator: Translator,
        locale: Optional[Union[str, Locale]] = Locale.american_english,
        timeout: float | None = 180,
    ):
        self.translator = translator
        self.locale = locale

        super().__init__(timeout=timeout)

    def str_translate(self, string: Union[str, locale_str]):
        return (
            self.translator.translations[
                (
                    str(self.locale)
                    if str(self.locale) in self.translator.translations
                    else str(Locale.american_english)
                )
            ][string.message]
            if isinstance(string, locale_str)
            else string
        )


class Button(discord.ui.Button):
    def __init__(
        self,
        translator: Translator,
        locale: Optional[Union[str, Locale]] = Locale.american_english,
        label: Optional[Union[str, locale_str]] = None,
        custom_id: Optional[str] = None,
        disabled: bool = False,
        style: ButtonStyle = ButtonStyle.secondary,
        emoji: Optional[Union[str, Emoji, PartialEmoji]] = None,
        row: Optional[int] = None,
        callback: Optional[Any] = None,
    ):
        if not translator or not getattr(translator, "translations", None):
            raise EmbedError
        self.translator = translator
        self.locale = locale
        if callback:
            self.callback = callback

        super().__init__(
            label=self.str_translate(label),
            custom_id=custom_id,
            disabled=disabled,
            style=style,
            emoji=emoji,
            row=row,
        )

    def str_translate(self, string: Union[str, locale_str]):
        return (
            self.translator.translations[
                (
                    str(self.locale)
                    if str(self.locale) in self.translator.translations
                    else str(Locale.american_english)
                )
            ][string.message]
            if isinstance(string, locale_str)
            else string
        )


class Page:
    def __init__(self, name: str, embed: discord.Embed) -> None:

        self.name = name
        self.embed = embed
        self.page_id_num = 0

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
            await self.paginator.set_page(self.custom_id)

    def __init__(
        self,
        pages: List[Page],
        translator: Translator,
        locale: Optional[Union[str, Locale]] = Locale.american_english,
    ) -> None:
        self.pages = pages
        self.current_page = 0

        self.translator = translator
        self.locale = locale

        self.interaction: discord.Interaction
        self.message: discord.Message

    def build_view(self):
        view = discord.ui.View(timeout=None)

        for i, page in enumerate(self.pages):
            page.page_id_num = i
            view.add_item(
                self.Page_Button(
                    custom_id=page.page_id,
                    disabled=i == self.current_page,
                    label=self.str_translate(locale_str(page.name)),
                    style=(
                        discord.ButtonStyle.blurple
                        if i == self.current_page
                        else discord.ButtonStyle.green
                    ),
                    paginator=self,
                )
            )

        return view

    def create(self):
        return self.pages[self.current_page].embed, self.build_view()

    async def set_page(self, page_id):
        page = next(p for p in self.pages if p.page_id == page_id)

        self.current_page = page.page_id_num
        try:
            await self.interaction.delete_original_response()
        except discord.errors.NotFound:
            await self.message.delete()
        self.message = await self.interaction.followup.send(
            embed=page.embed, view=self.build_view(), ephemeral=True
        )

    def str_translate(self, string: Union[str, locale_str]):
        return (
            self.translator.translations[
                (
                    str(self.locale)
                    if str(self.locale) in self.translator.translations
                    else str(Locale.american_english)
                )
            ][string.message]
            if isinstance(string, locale_str)
            else string
        )
