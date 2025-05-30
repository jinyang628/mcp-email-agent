import os
import time

import click
from click import Context

from .config import (
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_RULES_PATH,
    DEFAULT_TOKEN_PATH,
    ensure_dir_exists,
    load_rules,
)
from .gmail import get_email_details, get_gmail_service, get_unread_emails
from .processor import process_email


@click.group()
def cli():
    """MCP-EMAIL-AGENT: A tool to manage your emails."""
    ctx: Context = click.get_current_context()
    ctx.ensure_object(dict)
    ctx.obj["CREDENTIALS_PATH"] = DEFAULT_CREDENTIALS_PATH
    ctx.obj["TOKEN_PATH"] = DEFAULT_TOKEN_PATH
    ctx.obj["RULES_PATH"] = DEFAULT_RULES_PATH

    ensure_dir_exists(ctx.obj["CREDENTIALS_PATH"])
    ensure_dir_exists(ctx.obj["TOKEN_PATH"])
    ensure_dir_exists(ctx.obj["RULES_PATH"])


@cli.command()
@click.pass_context
def auth(ctx):
    """Authorize the application with Google Gmail."""
    click.echo("Attempting to authorize with Google Mail...")
    # CREDENTIALS_PATH is now always the default from ctx.obj
    if not os.path.exists(ctx.obj["CREDENTIALS_PATH"]):
        click.secho(f"Credentials file not found: {ctx.obj['CREDENTIALS_PATH']}", fg="red")
        click.echo(
            "Please download your 'credentials.json' from Google Cloud Console and place it there."
        )
        # Removed the part about specifying with --credentials
        return

    # TOKEN_PATH is now always the default from ctx.obj
    service = get_gmail_service(ctx.obj["CREDENTIALS_PATH"], ctx.obj["TOKEN_PATH"])
    if service:
        click.secho("Successfully authorized and token saved!", fg="green")
        try:
            user_profile = service.users().getProfile(userId="me").execute()
            click.echo(f"Authenticated as: {user_profile.get('emailAddress')}")
        except Exception as e:
            click.secho(f"Could not fetch profile: {e}", fg="yellow")
    else:
        click.secho("Authorization failed. Please check the console output.", fg="red")


@cli.command()
@click.option(
    "--query",
    default="is:unread -label:mcp-processed",  # Or e.g., f"is:unread -label:{APP_NAME.lower()}-processed"
    show_default=True,
    help="Gmail query to fetch emails.",
)
@click.option("--run-once", is_flag=True, help="Run once and exit (for cron jobs).")
@click.option(
    "--interval",
    default=300,
    show_default=True,
    help="Interval in seconds for continuous mode (if not run-once).",
)
@click.pass_context
def run(ctx, query, run_once, interval):
    """Fetch and process emails based on rules."""
    click.echo("Starting MCP email processing...")  # Or "MEA email processing..."

    # RULES_PATH is now always the default from ctx.obj
    rules_config = load_rules(ctx.obj["RULES_PATH"])
    if rules_config is None:
        click.secho("Could not load rules. Exiting.", fg="red")
        return

    # TOKEN_PATH is now always the default from ctx.obj
    if not os.path.exists(ctx.obj["TOKEN_PATH"]):
        click.secho(
            f"Token file not found at {ctx.obj['TOKEN_PATH']}. Please run 'mcp-cli auth' first.",  # Or 'mea auth'
            fg="red",
        )
        return

    # CREDENTIALS_PATH is now always the default from ctx.obj
    service = get_gmail_service(ctx.obj["CREDENTIALS_PATH"], ctx.obj["TOKEN_PATH"])
    if not service:
        click.secho("Failed to connect to Gmail. Exiting.", fg="red")
        return

    click.secho(f"MCP Processing Engine Started. Query: '{query}'", fg="cyan")  # Or "MEA..."

    processed_message_ids_this_session = set()

    def _process_cycle():
        nonlocal processed_message_ids_this_session
        click.echo(f"\n[{time.ctime()}] Checking for emails...")
        messages_info = get_unread_emails(service, query=query)

        if not messages_info:
            click.echo("No new emails matching query to process.")
        else:
            click.echo(f"Found {len(messages_info)} emails to process.")
            for message_stub in messages_info:
                msg_id = message_stub["id"]
                if msg_id in processed_message_ids_this_session:
                    continue

                click.echo(f"Processing email ID: {msg_id}")
                email_details = get_email_details(service, msg_id)
                if email_details:
                    action_taken = process_email(service, email_details, rules_config)
                    if action_taken:
                        # Optional: Add a "mcp-processed" label if your query uses it
                        # from .gmail_client import modify_message_labels, get_label_ids_by_name
                        # processed_label_id = get_label_ids_by_name(service, ["mcp-processed"]) # Or [f"{APP_NAME.lower()}-processed"]
                        # if processed_label_id:
                        #    modify_message_labels(service, msg_id, processed_label_id, [])
                        pass  # Action already logged in process_email
                    processed_message_ids_this_session.add(msg_id)
                else:
                    click.secho(f"Could not fetch details for message {msg_id}", fg="yellow")

        processed_message_ids_this_session.clear()

    if run_once:
        _process_cycle()
        click.secho("Run complete.", fg="green")
    else:
        click.echo(
            f"Running continuously. Checking every {interval} seconds. Press Ctrl+C to stop."
        )
        try:
            while True:
                _process_cycle()
                time.sleep(interval)
        except KeyboardInterrupt:
            click.secho("\nMCP process stopped by user.", fg="yellow")


@cli.command(name="show-paths")
def show_paths():
    """Show fixed paths for config files."""
    click.echo("Config paths used by MCP-EMAIL-AGENT:")
    click.echo(f"  Credentials: {DEFAULT_CREDENTIALS_PATH}")
    click.echo(f"  Token:       {DEFAULT_TOKEN_PATH}")
    click.echo(f"  Rules:       {DEFAULT_RULES_PATH}")
    click.echo("\nThese paths are fixed and determined by your operating system.")


if __name__ == "__main__":
    cli()
