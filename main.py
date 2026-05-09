import typer

import configure
from fuzzy_find import fuzzy_find

app = typer.Typer(help="Jira Report Buddy")


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        configure.load()
        options: list[str] = ['Java', 'JavaScript', 'Python', 'PHP', 'C++', 'Erlang', 'Haskell']
        option, index = fuzzy_find(options, title='Please choose your favorite programming language: ')
        print(option)
        print(index)


@app.command()
def init() -> None:
    """Configure Jira connection settings."""
    _ = configure.init()


@app.command()
def setproject() -> None:
    """Select and set the active Jira project."""
    configure.set_project()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
