from datetime import datetime
import pytz

def flex_message_generator(data):
    template = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "款項",
                            "weight": "bold",
                            "size": "sm",
                            "flex": 2,
                        },
                        {
                            "type": "text",
                            "text": "金額",
                            "weight": "bold",
                            "size": "sm",
                            "flex": 2,
                        },
                        {
                            "type": "text",
                            "text": "日期",
                            "weight": "bold",
                            "size": "sm",
                            "flex": 2,
                        },
                    ],
                },
                {"type": "separator", "margin": "md"},
            ],
        },
    }

    for item in data:
        content = {
            "type": "box",
            "layout": "horizontal",
            "margin": "sm", # if i == 0 else "sm",  # first one "md", others "sm"
            "contents": [
                {
                    "type": "text",
                    "text": item['name'],
                    "size": "sm",
                    "flex": 2,
                },
                {
                    "type": "text",
                    "text": str(item['amount']),
                    "size": "sm",
                    "flex": 2,
                },
                {
                    "type": "text",
                    "text": str(datetime.fromisoformat(item['time']).astimezone(pytz.timezone("Asia/Taipei")).date()),
                    "size": "sm",
                    "flex": 2
                },
            ],
        }

        template['body']['contents'].append(content)

    return template
