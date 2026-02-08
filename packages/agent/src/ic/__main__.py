"""Entry point for the IC CLI agent."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="ic",
        description="IC Agent - AI CLI Coding Assistant",
    )
    parser.add_argument(
        "--resume", "-r",
        help="Resume a previous project by ID",
    )
    parser.add_argument(
        "--model", "-m",
        help="Model to use (e.g. openai, anthropic, deepseek, custom)",
    )
    parser.add_argument(
        "--prompt", "-p",
        help="Run a single prompt and exit (non-interactive mode)",
    )
    args = parser.parse_args()

    from ic.config import Config
    from ic.app import App

    config = Config.load()

    if args.model and args.model in config.models:
        config.default_model = args.model

    app = App(config=config)

    if args.prompt:
        asyncio.run(_run_single(app, args.prompt))
    else:
        asyncio.run(app.run(resume_project=args.resume))


async def _run_single(app, prompt: str):
    """Run a single prompt in non-interactive mode."""
    if not app.config.models:
        app.console.print_error("No API keys configured.")
        return

    project = app.store.create()
    workspace = app.store.workspace_dir(project.id)
    app.engine = app._create_engine(workspace)
    app.console.start_streaming()
    app._streaming_started = True
    try:
        result = await app.engine.run_turn(prompt)
        app.console.end_streaming()
        if result.usage:
            app.console.print_usage(result.usage)
    except Exception as e:
        app.console.end_streaming()
        app.console.print_error(str(e))


if __name__ == "__main__":
    main()
