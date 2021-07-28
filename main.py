import gspread
import json
import os
from time import sleep
from datetime import datetime, timezone, timedelta
import requests

# from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from flask import Flask, request, abort, send_from_directory

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_BOT_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_BOT_CHANNEL_SECRET"))


# ServiceAccountCredentials：Googleの各サービスへアクセスできるservice変数を生成します。
from oauth2client.service_account import ServiceAccountCredentials

# 2つのAPIを記述しないとリフレッシュトークンを3600秒毎に発行し続けなければならない
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# 認証情報設定
# ダウンロードしたjsonファイル名をクレデンシャル変数に設定（秘密鍵、Pythonファイルから読み込みしやすい位置に置く）
G_SECRET = os.getenv("G_SECRET")
with open("./secret.json", "w") as f:
    f.write(G_SECRET)

credentials = ServiceAccountCredentials.from_json_keyfile_name("./secret.json", scope)

# OAuth2の資格情報を使用してGoogle APIにログインします。
gc = gspread.authorize(credentials)

# 共有設定したスプレッドシートキーを変数[SPREADSHEET_KEY]に格納する。
SPREADSHEET_KEY = os.getenv("SP_KEY")

# 共有設定したスプレッドシートのシート1を開く


RYO_UID = os.getenv("RYO_UID")  # ryo の UID


def update_taion(temp: str, uid: str):
    if uid == RYO_UID:
        worksheet = gc.open_by_key(SPREADSHEET_KEY).sheet1
    else:
        worksheet = gc.open_by_key(SPREADSHEET_KEY).get_worksheet(1)

    colE = worksheet.col_values(5)
    print(f"colE: {colE}")
    print(f"col values len : {len(colE)}")
    val = worksheet.acell("A1").value
    print(f"get value!: {val}")
    JST = timezone(timedelta(hours=+9), "JST")

    now = datetime.now(JST)  # current date and time
    date_time: str = now.strftime("%Y/%m/%d %H:%M:%S")

    len_p_1: int = len(colE) + 1
    worksheet.update_cell(len_p_1, 5, date_time)
    worksheet.update_cell(len_p_1, 6, temp)


@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print(
            "Invalid signature. Please check your channel access token/channel secret."
        )
        abort(400)

    return "OK"


def download_image(url, timeout=10):
    response = requests.get(url, allow_redirects=False, timeout=timeout)
    if response.status_code != 200:
        e = Exception("HTTP status: " + response.status_code)
        raise e

    content_type = response.headers["content-type"]
    if "image" not in content_type:
        e = Exception("Content-Type: " + content_type)
        raise e

    return response.content


def save_image(filename, image):
    with open(filename, "wb") as fout:
        fout.write(image)


@app.route("/images/<path:path>")
def send_image(path: str):
    return send_from_directory("./", path)


@app.route("/")
def hello():
    str_out = ""
    str_out += "<h2>Hello from Python!</h2>"
    str_out += "<blockquote>"
    str_out += "こんにちは<p />"
    str_out += "</blockquote>"
    str_out += "Aug/07/2017 PM 12:49<br />"
    return str_out


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    temp = event.message.text
    update_taion(temp, event.source.user_id)
    print(f"user id: {event.source.user_id}")

    sleep(4.5)
    now_timestamp: int = int(datetime.now().timestamp())
    if event.source.user_id == RYO_UID:
        image_url = os.getenv("RYO_IMAGE_URL")
        image_data = download_image(image_url)
        save_image(f"ryo_{now_timestamp}.png", image_data)
        uploaded_image_url = (
            f"https://python-taion.herokuapp.com/images/ryo_{now_timestamp}.png"
        )
    else:
        image_url = os.getenv("AI_IMAGE_URL")
        image_data = download_image(image_url)
        save_image(f"aina_{now_timestamp}.png", image_data)
        uploaded_image_url = (
            f"https://python-taion.herokuapp.com/images/aina_{now_timestamp}.png"
        )

    image_message = ImageSendMessage(
        original_content_url=uploaded_image_url,
        preview_image_url=uploaded_image_url,
    )

    line_bot_api.reply_message(event.reply_token, image_message)
    line_bot_api.reply_message(
        event.reply_token, TextMessage(text=f"time: {now_timestamp}")
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
