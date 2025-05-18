import base64
import hashlib
import hmac
import os
import json
import logging
import inspect

# line-bot-sdk-python v2.0.0
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage

from graph import BotMemory, build_graph


logger = logging.getLogger()
logger.setLevel("INFO")

line_bot_api = LineBotApi(os.environ["CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["CHANNEL_SECRET"])


def run_workflow(user_id: str, msg: str) -> str:

    bot_memory = BotMemory(user_id)
    bot_memory.save(msg)
    chat = bot_memory.get_history()

    if "小鴻" in chat:
        graph = build_graph()
        res = graph.invoke({"messages": [{"role": "user", "content": chat}]})

        if res["keep_alive"] == False:
            bot_memory.clear()

        return res["messages"][-1].content

    return ""


def lambda_handler(event, context):
    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):

        logger.info(event.source.user_id)

        return_text = run_workflow(event.source.user_id, event.message.text)

        if return_text != "":
            logger.info(return_text)

            try:
                flex_dict = json.loads(return_text)
                logger.info("Sending Flex Message")
                line_bot_api.reply_message(
                    event.reply_token,
                    FlexSendMessage(alt_text="Transaction Summary", contents=flex_dict),
                )
            except (json.JSONDecodeError, TypeError):
                logger.info("Sending Text Message")
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text=return_text)
                )

    # get X-Line-Signature header value
    signature = event["headers"]["x-line-signature"]

    # get request body as text
    body = event["body"]

    # handle webhook body
    try:
        secret = os.environ["CHANNEL_SECRET"]
        body = event["body"]
        received_sig = event["headers"].get("x-line-signature")

        hash = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
        expected_sig = base64.b64encode(hash).decode()

        if not hmac.compare_digest(received_sig, expected_sig):
            raise InvalidSignatureError

        handler.handle(body, signature)

    except InvalidSignatureError:
        return {
            "statusCode": 502,
            "body": json.dumps(
                "Invalid signature. Please check your channel access token/channel secret."
            ),
        }
    return {"statusCode": 200, "body": json.dumps("Hello from Line!")}
