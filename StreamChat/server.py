import threading
import queue

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

from langchain.chat_models import ChatOpenAI
from langchain.callbacks.manager  import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from langchain.schema import (
    HumanMessage,
    SystemMessage,
    AIMessage
)

from langchain.memory import ConversationBufferMemory

app = FastAPI(
    title="Demo chat",
)

memory = [SystemMessage(content="You are a helpful assistant.")]

class ThreadedGenerator:
    def __init__(self):
        self.queue = queue.Queue()
        self.msg = []

    def __iter__(self):
        return self

    def __next__(self):
        item = self.queue.get()
        if item is StopIteration:
            raise item
        return item

    def send(self, data):
        self.queue.put(data)
        self.msg += [data]

    def close(self):
        self.queue.put(StopIteration)


class ChainStreamHandler(StreamingStdOutCallbackHandler):
    def __init__(self, gen):
        super().__init__()
        self.gen = gen

    def on_llm_new_token(self, token: str, **kwargs):
        self.gen.send(token)


def llm_thread(g, prompt):
    global memory
    try:
        chat = ChatOpenAI(verbose=True,streaming=True,
            callback_manager=CallbackManager([ChainStreamHandler(g)]),
            # temperature=0.7,
        )
        memory.append(HumanMessage(content=prompt))
        chat(memory)
        # chat([SystemMessage(content="You are a helpful assistant."),HumanMessage(content=prompt)])
    except Exception as e:
        g.send(str(e))
    finally:
        memory.append(AIMessage(content=''.join(g.msg)))
        g.close()


def chat(prompt):
    g = ThreadedGenerator()
    threading.Thread(target=llm_thread, args=(g, prompt)).start()
    return g


@app.get("/test-stream")
async def stream():
    return StreamingResponse(
        chat("Do you know vuejs?"),
        media_type='text/event-stream'
    )

@app.post("/ask")
def ask(body: dict={'question':'How are you?'}):
    return StreamingResponse(chat(body['question']), media_type="text/event-stream")

@app.get("/")
async def homepage():
    global memory
    memory = [SystemMessage(content="You are a helpful assistant.")]
    return FileResponse('statics/index.html')


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
