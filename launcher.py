import os
import sys
import threading
import webbrowser
import streamlit.web.cli as stcli


def open_browser():
    webbrowser.open("http://localhost:8503")

if __name__ == "__main__":

    if getattr(sys, "frozen", False):
        base_dir = os.path.join(
            os.path.dirname(sys.executable),
            "_internal"
        )
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_dir, "src", "streamlit_app.py")

    print("BASE =", base_dir)
    print("APP =", app_path)
    print("EXISTS =", os.path.exists(app_path))

    threading.Timer(5, open_browser).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.port=8503",
        "--server.address=127.0.0.1",
        "--server.headless=true",
    ]

    stcli.main()