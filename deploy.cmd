@echo off
REM ============================================================
REM  Care Gap Navigator - Databricks bundle deploy
REM  Profile: DEFAULT  (https://dbc-f6607f85-16a2.cloud.databricks.com)
REM  Target : dev      (catalog: dais_hackathon_2026)
REM ============================================================
setlocal enabledelayedexpansion

set "PROFILE=DEFAULT"
set "TARGET=dev"
REM Newer CLIs ship refreshed signing keys for the internal Terraform
REM binary download. Older CLIs hit "openpgp: key expired". 0.260+ is known good.
set "MIN_CLI_MAJOR=0"
set "MIN_CLI_MINOR=260"

where databricks >nul 2>nul
if errorlevel 1 (
    echo [deploy] ERROR: databricks CLI not found on PATH.
    echo [deploy]   Install: winget install Databricks.DatabricksCLI    (or)    scoop install databricks
    exit /b 1
)

for /f "tokens=*" %%v in ('databricks --version') do set "CLI_LINE=%%v"
for /f "tokens=2 delims= " %%v in ("!CLI_LINE!") do set "CLI_VER=%%v"
set "CLI_VER=!CLI_VER:v=!"

for /f "tokens=1,2 delims=." %%a in ("!CLI_VER!") do (
    set "CLI_MAJOR=%%a"
    set "CLI_MINOR=%%b"
)

set "TOO_OLD=0"
if !CLI_MAJOR! LSS !MIN_CLI_MAJOR! set "TOO_OLD=1"
if !CLI_MAJOR! EQU !MIN_CLI_MAJOR! if !CLI_MINOR! LSS !MIN_CLI_MINOR! set "TOO_OLD=1"

if "!TOO_OLD!"=="1" (
    echo [deploy] ERROR: databricks CLI v!CLI_VER! is too old.
    echo [deploy]   Bundle deploys on this CLI hit 'openpgp: key expired' downloading Terraform.
    echo [deploy]   Upgrade: winget upgrade Databricks.DatabricksCLI    (or)    scoop update databricks
    exit /b 1
)
echo [deploy] databricks CLI : v!CLI_VER!

databricks --profile %PROFILE% current-user me >nul 2>nul
if errorlevel 1 (
    echo [deploy] ERROR: profile '%PROFILE%' is not authenticated.
    echo [deploy]   Run: databricks auth login --profile %PROFILE%
    exit /b 1
)

echo.
echo [deploy] Validating bundle ...
databricks --profile %PROFILE% bundle validate --target %TARGET%
if errorlevel 1 exit /b 1

echo.
echo [deploy] Deploying bundle to target '%TARGET%' ...
databricks --profile %PROFILE% bundle deploy --target %TARGET%
if errorlevel 1 exit /b 1

echo.
echo [deploy] Done.
echo [deploy] To run the ETL job:
echo [deploy]   databricks --profile %PROFILE% bundle run care_gap_etl --target %TARGET%
endlocal
