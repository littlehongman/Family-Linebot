import os
from langgraph.graph import StateGraph, START
import redis

from tools import State, insert_todo, intention_bot, greeting, insert_transaction, get_balance_by_user, get_transactions_by_user, get_visa_exchange_rate, list_todo


REDIS_KEY = os.environ["REDIS_KEY"]
redis_store = redis.Redis(host='redis-10664.c273.us-east-1-2.ec2.redns.redis-cloud.com', port=10664, decode_responses=True, username="default", password=REDIS_KEY)

class BotMemory():
    def __init__(self, user_id):
        self.redis = redis_store
        self.user_key = f"user:{user_id}"
    
    def save(self, input_text):
        self.redis.sadd(self.user_key, input_text)
        self.redis.expire(self.user_key, 30)
    
    def get_history(self):
        return " ".join([text for text in self.redis.smembers(self.user_key)])
    
    def clear(self):
        self.redis.delete(self.user_key)



def build_graph():
    graph_builder = StateGraph(State)

    # Add nodes
    graph_builder.add_node("intention_bot", intention_bot)
    graph_builder.add_node("greeting", greeting)
    graph_builder.add_node("transaction_insert", insert_transaction)
    graph_builder.add_node("currency_conversion", get_visa_exchange_rate)
    graph_builder.add_node("balance_check", get_balance_by_user)
    graph_builder.add_node("transaction_list", get_transactions_by_user)
    graph_builder.add_node("todo_insert", insert_todo)
    graph_builder.add_node("todo_list", list_todo)

    # # Add edges
    graph_builder.add_edge(START, "intention_bot")

    graph = graph_builder.compile()

    return graph
