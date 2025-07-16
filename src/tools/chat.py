# chat.py

import os
from typing import Callable
from dotenv import load_dotenv

load_dotenv()


class ChatFactory:
    model_base_to_chat_func: dict[str, Callable] = {}

    def __call__(self, _model: str, _messages: list[dict] = []) -> str:
        model_base = self.get_model_base(_model)
        if model_base not in self.model_base_to_chat_func:
            raise ValueError(f"Unsupported model: {_model}")
        return self.model_base_to_chat_func[model_base](
            model=_model,
            messages=_messages,
        )

    def register_model(self, _model: str):
        model_base = self.get_model_base(_model)
        if model_base not in self.model_base_to_chat_func:
            if model_base == "glm":
                from zhipuai import ZhipuAI
                from dotenv import load_dotenv

                load_dotenv()
                api_key = os.getenv("ZHIPU_APIKEY")
                if not api_key:
                    raise ValueError(f"ZHIPU_APIKEY is not set for glm model: {_model}")
                client = ZhipuAI(api_key=api_key)
                chat_func = client.chat.completions.create
                self.model_base_to_chat_func[model_base] = chat_func
            else:
                raise ValueError(f"Unsupported model: {_model}")

    def get_model_base(self, model: str) -> str:
        if "glm" in model:
            return "glm"
        elif "qwen" in model:
            return "qwen"
        elif "llama" in model:
            return "llama"
        else:
            raise ValueError(f"Unsupported model: {model}")


chat_factory = ChatFactory()


def chat(_model: str = "glm-4-flash-250414", _messages: list[dict] = []) -> str:
    chat_factory.register_model(_model)
    response = chat_factory(_model=_model, _messages=_messages)
    return response.choices[0].message.content
