import base64
from datetime import datetime
import hashlib
import onnxruntime as ort
import numpy as np
from PIL import Image
import json
import io
import os

import requests

RESOURCES_FOLDER = "resources"
# WOS API URLs and Key
wos_player_info_url = "https://wos-giftcode-api.centurygame.com/api/player"
wos_giftcode_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
wos_captcha_url = "https://wos-giftcode-api.centurygame.com/api/captcha"
wos_giftcode_redemption_url = "https://wos-giftcode.centurygame.com"
wos_encrypt_key = "tB87#kPtkxqOS2"


def encode_data(data, debug_sign_error=False):
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


def load_model():
    onnx_session = ort.InferenceSession(
        os.path.join(RESOURCES_FOLDER, "models", "captcha_model.onnx")
    )

    with open(
        os.path.join(RESOURCES_FOLDER, "models", "captcha_model_metadata.json"), "r"
    ) as f:
        metadata = json.load(f)

    return onnx_session, metadata


class CaptchaSolver:
    def __init__(self, req_session, response_stove_info, onnx_session, metadata):
        self.req_session: requests.Session = req_session
        self.player_id: int = response_stove_info.get("data").get("fid")
        self.onnx_session = onnx_session
        self.metadata = metadata

    def fetch_captcha(self):
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/x-www-form-urlencoded",
            "origin": wos_giftcode_redemption_url,
        }

        data_to_encode = {
            "fid": self.player_id,
            "time": f"{int(datetime.now().timestamp() * 1000)}",
            "init": "0",
        }

        encoded_data = encode_data(data_to_encode)

        try:
            response = self.req_session.post(
                wos_captcha_url,
                headers=headers,
                data=encoded_data,
            )
            # print(f"Captcha fetch response: {response.text}")

            if response.status_code == 200:
                captcha_data = response.json()
                if (
                    captcha_data.get("code") == 1
                    and captcha_data.get("msg") == "CAPTCHA GET TOO FREQUENT."
                ):
                    return None, "CAPTCHA_TOO_FREQUENT"

                if "data" in captcha_data and "img" in captcha_data["data"]:
                    if captcha_data["data"]["img"].startswith("data:image"):
                        img_b64_data = captcha_data["data"]["img"].split(",", 1)[1]
                    else:
                        img_b64_data = captcha_data["data"]["img"]
                    return img_b64_data, None

            return None, "CAPTCHA_FETCH_ERROR"
        except Exception as e:
            # self.logger.exception(f"Error fetching captcha: {e}")
            print(f"Error fetching captcha: {e}")
            return None, f"CAPTCHA_EXCEPTION: {str(e)}"

    def solve(self, image_bytes):
        # Preprocess
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        height, width = self.metadata["input_shape"][1:3]
        image = image.resize((width, height), Image.LANCZOS)

        image_array = np.array(image, dtype=np.float32)
        mean, std = (
            self.metadata["normalization"]["mean"][0],
            self.metadata["normalization"]["std"][0],
        )
        image_array = (image_array / 255.0 - mean) / std
        image_array = np.expand_dims(np.expand_dims(image_array, 0), 0)

        # Inference
        input_name = self.onnx_session.get_inputs()[0].name
        outputs = self.onnx_session.run(None, {input_name: image_array})

        # Decode
        idx_to_char = self.metadata["idx_to_char"]
        result = ""

        for pos in range(4):
            char_idx = np.argmax(outputs[pos][0])
            result += idx_to_char[str(char_idx)]

        return result

    def solve_captcha(self):
        image_b64, err = self.fetch_captcha()
        if err:
            print(f"Error fetching captcha: {err}")
            return None

        image_bytes = base64.b64decode(image_b64)
        return self.solve(image_bytes)


class GiftCodeRedeemer:
    def __init__(
        self,
        player_id: int,
        giftcode: str,
        onnx_session,
        onnx_metadata,
    ):
        self.req_session, self.stove_info = self.get_stove_info(player_id)
        self.giftcode = giftcode
        self.onnx_session = onnx_session
        self.onnx_metadata = onnx_metadata
        self.captcha_solution = self.start_captcha()

    def start_captcha(self):
        captcha_solver = CaptchaSolver(
            self.req_session,
            self.stove_info,
            self.onnx_session,
            self.onnx_metadata,
        )
        return captcha_solver.solve_captcha()

    def get_stove_info(self, player_id: int):
        session = requests.Session()
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/x-www-form-urlencoded",
            "origin": wos_giftcode_redemption_url,
        }
        data_to_encode = {
            "fid": f"{player_id}",
            "time": f"{int(datetime.now().timestamp())}",
        }
        data = encode_data(data_to_encode)
        response_stove_info = session.post(
            wos_player_info_url,
            headers=headers,
            data=data,
        )
        return session, response_stove_info.json()

    def redeem_gift_code(self):
        data_to_encode = {
            "fid": f"{self.stove_info.get('data').get('fid')}",
            "cdk": self.giftcode,
            "captcha_code": self.captcha_solution,
            "time": f"{int(datetime.now().timestamp()*1000)}",
        }
        data = encode_data(data_to_encode)
        response_giftcode = self.req_session.post(wos_giftcode_url, data=data).json()
        self.req_session.close()
        return response_giftcode.get("err_code", 0), response_giftcode.get("msg", "")
