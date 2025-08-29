# main import
from typing import Optional
import json

# discord import
import discord
from discord.app_commands import locale_str, TranslationContextTypes, Translator
from discord.app_commands.translator import OtherTranslationContext
from discord.enums import Locale


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
