import base64
import hashlib
import hmac
import os
import json
import logging
import inspect

# line-bot-sdk-python v3
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, UnsendEvent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
)

from tools import agent, rollback_transaction


logger = logging.getLogger()
logger.setLevel("INFO")

configuration = Configuration(access_token=os.environ["CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["CHANNEL_SECRET"])


def run_workflow(user_id: str, msg: str, msg_id=None) -> str:
    # Each message must be self-contained and address the bot by name
    if "小鴻" not in msg:
        return ""

    return agent.run_sync(msg, deps=msg_id).output


def _reply(reply_token, message) -> None:
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[message])
        )


def _push(to, message) -> None:
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(to=to, messages=[message])
        )


def rollback_and_push(message_id, source) -> None:
    """Roll back the transaction tied to ``message_id`` and push the result.

    Shared by the unsend event and the quote-reply "收回" recall: LINE blocks
    unsending a message after 24h, so for older messages the user quote-replies
    it instead, and we treat that exactly like an unsend.
    """
    return_text = rollback_transaction(message_id)

    if not return_text:
        return

    logger.info("Sending Text Message")
    target_id = source.group_id if source.type == "group" else source.user_id
    _push(target_id, TextMessage(text=return_text))


def lambda_handler(event, context):
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):

        logger.info(event.source.user_id)

        text = event.message.text
        quoted_id = event.message.quoted_message_id

        # Quote-reply recall: when a message is too old to unsend (LINE's 24h
        # limit), the user quote-replies it with "小鴻" + "收回" to roll it back.
        if quoted_id and "小鴻" in text and "收回" in text:
            logger.info("Quote-reply recall on message %s", quoted_id)
            rollback_and_push(quoted_id, event.source)
            return

        return_text = run_workflow(event.source.user_id, text, event.message.id)

        if return_text != "":
            logger.info(return_text)

            try:
                flex_dict = json.loads(return_text)
                logger.info("Sending Flex Message")
                _reply(
                    event.reply_token,
                    FlexMessage(
                        alt_text="Transaction Summary",
                        contents=FlexContainer.from_dict(flex_dict),
                    ),
                )
            except (json.JSONDecodeError, TypeError):
                logger.info("Sending Text Message")
                _reply(event.reply_token, TextMessage(text=return_text))

    @handler.add(UnsendEvent)
    def handle_unsend_message(event):
        rollback_and_push(event.unsend.message_id, event.source)

    # get X-Line-Signature header value
    signature = event["headers"]["x-line-signature"]

    # get request body as text
    body = event["body"]

    # log the incoming payload (events[].source.userId is the push `to`)
    logger.info("Incoming payload: %s", body)

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