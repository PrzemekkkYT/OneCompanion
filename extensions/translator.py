import html
import json
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

from google.cloud import translate_v2
from google.oauth2 import service_account

from orms.configs import GuildConfigs
from utils.whitecord import Embed, EmbedAuthor
import os
from datetime import date

FLAG_TO_LOCALE: dict[str, str] = {
    "🇵🇱": "pl",
    "🇬🇧": "en",
    "🇺🇸": "en",
    "🇩🇪": "de",
    "🇫🇷": "fr",
    "🇪🇸": "es",
    "🇮🇹": "it",
    "🇵🇹": "pt",
    "🇧🇷": "pt-BR",
    "🇳🇱": "nl",
    "🇸🇪": "sv",
    "🇳🇴": "no",
    "🇩🇰": "da",
    "🇫🇮": "fi",
    "🇨🇿": "cs",
    "🇸🇰": "sk",
    "🇭🇺": "hu",
    "🇷🇴": "ro",
    "🇧🇬": "bg",
    "🇺🇦": "uk",
    "🇷🇺": "ru",
    "🇹🇷": "tr",
    "🇬🇷": "el",
    "🇯🇵": "ja",
    "🇰🇷": "ko",
    "🇨🇳": "zh-CN",
    "🇹🇼": "zh-TW",
    "🇮🇳": "hi",
    "🇸🇦": "ar",
    "🇮🇱": "he",
    "🇮🇩": "id",
    "🇻🇳": "vi",
    "🇹🇭": "th",
}

LOCALE_TO_FLAG: dict[str, str] = {v: k for k, v in FLAG_TO_LOCALE.items()}


class Translator(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.translator = self.client.tree.translator

        self.translation_footer = f"*Translated with {self.client.user.mention}*"

        credentials = service_account.Credentials.from_service_account_file(
            "gcloud_credentials.json"
        )
        self.gtranslate_client = translate_v2.Client(credentials=credentials)

    async def get_or_create_webhook(self, channel: discord.TextChannel):
        webhooks = await channel.webhooks()
        for wh in webhooks:
            if wh.name == "Translator":
                return wh
        return await channel.create_webhook(name="Translator")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.client.user.id:
            return

        cfg: GuildConfigs | None = GuildConfigs.get_or_none(guild_id=payload.guild_id)
        if not cfg or not cfg.translator_enabled:
            return

        emoji = str(payload.emoji)
        if emoji not in FLAG_TO_LOCALE:
            return

        target_lang = FLAG_TO_LOCALE[emoji]
        channel = self.client.get_channel(payload.channel_id)

        if not isinstance(channel, discord.TextChannel):
            return

        message = await channel.fetch_message(payload.message_id)

        if not message.content:
            return

        if message.author.bot and (
            any(flag in message.author.name for flag in FLAG_TO_LOCALE.keys())
            or message.content.startswith("[└")
        ):
            await channel.send("Can't translate previously translated messages")
            return

        try:
            cache_path = "cache/translator.json"
            counter_path = "cache/translator_counter.json"

            os.makedirs(os.path.dirname(cache_path), exist_ok=True)

            # Load caches
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache: list[dict] = json.load(f) or []
            except (FileNotFoundError, json.JSONDecodeError):
                cache = []

            try:
                with open(counter_path, "r", encoding="utf-8") as f:
                    counter: dict = json.load(f) or {}
            except (FileNotFoundError, json.JSONDecodeError):
                counter = {"total_chars_translated": 0, "total_chars_requested": 0}

            # Try cache hit
            cache_entry = next(
                (
                    item
                    for item in cache
                    if item.get("original", {}).get("content") == message.content
                ),
                None,
            )

            translated_text = None
            source_language = "??"

            if cache_entry:
                source_language = cache_entry.get("original", {}).get("locale", "??")
                translated_text = cache_entry.get("translations", {}).get(target_lang)

            if not translated_text:
                # Daily 15k requested characters limit
                DAILY_LIMIT = 15_000

                # Ensure counter has date tracking

                today = date.today().isoformat()
                if counter.get("date") != today:
                    counter["date"] = today
                    counter["total_chars_requested"] = 0
                    counter["total_chars_translated"] = 0

                new_total_requested = int(
                    counter.get("total_chars_requested", 0)
                ) + len(message.content)
                if new_total_requested > DAILY_LIMIT:
                    await channel.send(
                        f"Daily translation limit reached ({DAILY_LIMIT} requested characters). Try again tomorrow.",
                        allowed_mentions=discord.AllowedMentions.none(),
                        reference=message,
                    )
                    return

                # Character limit accounting (requested chars)
                counter["total_chars_requested"] = new_total_requested

                # Translate via Google
                result: dict = self.gtranslate_client.translate(
                    message.content, target_language=target_lang
                )

                translated_text = html.unescape(result["translatedText"])
                source_language = result.get("detectedSourceLanguage", "??")

                # Character limit accounting (translated chars)
                counter["total_chars_translated"] = int(
                    counter.get("total_chars_translated", 0)
                ) + len(translated_text)

                # Update / insert cache entry
                if not cache_entry:
                    cache_entry = {
                        "original": {
                            "locale": source_language,
                            "content": message.content,
                        },
                        "translations": {},
                    }
                    cache.append(cache_entry)

                cache_entry.setdefault("translations", {})[
                    target_lang
                ] = translated_text

                # Persist caches
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)

                with open(counter_path, "w", encoding="utf-8") as f:
                    json.dump(counter, f, ensure_ascii=False, indent=2)

            source_language_flag = LOCALE_TO_FLAG.get(source_language, "🏳️")

            # await channel.send(
            #     content=f"[└{message.content[:20]}...]({message.jump_url}) | {source_language_flag} → {emoji}\n{translated_text}",
            #     allowed_mentions=discord.AllowedMentions.none(),
            #     reference=message,
            # )

            # Pobieramy lub tworzymy webhook
            webhook = await self.get_or_create_webhook(channel)

            # Wysyłamy wiadomość "jako użytkownik"
            await webhook.send(
                content=f"[└{message.content[:30]}...]({message.jump_url})\n{translated_text}\n",
                username=f"{source_language_flag} → {emoji} | {message.author.display_name}",
                avatar_url=message.author.display_avatar.url,
                allowed_mentions=discord.AllowedMentions.none(),  # Unikamy pingowania @everyone
            )

        except Exception as e:
            print(f"Błąd Webhooka/Tłumaczenia: {e}")


async def setup(client: commands.Bot):
    await client.add_cog(Translator(client))
