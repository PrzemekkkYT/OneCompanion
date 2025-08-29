import asyncio
import hashlib
import json
import requests
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

from utils.gift_codes import CaptchaSolver, GiftCodeRedeemer, load_model
from utils.whitecord import Embed, View, Button


class R4Tools(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.translator = self.client.tree.translator

    @app_commands.command()
    async def mass_redeem(
        self, interaction: discord.Interaction, code: str, ids_range: str = "0-100"
    ):
        with open("data/ids.json") as f:
            ids = json.load(f)
        # Redeem the code for each ID
        onnx, metadata = load_model()
        self.start = int(ids_range.split("-")[0])
        self.end = int(ids_range.split("-")[1])

        player_num = self.end - self.start - 1

        async def cancel_callback(button_interaction: discord.Interaction):
            await button_interaction.delete_original_response()
            return

        async def approve_callback(button_interaction: discord.Interaction):
            await interaction.delete_original_response()
            fail = []

            async def retry_callback(retry_button_interaction: discord.Interaction):
                await retry_button_interaction.response.defer()
                msg = await button_interaction.original_response()
                await msg.edit(
                    embed=Embed(
                        translator=self.translator,
                        locale=interaction.locale,
                        title="Mass Redeem - Retrying",
                        description=f"""
                        Code: `{code}`
                        Included accounts: {len(fail)}
                        ━━━━━━━━━━━━━━━━━━━━━━
                        ✅ 0 / {len(fail)} Success
                        ❗ 0 / {len(fail)} Already Redeemed
                        ❌ 0 / {len(fail)} Fail
                        ━━━━━━━━━━━━━━━━━━━━━━
                        """,
                    )
                )

                retry_success, retry_already_redeemed, retry_fail = (
                    await self.perform_mass_redeem(
                        button_interaction,
                        fail,
                        onnx,
                        metadata,
                        code,
                        self.start,
                        self.end,
                        True,
                    )
                )

                msg = await button_interaction.original_response()
                await msg.edit(
                    embed=Embed(
                        translator=self.translator,
                        locale=interaction.locale,
                        title="Mass Redeem - Retrying",
                        description=f"""
                        Code: `{code}`
                        Included accounts: {len(fail)}
                        ━━━━━━━━━━━━━━━━━━━━━━
                        ✅ {len(retry_success)} / {len(fail)} Success
                        ❗ {len(retry_already_redeemed)} / {len(fail)} Already Redeemed
                        ❌ {len(retry_fail)} / {len(fail)} Fail
                        ━━━━━━━━━━━━━━━━━━━━━━
                        """,
                    )
                )

            await button_interaction.response.send_message(
                embed=Embed(
                    translator=self.translator,
                    locale=interaction.locale,
                    title="Mass Redeem - Starting",
                    description=f"""
                    Code: `{code}`
                    Included accounts: {player_num}
                    ━━━━━━━━━━━━━━━━━━━━━━
                    ✅ 0 / {player_num} Success
                    ❗ 0 / {player_num} Already Redeemed
                    ❌ 0 / {player_num} Fail
                    ━━━━━━━━━━━━━━━━━━━━━━
                    """,
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc),
                ),
            )

            success, already_redeemed, fail = await self.perform_mass_redeem(
                button_interaction, ids, onnx, metadata, code, self.start, self.end
            )

            msg = await button_interaction.original_response()

            if fail:
                retry_view = View(
                    translator=self.translator,
                    locale=interaction.locale,
                )
                retry_view.add_item(
                    Button(
                        label="Retry",
                        style=discord.ButtonStyle.green,
                        custom_id="retry_mass_redeem",
                        callback=retry_callback,
                    )
                )

            await msg.edit(
                embed=Embed(
                    translator=self.translator,
                    locale=interaction.locale,
                    title="Mass Redeem - Finished",
                    description=f"""
                    Code: `{code}`
                    Included accounts: {player_num}
                    ━━━━━━━━━━━━━━━━━━━━━━
                    ✅ {len(success)} / {player_num} Success
                    ❗ {len(already_redeemed)} / {player_num} Already Redeemed
                    ❌ {len(fail)} / {player_num} Fail
                    ━━━━━━━━━━━━━━━━━━━━━━
                    { '**Failed multiple times, please try again later for successful redeem.**' if fail else '**All accounts have been successfully redeemed!**' }
                    """,
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc),
                ),
                view=retry_view if fail else None,
            )

        start_view = View(
            translator=self.translator,
            locale=interaction.locale,
        )
        start_view.add_item(
            Button(
                label="Start",
                style=discord.ButtonStyle.green,
                custom_id="approve_mass_redeem",
                callback=approve_callback,
            ),
        )
        start_view.add_item(
            Button(
                label="Cancel",
                style=discord.ButtonStyle.danger,
                custom_id="cancel_mass_redeem",
                callback=cancel_callback,
            ),
        )

        await interaction.response.send_message(
            embed=Embed(
                translator=self.translator,
                locale=interaction.locale,
                title="Mass Redeem - Starting",
                description=f"""
                Code: `{code}`
                Included accounts: {player_num}
                Start Mass Redeem?
                """,
                color=0x00FF00,
                timestamp=datetime.now(timezone.utc),
            ),
            view=start_view,
        )

    async def perform_mass_redeem(
        self, interaction, ids, onnx, metadata, code, start, end, retry=False
    ):
        success = []
        already_redeemed = []
        fail = []

        player_num = end - start

        for player_id in ids[start:end]:
            gift_code_redeemer = GiftCodeRedeemer(
                player_id=player_id,
                giftcode=code,
                onnx_session=onnx,
                onnx_metadata=metadata,
            )
            err_code, msg = gift_code_redeemer.redeem_gift_code()

            if err_code == 20000:
                success.append(player_id)
            elif err_code == 40008:
                already_redeemed.append(player_id)
            else:
                fail.append(player_id)

            interaction_message = await interaction.original_response()
            if not retry:
                await interaction_message.edit(
                    embed=Embed(
                        translator=self.translator,
                        locale=interaction.locale,
                        title="Mass Redeem - Executing...",
                        description=f"""
                        Code: `{code}`
                        Included accounts: {player_num}
                        ━━━━━━━━━━━━━━━━━━━━━━
                        ✅ {len(success)} / {player_num} Success
                        ❗ {len(already_redeemed)} / {player_num} Already Redeemed
                        ❌ {len(fail)} / {player_num} Fail
                        ━━━━━━━━━━━━━━━━━━━━━━
                        """,
                        color=0x00FF00,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            else:
                await interaction_message.edit(
                    embed=Embed(
                        translator=self.translator,
                        locale=interaction.locale,
                        title="Mass Redeem - Retrying...",
                        description=f"""
                        Code: `{code}`
                        Included accounts: {len(ids)}
                        ━━━━━━━━━━━━━━━━━━━━━━
                        ✅ {len(success)} / {len(ids)} Success
                        ❗ {len(already_redeemed)} / {len(ids)} Already Redeemed
                        ❌ {len(fail)} / {len(ids)} Fail
                        ━━━━━━━━━━━━━━━━━━━━━━
                        """,
                        color=0x00FF00,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            # Wait a few seconds before continuing to the next iteration
            await asyncio.sleep(2)

        return success, already_redeemed, fail


async def setup(client: commands.Bot):
    await client.add_cog(R4Tools(client))
