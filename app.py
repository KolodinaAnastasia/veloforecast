import argparse
from importlib.metadata import version
from zoneinfo import ZoneInfo


def check_environment():
    for package in ("numpy", "pandas", "scikit-learn", "joblib", "requests", "tzdata"):
        print(f"{package}: {version(package)}")

    timezone = ZoneInfo("America/New_York")
    print(f"Часовой пояс: {timezone.key}")
    print("Окружение готово.")


def main():
    parser = argparse.ArgumentParser(
        description="Veloforecast — прогноз спроса на городской велопрокат"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Проверить окружение")
    check.set_defaults(run=check_environment)

    args = parser.parse_args()
    args.run()


if __name__ == "__main__":
    main()