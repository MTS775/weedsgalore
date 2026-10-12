@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "CONDA_ACTIVATE=%USERPROFILE%\anaconda3\Scripts\activate.bat"

if not exist "%CONDA_ACTIVATE%" (
    echo Could not find Conda activation script:
    echo %CONDA_ACTIVATE%
    echo Update CONDA_ACTIVATE in this file to match your Anaconda or Miniconda installation.
    pause
    exit /b 1
)

call "%CONDA_ACTIVATE%" weedsgalore-streamlit
if errorlevel 1 (
    echo Could not activate the weedsgalore-streamlit environment.
    pause
    exit /b 1
)

pushd "%PROJECT_DIR%"
if errorlevel 1 (
    echo Could not open the project directory:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

python -m streamlit run src\streamlit_app.py
set "EXIT_CODE=%ERRORLEVEL%"

popd
pause
exit /b %EXIT_CODE%
