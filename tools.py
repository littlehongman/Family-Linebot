import os
import json
import pytz
import requests
from typing import Dict
from datetime import datetime, timedelta
from supabase import create_client, Client
from prettytable import PrettyTable

from typing import Dict, Literal
from typing_extensions import TypedDict

from langgraph.graph import END, MessagesState
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from line import flex_message_generator

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
SUPABASE_URL = "https://zuxyyrucwalzssdsqdrn.supabase.co"
SUPABASE_KEY = os.environ['SUPABASE_KEY']

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

options = ["greeting", "currency_conversion", "transaction_insert", "balance_check", "transaction_list", "todo_insert", "todo_list"]

class State(MessagesState):
    task: Literal[*options] # type: ignore
    props: Dict
    keep_alive: bool # If the bot should keep the conversation

class Router(TypedDict):
    task: Literal[*options] # type: ignore
    props: Dict


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

llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)


def intention_bot(state: State) -> Command[Literal[*options, "__end__"]]: # type: ignore
    # Check if previous conversation is store in redis

    messages = [
        {"role": "system", "content": system_prompt},
    ] + state["messages"]

    response = llm.with_structured_output(Router).invoke(messages)

    print(response)
    
    goto = response["task"]

    if goto == "FINISH":
        goto = END
    
    return Command(goto=goto, update={'props': response['props'], 'keep_alive': False})

def preprocess_message(text: str) -> str:
    text = text.replace("小鴻", '')
    text = text.strip()
    
    return text

def greeting(state):
    return_text = "我是小鴻"
    return Command(goto=END, update={"messages": [ HumanMessage(content=return_text) ], 'keep_alive': True})

def insert_transaction(state) -> str:
    return_text = ""
    keep_alive = True

    if state['props']['user'] == "":
        return_text = "要記誰的帳？"
    elif state['props']['name'] == "":
        return_text = "要記什麼款項？"
    elif state['props']['amount'] == 0:
        return_text = "多少錢？"
    else:
        response = supabase.rpc('insert_transaction', params={'username': state['props']['user'], "name": state['props']['name'], "amount": state['props']['amount']}).execute()

        keep_alive = False
        return_text = f"記帳確認: {state['props']['user']} {state['props']['name']} {state['props']['amount']}"
   
    return Command(goto=END, update={"messages": [ HumanMessage(content=return_text) ], 'keep_alive': keep_alive })

def get_balance_by_user(state):
    return_text = ""
    keep_alive = True

    if state['props']['user'] == "":
        return_text = "誰的餘額？"

    else:
        response = supabase.rpc('get_balance_by_user', params={'username': state['props']['user']}).execute()

        keep_alive = False
        return_text =  f"{state['props']['user']}餘額: {response.data}"

    return Command(goto=END, update={"messages": [ HumanMessage(content=return_text) ], 'keep_alive': keep_alive})

def get_transactions_by_user(state) -> str:

    def create_table_string(data):
        table = PrettyTable()
        table.field_names = ["款項", "金額"]
        
        for item in data:
            table.add_row([item['name'], item['amount']])
        
        table.align["款項"] = "l"  # Left align the Name column
        table.align["金額"] = "r"  # Right align the Amount column
        
        return table.get_string()
    
    return_text = ""
    keep_alive = True

    if 'user' not in state['props'] or state['props']['user'] == "":
        return_text = "誰的餘額？"
    
    else:
        response = supabase.rpc('get_transaction_by_user', params={'username': state['props']['user']}).execute()

        keep_alive = False
        return_message = json.dumps(flex_message_generator(response.data), ensure_ascii=False, indent=2)

    return Command(goto=END, update={"messages": [ HumanMessage(content=return_message) ], 'keep_alive': keep_alive })

def insert_todo(state):
    return_text = ""
    keep_alive = True

    if 'item' not in state['props'] or state['props']['item'] == "":
        return_text = "記什麼呢?"

    else:
        response = supabase.table("Todo").insert({"item": state['props']['item']}).execute()

        return_text = f"記好了 {state['props']['item']}"
        keep_alive = False

    return Command(goto=END, update={"messages": [ HumanMessage(content=return_text) ], 'keep_alive': keep_alive })

def list_todo(state):
    return_text = ""
    keep_alive = True


    response = supabase.table("Todo").select("item").execute()
    return_text = "- " + "\n- ".join([row['item'] for row in response.data])
    keep_alive = False

    return Command(goto=END, update={"messages": [ HumanMessage(content=return_text) ], 'keep_alive': keep_alive })

def get_visa_exchange_rate(state, from_curr='TWD', to_curr='USD', amount=1):
    base_url = "https://usa.visa.com/cmsapi/fx/rates"
    current_date = datetime.now(pytz.timezone('America/New_York'))
    max_retries = 3

    def format_date(date):
        return date.strftime('%m/%d/%Y')
    
    for _ in range(max_retries):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://usa.visa.com',
            'Referer': 'https://usa.visa.com/support/consumer/travel-support/exchange-rate-calculator.html',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        params = {
            'amount': amount,
            'fee': 0,
            'utcConvertedDate': format_date(current_date),
            'exchangedate': format_date(current_date),
            'fromCurr': from_curr,
            'toCurr': to_curr
        }

        response = requests.get(base_url, params=params, headers=headers, verify=False)

        if response.status_code == 200:
            res_json = response.json()
       
            return_text = f"今日美金匯率: {res_json['originalValues']['toAmountWithVisaRate']}"
            return Command(goto=END, update={"messages": [ HumanMessage(content=return_text) ]})
        
        current_date -= timedelta(days=1)
    
    raise Exception(f"Failed to get exchange rate after {max_retries} retries") 