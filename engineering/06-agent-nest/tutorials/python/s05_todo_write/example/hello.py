"""A minimal greeting example."""


def greet(name: str) -> None:
    """Print a greeting message for the given name.

    Args:
        name: The name of the person to greet.
    """
    message = "Hello, " + name
    print(message)


def main() -> None:
    """Run the default greeting example."""
    greet("Claude")


if __name__ == "__main__":
    main()
