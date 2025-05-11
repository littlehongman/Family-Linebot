from tools import preprocess_message
from graph import BotMemory, build_graph


def run_workflow(user_id: str, msg: str) -> str:
    
    bot_memory = BotMemory(user_id)
    bot_memory.save(msg)
    chat = bot_memory.get_history()

    if "小鴻" in chat:
        graph = build_graph()
        res = graph.invoke({"messages":[{"role": "user", "content": chat}]})

        if res['keep_alive'] == False:
            bot_memory.clear()

        return res['messages'][-1].content
    
    return ""


if __name__ == "__main__":
    result = run_workflow("123", "小鴻 鴻傑 明細")
    print(result)