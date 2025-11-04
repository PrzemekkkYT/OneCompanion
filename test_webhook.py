import requests

webhook_data = {
    "username": "One Companion GiftCodes",
    "avatar_url": "https://cdn.discordapp.com/avatars/1403357392149942292/caaff7835a12e42af80d38415095aa3d.png?size=1024",
    "content": "test",
}

if __name__ == "__main__":
    WEBHOOK_ID = "1434898414440550410"
    WEBHOOK_TOKEN = (
        "W-2-v_hqMpgff8NXN9S4WFX-jq0R5tyxvcw2NY_UY4O5ZPEK-yN-_3ReG4itIlfubw6s"
    )

    response = requests.post(
        f"https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}",
        json=webhook_data,
        params={"with_components": True},
    )

    print(response.text)
