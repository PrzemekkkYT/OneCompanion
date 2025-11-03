import random
from time import sleep
from typing import List
import requests
import json
from datetime import datetime
from jsonc_parser.parser import JsoncParser

from utils.gift_codes import GiftCodeRedeemer, load_model
from utils.utils import (
    keys_exists,
    ReturnType,
    timestamp,
    pretty_traceback,
    setup_logger,
)

from orms.giftcodes import GiftCodes, RedeemedCodes

IDS_FILE = "data/ids.jsonc"
# IDS_FILE = "data/test_ids.json"
MAX_RETRIES = 5

GIFTCODE_API_URL = "http://gift-code-api.whiteout-bot.com/giftcode_api.php"
GIFTCODE_API_KEY = "super_secret_bot_token_nobody_will_ever_find"

WEBHOOK_ID = "1434898414440550410"
WEBHOOK_TOKEN = "W-2-v_hqMpgff8NXN9S4WFX-jq0R5tyxvcw2NY_UY4O5ZPEK-yN-_3ReG4itIlfubw6s"

log = setup_logger("redeemer", "logs/redeemer.log")


def main():
    ids_list = JsoncParser.parse_file(IDS_FILE)
    if not isinstance(ids_list, list):
        raise ValueError("Invalid format in ids.jsonc, expected a list of player ids.")

    api_call_headers = {
        "X-API-Key": GIFTCODE_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        with requests.get(GIFTCODE_API_URL, headers=api_call_headers) as response:
            if response.status_code != 200:
                raise ConnectionError(
                    f"Failed to fetch gift code: {response.status_code} - {response.text}"
                )

            code_lines = process_response(response)

            for code_line in code_lines:
                query = GiftCodes.select().where((GiftCodes.code_line == code_line))

                if not query.exists():
                    log.info("==== TESTING VALIDITY ====")
                    code_valid = test_code_validity(code_line=code_line)
                    log.info(f"{code_line=} | {code_valid=}")

                    if code_valid:
                        log.info("==== ADDING CODE TO THE DATABASE ====")
                        GiftCodes.create(code_line=code_line)
                    sleep(1)
                else:
                    # log.info(f"Code {code_line} already exists")
                    for gc in query:
                        if not gc.active:
                            gc.active = 1
                            gc.save()

            for gc in GiftCodes.select().where(GiftCodes.active == 1):
                if gc.code_line not in code_lines:
                    gc.active = 0
                    gc.save()

    except Exception as e:
        print(pretty_traceback(e))

    log.info("==== STARTING REDEEMER ====")
    redeeming_output = start_redeeming(ids_list)

    log.info("==== SAVING FILE ====")
    with open("test_redeem.json", "w+") as f:
        json.dump(redeeming_output, f, ensure_ascii=False, indent=4)


def process_response(response: requests.Response):
    data = response.json()
    if "codes" not in data:
        raise ValueError("Invalid response format, 'codes' key not found.")

    return data["codes"]


def test_code_validity(code_line: str) -> bool:
    code_line_split = code_line.split(" ")
    if len(code_line_split) != 2:
        log.info("code_line should consist only of gift code and it's starting date")
        return False

    gift_code, start_date = code_line_split

    if datetime.strptime(start_date, "%d.%m.%Y") > datetime.now():
        log.info(f"Giftcode {gift_code} didn't even start yet")
        return False

    onnx_session, metadata = load_model()

    redeemer = GiftCodeRedeemer(
        player_id=350790869,
        giftcode=gift_code,
        onnx_session=onnx_session,
        onnx_metadata=metadata,
    )

    err_code = 0

    for i in range(MAX_RETRIES):
        if i > 0:
            redeemer.captcha_solution = redeemer.start_captcha()
        redeem_data = redeemer.redeem_gift_code()
        err_code = keys_exists(redeem_data, ("request", "err_code"), ReturnType.RESULT)
        err_msg = keys_exists(redeem_data, ("request", "msg"), ReturnType.RESULT)

        log.info(f"{err_code=} | {err_msg=}")

        if err_code in [20000, 40008]:
            return True

        if err_code == 40014:
            break

        sleep(
            random.uniform(1, 5)
            if err_code not in [40100, 40101]
            else random.uniform(20, 40)
        )

    return not (err_code == 40014 or not err_code)


def start_redeeming(id_list: List[int]):
    code_entries = GiftCodes.select().where((GiftCodes.active == True))

    code_lines = [code_entry.code_line for code_entry in code_entries]

    send_startbatch_webhook(code_lines, len(id_list))

    gift_code_executed = {}

    for code_line in code_lines:
        log.info(code_line)
        gift_code_executed[code_line] = execute(id_list, code_line)

        sleep(random.uniform(30, 120))

    return gift_code_executed


def execute(id_list: List[int], code_line: str):
    onnx_session, metadata = load_model()

    gift_code = code_line.split(" ")[0]

    send_start_webhook(gift_code, len(id_list))

    succeed, redeemed, failed = [], [], id_list.copy()

    log.info(f"{len(succeed)=} | {len(redeemed)=} | {len(failed)=}")

    while failed:
        failed_copy = failed.copy()
        log.info(failed_copy)
        for player_id in failed_copy:
            redeemed_for_player = RedeemedCodes.select().where(
                (RedeemedCodes.player_id == player_id)
                & (RedeemedCodes.code_line == code_line)
            )
            if not redeemed_for_player.exists():
                gift_code_redeemer = GiftCodeRedeemer(
                    player_id=player_id,
                    giftcode=gift_code,
                    onnx_session=onnx_session,
                    onnx_metadata=metadata,
                )
                for i in range(MAX_RETRIES):
                    if i > 0:
                        gift_code_redeemer.captcha_solution = (
                            gift_code_redeemer.start_captcha()
                        )

                    redeem_data = gift_code_redeemer.redeem_gift_code()
                    err_code = keys_exists(
                        redeem_data, ("request", "err_code"), ReturnType.RESULT
                    )
                    err_msg = keys_exists(
                        redeem_data, ("request", "msg"), ReturnType.RESULT
                    )

                    log.info(f"{code_line=} | {player_id=} || {err_code=} | {err_msg=}")

                    if err_code in [20000, 40008, 40011]:
                        failed.remove(player_id)
                        if err_code == 20000:
                            succeed.append(player_id)
                        else:
                            redeemed.append(player_id)
                        RedeemedCodes.create(code_line=code_line, player_id=player_id)
                        break

                    # log.info(f"{succeed=} | {redeemed=} | {failed=}")

                    sleep(
                        random.uniform(1, 5)
                        if err_code not in [40100, 40101]
                        else random.uniform(20, 40)
                    )
                sleep(random.uniform(1, 5))
            else:
                redeemed.append(player_id)
                failed.remove(player_id)

    send_finish_webhook(
        gift_code, len(id_list), len(succeed), len(redeemed), len(failed)
    )

    return succeed, redeemed, failed


def send_startbatch_webhook(codes, ids_len):
    formatted_codes = "\n".join([f"└ `{code}`" for code in codes])
    webhook_data = {
        "flags": 32768,  # IS_COMPONENTS_V2
        "username": "One Companion",
        "avatar_url": "https://cdn.discordapp.com/avatars/1403357392149942292/caaff7835a12e42af80d38415095aa3d.png?size=1024",
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": "## Auto Redeem - Starting"},
                    {
                        "type": 10,
                        "content": "Redeemer CronJob found new available and working giftcodes.",
                    },
                    {
                        "type": 10,
                        "content": f"**Included accounts: {ids_len}\nCodes:\n{formatted_codes}**",
                    },
                ],
            }
        ],
    }

    requests.post(
        f"https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}",
        json=webhook_data,
        params={"with_components": True},
    )


def send_start_webhook(code, ids_len):
    webhook_data = {
        "flags": 32768,  # IS_COMPONENTS_V2
        "username": "One Companion",
        "avatar_url": "https://cdn.discordapp.com/avatars/1403357392149942292/caaff7835a12e42af80d38415095aa3d.png?size=1024",
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": "## Auto Redeem - Starting"},
                    {
                        "type": 10,
                        "content": f"**Code: `{code}`\nIncluded accounts: {ids_len}**",
                    },
                ],
            }
        ],
    }

    requests.post(
        f"https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}",
        json=webhook_data,
        params={"with_components": True},
    )


def send_finish_webhook(code, ids_len, succeed_len, redeemed_len, failed_len):
    webhook_data = {
        "flags": 32768,  # IS_COMPONENTS_V2
        "username": "One Companion",
        "avatar_url": "https://cdn.discordapp.com/avatars/1403357392149942292/caaff7835a12e42af80d38415095aa3d.png?size=1024",
        "components": [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": "## Auto Redeem - Finished"},
                    {
                        "type": 10,
                        "content": f"**Code: `{code}`\nIncluded accounts: {ids_len}**",
                    },
                    {
                        "type": 10,
                        "content": f"""
━━━━━━━━━━━━━━━━━━━━━━
✅ {succeed_len} / {ids_len} Success
❗ {redeemed_len} / {ids_len} Already Redeemed
❌ {failed_len} / {ids_len} Fail
━━━━━━━━━━━━━━━━━━━━━━
""",
                    },
                ],
            }
        ],
    }

    requests.post(
        f"https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}",
        json=webhook_data,
        params={"with_components": True},
    )


if __name__ == "__main__":
    main()
