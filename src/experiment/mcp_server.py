"""Worker-facing MCP tools backed by the same Session used by API runs."""
from threading import RLock

from .storage import BudgetExceeded


def build_server(session):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise RuntimeError("Install MCP support with: uv sync --extra mcp") from None
    server = FastMCP("Preference experiments", instructions=(
        "Call next_task, then create the requested artifact. Use ask_user for clarification, "
        "submit_artifact with complete file contents for review, and revise until status is terminal. "
        "Then call next_task. Use only provided memory across tasks. Private profiles and evaluator assessments "
        "are intentionally unavailable. Do not inspect the experiment server's files."))
    lock = RLock()

    def call(operation, *args):
        with lock:
            try:
                return operation(*args)
            except BudgetExceeded as error:
                session.fail(error)
                return {"error": str(error), **session.status()}
            except ValueError as error:
                if operation in (session.submit_artifact, session.ask_user):
                    session.fail(error)
                return {"error": str(error)}
            except Exception as error:
                session.fail(error)
                return {"error": type(error).__name__, **session.status()}

    @server.tool()
    def next_task() -> dict:
        """Start the next task after finishing the current one; returns public task and learned memory."""
        return call(session.next_task)

    @server.tool()
    def get_task() -> dict:
        """Read the active task, feedback, last submitted files and allowed preference memory."""
        return call(session.get_task)

    @server.tool()
    def ask_user(question: str) -> dict:
        """Ask a bounded clarification question. The answer is recorded and may update memory."""
        return call(session.ask_user, question)

    @server.tool()
    def submit_artifact(files: dict[str, str]) -> dict:
        """Submit ALL deliverable files as relative paths mapped to complete text; receive feedback."""
        return call(session.submit_artifact, files)

    @server.tool()
    def get_status() -> dict:
        """Read progress only; never returns private persona, evaluator scores or server paths."""
        return call(session.status)

    @server.tool()
    def stop_run() -> dict:
        """Stop the experiment. Active and remaining tasks count as interrupted, not successes."""
        def stop():
            session.close("interrupted")
            return session.status()
        return call(stop)

    return server
