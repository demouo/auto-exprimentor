from auto_exprimentor.config.config import cfg
from auto_exprimentor.agent.agents import Agent
from auto_exprimentor.journal.journals import Journal
from auto_exprimentor.tools.interpreter import Interpreter
from auto_exprimentor.journal.saver import save_run
import logging

logging.basicConfig(level=logging.INFO)


def main():

    def exec_callback(*args, **kwargs):
        res = interpreter.run(*args, **kwargs)
        return res

    interpreter = Interpreter()
    journal = Journal()
    agent = Agent(cfg=cfg, journal=journal)

    step = len(journal)
    while step < cfg.agent.steps:
        agent.step(exec_callback=exec_callback)
        save_run(cfg=cfg, journal=journal)
        step = step + 1

    interpreter.cleanup_session()


if __name__ == "__main__":
    main()
