import subprocess
import sys


def newer_python():
    return sys.version_info >= (3, 11)


def install_requirements():
    try:
        if newer_python():
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements-3_11.txt"])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("All requirements have been installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while installing requirements: {e}")


def main():
    install_requirements()
    try:
        import db_creation.create_db
        from src import db_access
    except ImportError as e:
        print(f"Error occurred while importing the module: {e}")
    except AttributeError as e:
        print(f"Error occurred while calling the function: {e}")


if __name__ == '__main__':
    main()
