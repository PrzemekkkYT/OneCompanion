import random
from time import sleep
from typing import List
import requests
import json
from datetime import datetime
from jsonc_parser.parser import JsoncParser

from utils.gift_codes import GiftCodeRedeemer, load_model
from utils.utils import keys_exists, ReturnType, timestamp, pretty_traceback

from orms.giftcodes import GiftCodes, RedeemedCodes

# IDS_FILE = "data/ids.jsonc"
IDS_FILE = "data/test_ids.json"
MAX_RETRIES = 5

GIFTCODE_API_URL = "http://gift-code-api.whiteout-bot.com/giftcode_api.php"
GIFTCODE_API_KEY = "super_secret_bot_token_nobody_will_ever_find"


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

            for gift_code_data in process_response(response):
                print(gift_code_data)
                gift_code, start_date = gift_code_data
                start_timestamp = timestamp(datetime.strptime(start_date, "%d.%m.%Y"))

                query = GiftCodes.select().where(
                    (GiftCodes.code == gift_code)
                    & (GiftCodes.code_start_timestamp == start_timestamp)
                )
                if not query.exists():
                    print("==== TESTING VALIDITY ====")
                    code_valid = test_code_validity(
                        gift_code=gift_code, start_date=start_date
                    )
                    print(gift_code, code_valid)
                    if code_valid:
                        print("==== ADDING CODE TO THE DATABASE ====")
                        GiftCodes.create(
                            code=gift_code, code_start_timestamp=start_timestamp
                        )
                    sleep(1)
                else:
                    print("Code already exists")

    except Exception as e:
        print(pretty_traceback(e))

    print("==== STARTING REDEEMER ====")
    redeeming_output = start_redeeming(ids_list)

    print("==== SAVING FILE ====")
    with open("test_redeem.json", "w+") as f:
        json.dump(redeeming_output, f, ensure_ascii=False, indent=4)


def process_response(response):
    data = response.json()
    if "codes" not in data:
        raise ValueError("Invalid response format, 'codes' key not found.")
    valid_codes = []
    for code_line in data["codes"]:
        try:
            code, start_date = code_line.split(" ")
            valid_codes.append((code, start_date))
        except Exception as e:
            print(f"Error processing code line '{code_line}': {e}")
    return valid_codes


def test_code_validity(gift_code: str, start_date: str) -> bool:
    if datetime.strptime(start_date, "%d.%m.%Y") > datetime.now():
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

        print(f"{err_code=} | {err_msg=}")

        if err_code in [20000, 40008]:
            return True

        if err_code == 40014:
            break

        sleep(1)

    return not (err_code == 40014 or not err_code)


def start_redeeming(id_list: List[int]):
    gift_codes = GiftCodes.select().where(
        (timestamp(datetime.now()) >= GiftCodes.code_start_timestamp)
        & (GiftCodes.active == True)
    )

    gift_code_executed = {}

    for gift_code in gift_codes:
        print(gift_code.code)
        gift_code_executed[gift_code.code] = execute(id_list, gift_code.code)

        sleep(2)

    return gift_code_executed


def execute(id_list: List[int], gift_code: str):
    onnx_session, metadata = load_model()

    succeed, redeemed, failed = [], [], id_list.copy()

    print(f"{succeed=} | {redeemed=} | {failed=}")

    while failed:
        failed_copy = failed.copy()
        print(failed_copy)
        for player_id in failed_copy:
            redeemed_for_player = RedeemedCodes.select().where(
                (RedeemedCodes.player_id == player_id)
                & (RedeemedCodes.code == gift_code)
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

                    print(f"{gift_code=} | {player_id=} || {err_code=} | {err_msg=}")

                    if err_code == 20000:
                        failed.remove(player_id)
                        succeed.append(player_id)
                        RedeemedCodes.create(code=gift_code, player_id=player_id)
                        break

                    if err_code == 40008:
                        failed.remove(player_id)
                        redeemed.append(player_id)
                        RedeemedCodes.create(code=gift_code, player_id=player_id)
                        break

                    print(f"{succeed=} | {redeemed=} | {failed=}")

                    sleep(
                        random.uniform(1, 5)
                        if err_code != 40014
                        else random.uniform(20, 40)
                    )
                sleep(random.uniform(1, 5))
            else:
                failed.remove(player_id)

    return succeed, redeemed, failed


if __name__ == "__main__":
    main()
