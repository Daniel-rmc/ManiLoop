"""Legacy entry point; retained for existing scripts and tests."""

if __name__ == "__main__":
    from maniloop.cli import main
    import sys

    arguments = sys.argv[1:]
    if "--smoke-test" in arguments:
        arguments.remove("--smoke-test")
        main(["smoke", *arguments])
    else:
        main(["demo", *arguments])
else:
    import sys
    from maniloop.runtime import runner

    sys.modules[__name__] = runner
