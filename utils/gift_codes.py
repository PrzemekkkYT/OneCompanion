import asyncio
from datetime import datetime
import hashlib
import random
import json
from requests.adapters import HTTPAdapter, Retry

import requests

from utils.browser_headers import get_headers
from utils.utils import setup_logger

RESOURCES_FOLDER = "resources"
# WOS API URLs and Key
wos_player_info_url = "https://wos-giftcode-api.centurygame.com/api/player"
wos_giftcode_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
wos_captcha_url = "https://wos-giftcode-api.centurygame.com/api/captcha"
wos_giftcode_redemption_url = "https://wos-giftcode.centurygame.com"
wos_encrypt_key = "tB87#kPtkxqOS2"

logger = setup_logger("giftcodes", "logs/giftcodes.log")

MAX_RETRIES = 5


def encode_data(data):
    secret = wos_encrypt_key
    sorted_keys = sorted(data.keys())
    encoded_data = "&".join(
        [
            f"{key}={json.dumps(data[key]) if isinstance(data[key], dict) else data[key]}"
            for key in sorted_keys
        ]
    )
    sign = hashlib.md5(f"{encoded_data}{secret}".encode()).hexdigest()

    return {"sign": sign, **data}


async def test_code_validity(code: str) -> bool:

    redeemer = GiftCodeRedeemer(
        player_id=350790869, player_state=2263, giftcode=code
    )  # Using a dummy player for validation

    err_code = 0

    for _ in range(MAX_RETRIES):
        redeem_data = redeemer.redeem_gift_code()

        err_code = redeem_data.err_code or 0

        logger.info(f"Veryfication for code {code}: {redeem_data}")

        if err_code in [20000, 40008, 40011]:
            return True, err_code

        if err_code in [40014, 40018]:
            return True, err_code

        await asyncio.sleep(
            random.uniform(1, 5)
            if err_code not in [40100, 40101]
            else random.uniform(20, 40)
        )

    return False, err_code


class GiftCodeResponse:
    def __init__(self, code: int, data: list, msg: str, err_code: int):
        self.code = code
        self.data = data
        self.msg = msg
        self.err_code = err_code

    def __str__(self):
        return f"GiftCodeResponse(code={self.code}, data={self.data}, msg={self.msg}, err_code={self.err_code})"


class GiftCodeRedeemer:
    def __init__(
        self,
        player_id: int,
        player_state: int,
        giftcode: str,
    ):
        self.player_id = player_id
        self.player_state = player_state
        self.giftcode = giftcode

        self.session = requests.Session()
        self.session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["POST", "GET"],
                )
            ),
        )
        self.session.headers.update(get_headers(wos_giftcode_redemption_url))

    def redeem_gift_code(self):
        data_to_encode = {
            "fid": f"{self.player_id}",
            "cdk": self.giftcode,
            "kid": f"{self.player_state}",
            "time": f"{int(datetime.now().timestamp())}",
        }
        data = encode_data(data_to_encode)
        response_giftcode = GiftCodeResponse(
            **self.session.post(wos_giftcode_url, data=data).json()
        )

        err_code = response_giftcode.err_code or 0

        if err_code in [20000, 40008]:
            self.session.close()

        return response_giftcode
