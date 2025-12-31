import io
import json
import asyncio
import random
import requests
from types import NoneType
from typing import List, Optional
import logging
from logging import StreamHandler
from jsonc_parser.parser import JsoncParser

import discord
from discord import ui
from discord import app_commands
from discord.ext import commands
from discord import ButtonStyle
from discord.utils import MISSING

from utils.gift_codes import GiftCodeRedeemer, load_model
from utils.utils import ReturnType, keys_exists, setup_logger

IDS_FILE = "data/ids.jsonc"
MAX_RETRIES = 5


log = setup_logger("giftcodes", "logs/giftcodes.log")


class GiftCodes(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.translator = self.client.tree.translator

    @app_commands.command()
    async def redeemer(
        self,
        interaction: discord.Interaction,
        code: str,
        ids_source: Optional[str] = None,
    ):
        ids = []
        if ids_source:
            if ids_source.startswith("http"):
                try:
                    req = requests.get(ids_source)
                    req_data = JsoncParser.parse_str(req.text)
                    if isinstance(req_data, list):
                        ids = req_data
                except:
                    pass
            else:
                try:
                    source_data = JsoncParser.parse_str(ids_source)
                    if isinstance(source_data, list):
                        ids = source_data
                except:
                    pass
        else:
            file_data = JsoncParser.parse_file(IDS_FILE)
            if isinstance(file_data, list):
                ids = file_data

        if not ids:
            await interaction.response.send_message("No IDs found in the given source")
            return

        redeemer = RedeemerView(interaction, code)
        await redeemer.init(ids)


class RedeemerView(ui.LayoutView):
    @property
    def interaction(self):
        return self.__interaction

    @property
    def fail(self):
        return self.__fail

    def __init__(self, interaction: discord.Interaction, code: str):
        super().__init__(timeout=None)
        self.__interaction = interaction
        self.__code = code

        self.__onnx, self.__metadata = load_model()

        self.__title = ui.TextDisplay("## Auto Redeem - Confirm")
        self.__info = ui.TextDisplay(f"### Code: `{self.__code}`")
        self.__progress: ui.TextDisplay | None = None
        self.__error: ui.TextDisplay | None = None

        self.__control_buttons = RedeemerControlButtons(self)

        self.__additional_items = []

        self.__success = []
        self.__already_redeemed = []
        self.__fail = []

        self.add_item(self._build_container())

    async def init(self, ids: List[int]):
        self.__ids = ids
        self.__info.content = f"**Code: `{self.__code}`\nIncluded accounts: {len(ids)}\nStart the auto redeem?**"
        await self.__interaction.response.send_message(view=self)

    def _build_container(self):
        return ui.Container(
            self.__title,
            self.__info,
            *([self.__progress] if self.__progress else []),
            *([self.__error] if self.__error else []),
            *([self.__control_buttons] if self.__control_buttons else []),
        )

    async def update_view(
        self,
        title: ui.TextDisplay = MISSING,
        info: ui.TextDisplay = MISSING,
        progress: ui.TextDisplay | None = MISSING,
        error: ui.TextDisplay | None = MISSING,
        control_buttons: ui.ActionRow | None = MISSING,
        new_items: List[ui.Item] | None = MISSING,
        only_return=False,
    ):
        # set title
        if title is not MISSING:
            if isinstance(title, ui.TextDisplay):
                self.__title = title
        # set info
        if info is not MISSING:
            if isinstance(info, ui.TextDisplay):
                self.__info = info
        # set progress
        if progress is not MISSING:
            if isinstance(
                progress,
                (ui.TextDisplay, NoneType),
            ):
                self.__progress = progress
        # set error
        if error is not MISSING:
            if isinstance(
                error,
                (ui.TextDisplay, NoneType),
            ):
                self.__error = error
        if control_buttons is not MISSING:
            self.__control_buttons = control_buttons

        new_container = self._build_container()
        self.clear_items()
        self.add_item(new_container)

        if new_items is not MISSING:
            self.__additional_items = new_items

        for item in self.__additional_items:
            self.add_item(item)

        if not only_return:
            await self.__interaction.edit_original_response(view=self)
        return self

    async def execute(self, ids: List[int]):
        success = []
        already_redeemed = []
        fail = []

        to_process = ids.copy()

        while to_process:
            to_process_copy = to_process.copy()

            for player_id in to_process_copy:
                gift_code_redeemer = GiftCodeRedeemer(
                    player_id=player_id,
                    giftcode=self.__code,
                    onnx_session=self.__onnx,
                    onnx_metadata=self.__metadata,
                )

                player_name = keys_exists(
                    element=gift_code_redeemer.stove_info,
                    keys=("data", "nickname"),
                    returntype=ReturnType.RESULT,
                )

                err_code = 0

                for i in range(MAX_RETRIES):
                    if i > 0:
                        gift_code_redeemer.captcha_solution = (
                            gift_code_redeemer.start_captcha()
                        )

                    redeem_data = gift_code_redeemer.redeem_gift_code()
                    # err_code = redeem_data.get("request").get("err_code")
                    err_code = keys_exists(
                        redeem_data, ("request", "err_code"), ReturnType.RESULT
                    )

                    if err_code in [20000, 40008, 40011]:
                        break

                    await self.update_view(
                        error=ui.TextDisplay(
                            f"Retry {i + 1}/{MAX_RETRIES} for {player_name}[{player_id}]"
                        )
                    )

                    await asyncio.sleep(
                        random.uniform(1, 5)
                        if err_code not in [40100, 40101]
                        else random.uniform(20, 40)
                    )

                await self.update_view(error=None)

                if err_code in [20000, 40008, 40011]:
                    to_process.remove(player_id)
                    if err_code == 20000:
                        success.append(player_id)
                    else:
                        already_redeemed.append(player_id)
                else:
                    fail.append(player_id)
                    err = f"Error {err_code} encountered for {player_name}[{player_id}]"
                    log.warning(err)
                    await self.update_view(error=ui.TextDisplay(err))

                # match err_code:
                #     case 20000:
                #         success.append(player_id)
                #     case 40008:
                #         already_redeemed.append(player_id)
                #     case _:
                #         fail.append(redeem_data)

                await self.update_view(
                    progress=ui.TextDisplay(
                        f"""
    Finished for {len(success) + len(already_redeemed) + len(fail)} / {len(ids)}
    ━━━━━━━━━━━━━━━━━━━━━━
    ✅ {len(success)} / {len(ids)} Success
    ❗ {len(already_redeemed)} / {len(ids)} Already Redeemed
    # ❌ {len(fail)} / {len(ids)} Fail
    ━━━━━━━━━━━━━━━━━━━━━━
    """
                    ),
                    error=(
                        ui.TextDisplay(f"ID: {player_id} failed")
                        if err_code not in [20000, 40008, 40011]
                        else None
                    ),
                )

                await asyncio.sleep(random.uniform(1, 5))
        return success, already_redeemed, fail

    async def perform_mass_redeem(self):
        await self.update_view(
            title=ui.TextDisplay("## Auto Redeem - Executing"),
            info=ui.TextDisplay(
                f"**Code: `{self.__code}`\nIncluded accounts: {len(self.__ids)}**"
            ),
        )

        self.__success, self.__already_redeemed, self.__fail = await self.execute(
            self.__ids
        )

        await self.update_view(
            title=ui.TextDisplay("## Auto Redeem - Finished"),
            error=(
                ui.TextDisplay(f"**Failed on {len(self.__fail)} accounts. Retry?**")
                if self.__fail
                else None
            ),
            control_buttons=RedeemerRetryButtons(self) if self.__fail else None,
        )

    async def retry(self):
        await self.update_view(
            title=ui.TextDisplay("## Auto Redeem - Retrying"),
            info=ui.TextDisplay(
                f"**Code: `{self.__code}`\nIncluded accounts: {len(self.__fail)}**"
            ),
            error=None,
            control_buttons=None,
        )

        to_retry = [f.get("player").get("fid") for f in self.__fail]

        success, already_redeemed, fail = await self.execute(to_retry)

        self.__success = self.__success + success
        self.__already_redeemed = self.__already_redeemed + already_redeemed
        self.__fail = fail

        if fail:
            await self.update_view(
                title=ui.TextDisplay("## Auto Redeem - Finished Retrying"),
                progress=ui.TextDisplay(
                    f"""
━━━━━━━━━━━━━━━━━━━━━━
✅ {len(self.__success)} / {len(self.__ids)} Success
❗ {len(self.__already_redeemed)} / {len(self.__ids)} Already Redeemed
❌ {len(self.__fail)} / {len(self.__ids)} Fail
━━━━━━━━━━━━━━━━━━━━━━
"""
                ),
                error=(
                    ui.TextDisplay(
                        f"**Still failed on {len(self.__fail)} accounts.\nDo you want info of all failed players?**"
                    )
                    if self.__fail
                    else None
                ),
                control_buttons=RedeemerFailedButtons(self),
            )


class RedeemerControlButtons(ui.ActionRow):
    @property
    def view(self):
        return self.__view

    def __init__(self, view: RedeemerView):
        self.__view = view

        super().__init__()

    @ui.button(label="Confirm", style=ButtonStyle.green, custom_id="redeemer_confirm")
    async def confirm_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()
        await self.__view.update_view(control_buttons=None)
        await self.__view.perform_mass_redeem()

    @ui.button(label="Cancel", style=ButtonStyle.red, custom_id="redeemer_cancel")
    async def cancel_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()
        await self.__view.interaction.delete_original_response()
        await button_interaction.followup.send("Auto Redeem canceled")


class RedeemerRetryButtons(ui.ActionRow):
    def __init__(self, view: RedeemerView):
        self.__view = view

        super().__init__()

    @ui.button(label="Retry", style=ButtonStyle.primary, custom_id="redeemer_retry")
    async def retry_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()
        await self.__view.update_view(control_buttons=None)
        await self.__view.retry()

    @ui.button(label="Cancel", style=ButtonStyle.red, custom_id="redeemer_retry_cancel")
    async def cancel_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()
        await self.__view.interaction.delete_original_response()
        await button_interaction.followup.send("Auto Redeem canceled without retrying")


class RedeemerFailedButtons(ui.ActionRow):
    def __init__(self, view: RedeemerView):
        self.__view = view

        super().__init__()

    @ui.button(
        label="Download full fail fnfo",
        style=ButtonStyle.primary,
        custom_id="redeemer_download_full",
    )
    async def download_full_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()

        new_view = await self.__view.update_view(
            title=ui.TextDisplay("## Auto Redeem - Finished"),
            control_buttons=None,
            error=ui.TextDisplay("Json file with info of fails has been created."),
            new_items=[ui.File(f"attachment://ids_{button_interaction.guild.id}.json")],
            only_return=True,
        )

        await self.__view.interaction.edit_original_response(
            view=new_view,
            attachments=[
                discord.File(
                    io.BytesIO(json.dumps(self.__view.fail).encode("utf-8")),
                    filename=f"ids_{button_interaction.guild.id}.json",
                )
            ],
        )

    @ui.button(
        label="Download IDs",
        style=ButtonStyle.primary,
        custom_id="redeemer_download_ids",
    )
    async def download_ids_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()

        ids = [fail.get("player").get("fid") for fail in self.__view.fail]

        new_view = await self.__view.update_view(
            title=ui.TextDisplay("## Auto Redeem - Finished"),
            control_buttons=None,
            error=ui.TextDisplay("Json file with failed ids has been created."),
            new_items=[ui.File(f"attachment://ids_{button_interaction.guild.id}.json")],
            only_return=True,
        )

        await self.__view.interaction.edit_original_response(
            view=new_view,
            attachments=[
                discord.File(
                    io.BytesIO(json.dumps(ids).encode("utf-8")),
                    filename=f"ids_{button_interaction.guild.id}.json",
                )
            ],
        )

    @ui.button(
        label="Cancel", style=ButtonStyle.red, custom_id="redeemer_download_cancel"
    )
    async def cancel_button(
        self, button_interaction: discord.Interaction, button: ui.Button
    ):
        await button_interaction.response.defer()
        await self.__view.interaction.delete_original_response()
        await button_interaction.followup.send(
            "Auto Redeem canceled without getting failed ids"
        )


#################################################
# TODO: Retry if any fails
#################################################


async def setup(client: commands.Bot):
    await client.add_cog(GiftCodes(client))
