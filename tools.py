import os
import json
import time
import requests
import random

from pydantic_ai import Agent, RunContext
from supabase import create_client, Client

from line import flex_message_generator

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
SUPABASE_URL = "https://zuxyyrucwalzssdsqdrn.supabase.co"
SUPABASE_KEY = os.environ['SUPABASE_KEY']

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

options = ["greeting", "currency_conversion", "transaction_insert", "balance_check", "transaction_list", "todo_insert", "todo_list"]


system_prompt = f"""
Imagine you are a multi-purpose agent called 小鴻. Your task workflow is the following:

1. Identify your task based on input. The message sent is in Traditional Chinese. There are following task types: {options}

2. Validate Input Fields:
- If the input includes "小鴻", treat it as addressing the agent, not as user data
- For transaction_insert: Check each field (subject/user, amount, name) independently
- If any field cannot be determined, leave it empty ("") or 0 for amount
- Populate all valid fields even if some fields are invalid
- For balance_check: Verify subject (user) is present
- For todo_insert: 
  - If the content after "記" only contains generic terms like "東西", "事情", "事", the item field should be empty
  - Only extract specific tasks/items after these patterns: "記", "記錄", "幫我記"
- For todo_list: 
  - Trigger when user uses any of these phrases:
    * "待辦事項"
    * "待辦"
    * "清單"
    * "代辦"
    * "查看事項"
    * "列出事項"
    * "有什麼事要做"
    * "要做什麼"
    * "該做什麼"

3. For valid fields:
- For transaction_insert, balance_check, and transaction_list identify the subject (user) who is performing the action
- For transaction_insert, include the transaction name

Special Transaction Handling:
提領: Treat as a positive number, as it is cash withdrawal from one's own account
轉帳: Determine if it's income or expense based on context
If a transaction item has a number or symbol, the user will input the number together, place recorded together, ex: 鴻億 AA12保險費 200, place record 'AA12保險' as the name
If a transaction item has a time (month, year, day), the user will input the time information together, place recorded together, ex1: 鴻億 一月學生貸款 200, place record '一月學生貸款' as the name, ex: 鴻億 108年學生貸款 200, place record '108年學生貸款' as the name


JSON Response Structure:
{{
"task": "<task_type>",
"props": {{
    // Task-specific details here
}}
}}

Examples:

Simple Greeting Input: "你好"
Response:
{{
"task": "greeting",
"props": {{}}
}}

Currency Conversion Input: "匯率"
Response:
{{
"task": "currency_conversion",
"props": {{}}
}}

Transaction Insert Input: "鴻傑 500 管理費"
Response:
{{
"task": "transaction_insert",
"props": {{
    "user": "鴻傑",
    "name": "管理費",
    "amount": -500
}}
}}

Balance Check Input: "鴻傑 餘額"
Response:
{{
"task": "balance_check",
"props": {{
    "user": "鴻傑"
}}
}}

TaskRemember Input: "幫我記 辦良民證"
Response:
{{
"task": "todo_insert",
"props": {{
    "item": "辦良民證"
}}
}}

Partial Invalid Input Example (Missing Subject): "支出爸爸紅包 6000"
Response:
{{
"task": "transaction_insert",
"props": {{
    "user": "",
    "name": "爸爸紅包",
    "amount": -6000
}}
}}

Invalid Balance Check (No User Specified): "小鴻餘額"
Response:
{{
"task": "balance_check",
"props": {{
    "user": ""
}}
}}

Additional Transaction Insert Examples:
a. Input: "小明100健康保險費"
Response: {{
"task": "transaction_insert",
"props": {{
    "user": "小明",
    "name": "健康保險",
    "amount": -100
}}
}}
b. Input: "志明130六月貸款"
Response: {{
"task": "transaction_insert",
"props": {{
    "user": "志明",
    "name": "六月貸款",
    "amount": -130
}}
}}
c. Input: "鴻傑150公司獎金"
Response: {{
"task": "transaction_insert",
"props": {{
    "user": "鴻傑",
    "name": "獎金",
    "amount": 150
}}
}}
d. Input: "永志提領150"
Response: {{
"task": "transaction_insert",
"props": {{
    "user": "永志",
    "name": "提領",
    "amount": 150
}}
}}
e. Input: "明德150電話費"
Response: {{
"task": "transaction_insert",
"props": {{
    "user": "明德",
    "name": "電話",
    "amount": -150
}}
}}
f. Input: "春慧1897 023保費"
Response: {{
"task": "transaction_insert",
"props": {{
    "user": "春慧",
    "name": "023保費",
    "amount": -1897
}}
}}
Key Guidelines:
Always parse the input carefully
Extract all relevant information
Include only the columns relevant to the specific task type in the props object
"""

def greeting() -> str:
    """Respond to a simple greeting."""
    return "我是小鴻"

def transaction_insert(ctx: RunContext[str], user: str = "", name: str = "", amount: float = 0) -> str:
    """Record a transaction. amount is signed: expenses negative, income/withdrawal positive.
    Leave a field empty ("" or 0) when it cannot be determined from the message."""
    if user == "":
        return "要記誰的帳？"
    if name == "":
        return "要記什麼款項？"
    if amount == 0:
        return "多少錢？"

    supabase.rpc('insert_transaction', params={"username": user, "name": name, "amount": amount, "msg": ctx.deps}).execute()

    return f"記帳確認: {user} {name} {amount:g}"

def balance_check(user: str = "") -> str:
    """Report a user's balance. Leave user empty ("") when it cannot be determined."""
    if user == "":
        return "誰的餘額？"

    response = supabase.rpc('get_balance_by_user', params={'username': user}).execute()

    return f"{user}餘額: {response.data}"

def transaction_list(user: str = "") -> str:
    """List a user's transactions. Leave user empty ("") when it cannot be determined."""
    if user == "":
        return "誰的餘額？"

    response = supabase.rpc('get_transaction_by_user', params={'username': user}).execute()

    # JSON string; lambda_function parses it into a LINE FlexMessage
    return json.dumps(flex_message_generator(response.data), ensure_ascii=False, indent=2)

def rollback_transaction(msg_id: str) -> str:
    response = (
        supabase.table("Transaction")
            .update({"is_void": True})
            .eq("line_msg_id", msg_id)
            .execute()
    )
    
    if not response.data:
        return None
    
    return_text = f"記帳取消確認"
    return return_text


def todo_insert(item: str = "") -> str:
    """Add a todo item. Leave item empty ("") when only generic terms were given."""
    if item == "":
        return "記什麼呢?"

    supabase.table("Todo").insert({"item": item}).execute()

    return f"記好了 {item}"

def todo_list() -> str:
    """List all todo items."""
    response = supabase.table("Todo").select("item").execute()

    return "- " + "\n- ".join([row['item'] for row in response.data])

def currency_conversion() -> str:
    """Report today's USD/TWD exchange rate."""
    base_url = f"https://v6.exchangerate-api.com/v6/{os.environ['EXCHANGERATE_API_KEY']}/pair/USD/TWD"
    max_retries = 3

    for _ in range(max_retries):
        response = requests.get(base_url)

        if response.status_code == 200:
            res_json = response.json()
       
            return f"今日美金匯率: {res_json['conversion_rate']}"
        
        time.sleep(random.uniform(2, 5)) # Random delay

    return "匯率查詢失敗，請稍後再試"


# The model must finish by calling exactly one of these output functions;
# its return value is the bot's reply (single LLM call, no paraphrasing).
agent = Agent(
    "openai:gpt-4o-mini",
    instructions=system_prompt,
    deps_type=str,  # LINE message id, used by transaction_insert for the unsend feature
    output_type=[greeting, currency_conversion, transaction_insert,
                 balance_check, transaction_list, todo_insert, todo_list],
)