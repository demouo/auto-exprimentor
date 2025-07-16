import random
from ..tools.chat import chat
from ..journal.journals import Journal
from ..journal.nodes import Node
from ..tools.text_processing import *
from ..tools.data_helper import *
from ..tools.interpreter import *
from typing import Callable


DEFAULT_MODEL = "glm-4-flash-250414"
model = "llama3.1:8b-instruct-q8_0"

ExecCallbackType = Callable[[str, bool], ExecutionResult]


class Agent:
    def __init__(self, cfg, journal: Journal):
        super().__init__()
        self.cfg = cfg
        self.journal = journal
        self.data_preview: str | None = None

    def plan_and_code_query(
        self, system_message, user_message, model=DEFAULT_MODEL, retries=3
    ) -> tuple[str, str]:
        """Generate a natural language plan + code in the same LLM call and split them apart."""

        response = None
        for _ in range(retries):

            response = chat(
                _model=model,
                _messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
            )
            code = extract_code(response)
            plan = extract_text_up_to_code(response)

            if code:
                return plan, code

            # Failed
            print("Plan + code extraction failed, retrying...")

        # Final Failed
        print("Final plan + code extraction failed, giving up...")
        return "", response

    def do_draft(self) -> Node:

        # ================ TODO: ask LLM agents to come up with a solution and then implement ================

        system_promt = "You are an AI agent."

        user_prompt = [
            "You have to come up with a solution for machine learning task and then implement this solution in Python.",
            f"The task is to {str(self.cfg.task_goal)} ",
            f'All the provided input data is stored in "{self.cfg.data_dir}" directory.',
            f"{str(self.data_preview)}",
            'You have to save the predictions result on testing set in "/data/submission.csv".',
            "Note that the testing file DOES NOT have the target column.",
            "You should only return the whole analysis and final code.",
        ]
        system_message = system_promt
        user_message = "\n".join(user_prompt)
        plan, code = self.plan_and_code_query(
            system_message=system_message,
            user_message=user_message,
            model=model,
        )
        return Node(plan=plan, code=code)

    def do_improve(self, parent: Node) -> Node:

        # ================= TODO: ask LLM agent to improve the draft ==================
        system_prompt = "You are an AI assistant. Please improve the following task-code to better overcome the task:"

        user_prompt = [
            f"Task description: {str(self.cfg.task_goal)} ",
            f"Memory: {str(self.journal.generate_summary())} ",
            f"Previous solution: Code: {str(wrap_code(parent.code))} ",
            "You should only return the whole analysis and final code.",
        ]
        system_message = system_prompt
        user_message = " ".join(user_prompt)
        plan, code = self.plan_and_code_query(
            system_message=system_message,
            user_message=user_message,
            model=model,
        )
        return Node(plan=plan, code=code, parent=parent)

    def do_debug(self, parent: Node) -> Node:

        # ================ TODO: ask LLM agent to debug ====================
        system_prompt = "You are an LLM agent. Please debug the following task-code to better overcome the task:"

        user_prompt = [
            f"Task description: {str(self.cfg.task_goal)}",
            f"Previous (buggy) implementation: {str(wrap_code(parent.code))}",
            f"Execution output: {str(wrap_code(parent.term_out, lang=''))}",
            f"The revelant data:\n {str(self.data_preview)}",
            "You should only return the whole analysis and final code.",
        ]

        system_message = system_prompt
        user_message = "\n\n".join(user_prompt)

        plan, code = self.plan_and_code_query(
            system_message=system_message,
            user_message=user_message,
            model=model,
        )
        return Node(plan=plan, code=code, parent=parent)

    def update_data_preview(self):
        self.data_preview = data_preview_generate(self.cfg.data_dir)

    def select_node(self) -> Node:
        """Select a node to work on (None if drafting a new node)."""
        search_cfg = self.cfg.agent.search

        # initial drafting
        if len(self.journal.draft_nodes) < search_cfg.num_drafts:
            return None

        # randomly debugging
        if random.random() < search_cfg.debug_prob:
            # buggable & leaf nodes
            debuggable_nodes = [
                node for node in self.journal.buggy_nodes if node.is_leaf
            ]
            if debuggable_nodes:
                return random.choice(debuggable_nodes)

        # improving
        good_nodes = self.journal.good_nodes
        if not good_nodes:
            # there are all buggable nodes, Backing to draft to make a new one.
            return None

        # TODO If the best one now will be the best next?
        best_node = self.journal.best_node
        return best_node

    def step(self, exec_callback: ExecCallbackType):
        if not self.journal.nodes or not self.data_preview:
            self.update_data_preview()

        prev_node = self.select_node()

        if prev_node is None:
            next_node = self.do_draft()
        elif prev_node.is_buggy:
            next_node = self.do_debug(parent=prev_node)
        else:
            next_node = self.do_improve(parent=prev_node)

        self.parse_exec_result(
            node=next_node,
            exec_result=exec_callback(next_node.code, True),
            model=model,
        )

        # update the journal
        self.journal.append(next_node)

    def parse_exec_result(
        self, node: Node, exec_result: ExecutionResult, model=DEFAULT_MODEL
    ):
        node.absorb_exec_result(exec_result)

        system_prompt = "You are an AI assistant."

        # ================  TODO: ask LLM agent to extract evaluation result from the execution output. ================
        # save log file
        user_prompt = [
            f"The task is:\n {self.cfg.task_goal}",
            f"The code implementation is:\n {wrap_code(node.code)}",
            f"The execution output is:\n {wrap_code(node.term_out, lang='')}",
            f"Please summarize the implementation, determine if the code has bug,",
            "and extract the validation MSE metric as a float number if the execution output above shows a metric.",
            'Output in this format: {"summary": "what the code doing and its result", "is_buggy": True or False, "metric": the float metric}',
            "If you can answer it well, you will win 1 million dollar prize!",
        ]

        system_message = system_prompt
        user_message = "\n".join(user_prompt)

        response = chat(
            _model=model,
            _messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        )

        # ================  TODO: evaluation ================
        # you can force the LLM to structure the output to extract the metric
        # reference: https://python.useinstructor.com/integrations/llama-cpp-python/#llama-cpp-python
        # node.analysis = response.summary
        # node.is_buggy = (
        #     response.is_buggy
        #     or node.exc_type is not None
        #     or response.metric is None
        # )
        response = extract_json(response)
        MAX_METRIC = 1000
        if response:
            # right extract
            response = response[0]
            node.analysis = response.get("summary", "The result is null")
            node.is_buggy = (
                node.exc_type
                or response.get("is_buggy", True)
                or response.get("metric", None) is None
            )
            node.metric = response.get("metric", MAX_METRIC)
        else:
            node.is_buggy = True
            node.metric = MAX_METRIC
