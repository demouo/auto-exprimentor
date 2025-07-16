"""
DO NOT MODIFY THIS CELL

Python interpreter for executing code snippets and capturing their output.
"""

import logging
import os
import queue
import signal
import sys
import time
import traceback
import zipfile
from pathlib import Path
from shutil import rmtree
import shutil
from multiprocessing import Process, Queue
from typing import Hashable, cast

import humanize
import rich
import shutup
from rich.logging import RichHandler
from rich.syntax import Syntax
from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin


@dataclass
class ExecutionResult(DataClassJsonMixin):
    """
    Result of executing a code snippet in the interpreter.
    Contains the output, execution time, and exception information.
    """

    term_out: list[str]
    exec_time: float
    exc_type: str | None
    exc_info: dict | None = None
    exc_stack: list[tuple] | None = None


def exception_summary(e, exec_file_name):
    """Generates a string that summarizes an exception and its stack trace"""
    tb_lines = traceback.format_exception(e)
    # Combine the traceback lines into a single string, skipping lines that contain "importlib".
    tb_str = "".join(
        [
            line
            for line in tb_lines
            # if "importlib" not in line  # Filter out unwanted traceback lines.
        ]
    )

    exc_info = {}
    if hasattr(e, "args"):
        exc_info["args"] = [
            str(i) for i in e.args
        ]  # Store the exception arguments as strings.
    for att in ["name", "msg", "obj"]:
        if hasattr(e, att):
            exc_info[att] = str(
                getattr(e, att)
            )  # Store additional attributes if available.

    tb = traceback.extract_tb(e.__traceback__)  # Extract the traceback information.
    # Create a list of tuples for each frame in the traceback.
    exc_stack = [(t.filename, t.lineno, t.name, t.line) for t in tb]

    return (
        tb_str,
        e.__class__.__name__,
        exc_info,
        exc_stack,
    )  # Return the formatted traceback and exception details.


# Define a class that redirects write operations to a multiprocessing queue.
class RedirectQueue:
    def __init__(self, queue, timeout=5):
        self.queue = queue  # Store the provided queue.
        self.timeout = timeout  # Set the timeout for queue operations.

    def write(self, msg):
        try:
            self.queue.put(
                msg, timeout=self.timeout
            )  # Attempt to put the message into the queue.
        except queue.Full:
            print.warning(
                "Queue write timed out"
            )  # Warn if the queue is full and the write times out.

    def flush(self):
        pass  # No operation is needed for flushing in this context.


# Define the Interpreter class that simulates a standalone Python REPL.
class Interpreter:
    def __init__(
        self,
        timeout: int = 3600,  # Default timeout of 3600 seconds.
        agent_file_name: str = "runfile.py",  # Default file name for writing the agent's code.
    ):
        """
        Simulates a standalone Python REPL with an execution time limit.

        Args:
            timeout (int, optional): Timeout for each code execution step. Defaults to 3600.
            agent_file_name (str, optional): The name for the agent's code file. Defaults to "runfile.py".
        """
        self.timeout = timeout  # Save the timeout value.
        self.agent_file_name = agent_file_name  # Save the agent file name.
        self.process: Process = (
            None  # Initialize the process attribute (will hold the child process).
        )

    def child_proc_setup(self, result_outq: Queue) -> None:
        # Import shutup to suppress warnings in the child process.
        import shutup

        shutup.mute_warnings()  # Mute all warnings before further execution.

        # Redirect both stdout and stderr to the provided result queue.
        # trunk-ignore(mypy/assignment)
        sys.stdout = sys.stderr = RedirectQueue(result_outq)

    def _run_session(
        self, code_inq: Queue, result_outq: Queue, event_outq: Queue
    ) -> None:
        self.child_proc_setup(
            result_outq
        )  # Set up the child process for capturing output.

        global_scope: dict = (
            {}
        )  # Create an empty dictionary to serve as the global scope.
        while True:  # Continuously wait for new code to execute.
            code = code_inq.get()  # Retrieve code from the code input queue.
            with open(
                self.agent_file_name, "w"
            ) as f:  # Open the agent file for writing.
                f.write(code)  # Write the received code into the file.

            event_outq.put(
                ("state:ready",)
            )  # Signal that the interpreter is ready to execute the code.
            try:
                # Compile and execute the code within the global scope.
                exec(compile(code, self.agent_file_name, "exec"), global_scope)
            except BaseException as e:
                # If an exception occurs, generate a summary of the exception.
                tb_str, e_cls_name, exc_info, exc_stack = exception_summary(
                    e,
                    self.agent_file_name,
                )
                result_outq.put(
                    tb_str
                )  # Put the traceback string into the result queue.
                if e_cls_name == "KeyboardInterrupt":
                    e_cls_name = "TimeoutError"  # Convert a KeyboardInterrupt into a TimeoutError.

                event_outq.put(
                    ("state:finished", e_cls_name, exc_info, exc_stack)
                )  # Signal that execution finished with an error.
            else:
                event_outq.put(
                    ("state:finished", None, None, None)
                )  # Signal that execution finished successfully.

            os.remove(self.agent_file_name)  # Remove the agent file after execution.

            result_outq.put(
                "<|EOF|>"
            )  # Put an EOF marker to indicate the end of output.

    def create_process(self) -> None:
        # Create three queues for communication with the child process:
        # - code_inq: for sending code to execute.
        # - result_outq: for receiving output from the execution.
        # - event_outq: for receiving state events (like ready and finished).
        # trunk-ignore(mypy/var-annotated)
        self.code_inq, self.result_outq, self.event_outq = Queue(), Queue(), Queue()
        self.process = Process(
            target=self._run_session,  # Set the target function for the child process.
            args=(
                self.code_inq,
                self.result_outq,
                self.event_outq,
            ),  # Provide the necessary queues as arguments.
        )
        self.process.start()  # Start the child process.

    def cleanup_session(self):
        if self.process is None:  # If there is no process, nothing to clean up.
            return
        try:
            # Attempt to terminate the child process gracefully.
            self.process.terminate()  # Request the process to terminate.
            self.process.join(
                timeout=0.5
            )  # Wait for the process to finish with a 0.5-second timeout.

            if self.process.exitcode is None:  # If the process is still running,
                self.process.kill()  # Forcefully kill the process.
                self.process.join(timeout=0.5)  # Wait again for termination.

                if (
                    self.process.exitcode is None
                ):  # If the process still hasn't terminated,
                    os.kill(self.process.pid, signal.SIGKILL)  # Send a SIGKILL signal.
        except Exception as e:
            print(
                f"Error during process cleanup: {e}"
            )  # Print an error message if cleanup fails.
        finally:
            if self.process is not None:  # If the process exists,
                self.process.close()  # Close the process.
                self.process = None  # Reset the process attribute to None.

    def run(self, code: str, reset_session=True) -> ExecutionResult:
        """
        Execute the provided Python command in a separate process and return its output.

        Parameters:
            code (str): Python code to execute.
            reset_session (bool, optional): Whether to reset the interpreter session before executing the code. Defaults to True.

        Returns:
            ExecutionResult: Object containing the output and metadata of the code execution.
        """

        if reset_session:
            if self.process is not None:
                # If a previous process exists, clean it up before starting a new one.
                self.cleanup_session()
            self.create_process()  # Create a new child process.
        else:
            # For the first execution, reset_session must be True.
            assert self.process is not None

        assert self.process.is_alive()  # Ensure that the child process is running.

        self.code_inq.put(code)  # Send the code to the child process via the queue.

        # Wait for the child process to signal that it is ready.
        try:
            state = self.event_outq.get(
                timeout=10
            )  # Wait up to 10 seconds for the "state:ready" event.
        except queue.Empty:
            msg = "REPL child process failed to start execution"
            # print.critical(msg)  # Log a critical error if the process does not start.
            while not self.result_outq.empty():
                continue  # Drain the result queue.
            raise RuntimeError(msg) from None
        assert (
            state[0] == "state:ready"
        ), state  # Verify that the received state is "state:ready".
        start_time = time.time()  # Record the start time of execution.

        child_in_overtime = (
            False  # Flag to indicate if the child process has exceeded the timeout.
        )

        while True:
            try:
                # Try to get the finished state from the child process.
                state = self.event_outq.get(
                    timeout=1
                )  # Wait for the "state:finished" event.
                assert (
                    state[0] == "state:finished"
                ), state  # Ensure the state is "state:finished".
                exec_time = (
                    time.time() - start_time
                )  # Calculate the total execution time.
                break  # Exit the loop if execution is finished.
            except queue.Empty:
                # If no event is received, check whether the process is still alive.
                if not child_in_overtime and not self.process.is_alive():
                    msg = "REPL child process died unexpectedly"
                    raise RuntimeError(msg) from None

                # If the process is still running, check if it has exceeded the timeout.
                if self.timeout is None:
                    continue
                running_time = time.time() - start_time  # Determine the running time.
                if running_time > self.timeout:
                    print(
                        f"Execution exceeded timeout of {self.timeout}s"
                    )  # Log a timeout message.
                    os.kill(
                        self.process.pid, signal.SIGINT
                    )  # Send SIGINT to the process.
                    child_in_overtime = (
                        True  # Mark that the process is now in overtime.
                    )

                    # If the process exceeds the timeout by more than 5 seconds, force cleanup.
                    if running_time > self.timeout + 5:
                        self.cleanup_session()  # Clean up the child process.

                        state = (
                            None,
                            "TimeoutError",
                            {},
                            [],
                        )  # Set state to indicate a timeout error.
                        exec_time = (
                            self.timeout
                        )  # Set the execution time to the timeout limit.
                        break

        output: list[str] = []  # Initialize a list to collect output lines.
        # Collect all output from the result queue until the EOF marker is encountered.
        start_collect = time.time()  # Record the start time for output collection.
        while not self.result_outq.empty() or not output or output[-1] != "<|EOF|>":
            try:
                # If output collection exceeds 5 seconds, log a warning.
                if time.time() - start_collect > 5:
                    print.warning("Output collection timed out")
                    break
                output.append(
                    self.result_outq.get(timeout=1)
                )  # Append the next line of output.
            except queue.Empty:
                continue  # Continue if no output is available immediately.
        output.pop()  # Remove the EOF marker from the output list.

        # Extract exception information from the finished state.
        e_cls_name, exc_info, exc_stack = state[1:]

        if e_cls_name == "TimeoutError":
            # Append a timeout error message to the output if a timeout occurred.
            output.append(
                f"TimeoutError: Execution exceeded the time limit of {humanize.naturaldelta(self.timeout)}"
            )
        else:
            # Append the execution time information to the output.
            output.append(
                f"Execution time: {humanize.naturaldelta(exec_time)} seconds (time limit is {humanize.naturaldelta(self.timeout)})."
            )
        # Return an ExecutionResult object with all the execution details.
        return ExecutionResult(output, exec_time, e_cls_name, exc_info, exc_stack)
