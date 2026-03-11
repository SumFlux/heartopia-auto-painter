from heartopia_app.bootstrap import create_application


def main() -> int:
    context = create_application()
    context.main_window.show()
    return context.app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
