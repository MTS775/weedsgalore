@echo off
cd /d "%~dp0"

call conda activate weedsgalore-streamlit
if errorlevel 1 (
    echo Could not activate the weedsgalore-streamlit Conda environment.
    echo Run this file from an initialized Anaconda Prompt and check that the environment exists.
    pause
    exit /b 1
)

python -m streamlit run src\streamlit_app.py
set "EXIT_CODE=%ERRORLEVEL%"

pause
exit /b %EXIT_CODE%
