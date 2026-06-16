@echo off
REM ============================================================
REM  Care Gap Navigator - Databricks bundle deploy
REM  Profile: DEFAULT  (https://dbc-f6607f85-16a2.cloud.databricks.com)
REM  Target : dev      (catalog: dais_hackathon_2026)
REM
REM  Steps:
REM    1. Sanity-check CLI version + auth
REM    2. bundle validate
REM    3. bundle deploy
REM    4. bundle run care_gap_etl --no-wait    (fire-and-forget)
REM    5. apps stop  (best-effort)
REM    6. apps start (waits for RUNNING, prints URL)
REM
REM  Skip steps with env vars:
REM    set SKIP_ETL=1 & deploy.cmd
REM    set SKIP_APP=1 & deploy.cmd
REM ============================================================
setlocal enabledelayedexpansion

set "PROFILE=DEFAULT"
set "TARGET=dev"

REM Per-developer namespace for the deployed Bundle, Job, and App.
if not defined APP_PREFIX (
    if defined USERNAME (set "APP_PREFIX=%USERNAME%") else (set "APP_PREFIX=pradeep")
)
for /f "delims=" %%i in ('powershell -NoProfile -Command "$env:APP_PREFIX.ToLower() -replace '[^a-z0-9-]','-' -replace '^-+|-+$',''"') do set "APP_PREFIX=%%i"
echo [deploy] app_prefix     : !APP_PREFIX!

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

set "APP_NAME=!APP_PREFIX!-care-gap-navigator"
set "JOB_NAME=!APP_PREFIX!-care-gap-etl"

REM -- 1. Validate -------------------------------------------------------
echo.
echo [deploy] (1/5) Validating bundle ...
databricks --profile %PROFILE% bundle validate --target %TARGET% --var="app_prefix=!APP_PREFIX!"
if errorlevel 1 exit /b 1

REM -- 2. Deploy ---------------------------------------------------------
echo.
echo [deploy] (2/5) Deploying bundle to target '%TARGET%' ...
databricks --profile %PROFILE% bundle deploy --target %TARGET% --var="app_prefix=!APP_PREFIX!"
if errorlevel 1 exit /b 1

REM -- 3. Trigger ETL (fire-and-forget) ---------------------------------
if "%SKIP_ETL%"=="1" (
    echo.
    echo [deploy] (3/5) SKIP_ETL=1 -- skipping ETL trigger.
) else (
    echo.
    echo [deploy] (3/5) Triggering ETL job '!JOB_NAME!' ^(fire-and-forget^) ...
    databricks --profile %PROFILE% bundle run care_gap_etl --target %TARGET% --var="app_prefix=!APP_PREFIX!" --no-wait
    if errorlevel 1 (
        echo [deploy] WARN: ETL trigger failed. Continuing -- bundle is deployed.
        echo [deploy]       Run manually: databricks --profile %PROFILE% bundle run care_gap_etl --target %TARGET% --var="app_prefix=!APP_PREFIX!"
    )
)

REM -- 4 & 5. Restart App -----------------------------------------------
if "%SKIP_APP%"=="1" (
    echo.
    echo [deploy] (4/5) SKIP_APP=1 -- skipping App restart.
    echo [deploy] Done.
    endlocal
    exit /b 0
)

REM Read state. Fresh deploys won't have a running app yet -- that's fine.
set "APP_STATE=UNKNOWN"
for /f "delims=" %%s in ('databricks --profile %PROFILE% apps get !APP_NAME! 2^>nul ^| powershell -NoProfile -Command "$j = $input ^| ConvertFrom-Json; if ($j) { if ($j.compute_status.state) { $j.compute_status.state } elseif ($j.app_status.state) { $j.app_status.state } else { 'UNKNOWN' } }"') do set "APP_STATE=%%s"
echo.
echo [deploy] (4/5) App '!APP_NAME!' state: !APP_STATE!

if "!APP_STATE!"=="RUNNING" (
    echo [deploy]       Stopping for clean restart so new code loads ...
    databricks --profile %PROFILE% apps stop !APP_NAME! >nul 2>nul
)
if "!APP_STATE!"=="STARTING" (
    echo [deploy]       Stopping for clean restart so new code loads ...
    databricks --profile %PROFILE% apps stop !APP_NAME! >nul 2>nul
)

echo.
echo [deploy] (5/5) Starting App '!APP_NAME!' ...
databricks --profile %PROFILE% apps start !APP_NAME! >nul 2>nul

REM Poll up to 5 minutes for RUNNING.
set "DEADLINE_LOOPS=60"
:wait_app
set /a DEADLINE_LOOPS=!DEADLINE_LOOPS!-1
if !DEADLINE_LOOPS! lss 0 goto wait_done
for /f "delims=" %%s in ('databricks --profile %PROFILE% apps get !APP_NAME! 2^>nul ^| powershell -NoProfile -Command "$j = $input ^| ConvertFrom-Json; if ($j) { if ($j.compute_status.state) { $j.compute_status.state } elseif ($j.app_status.state) { $j.app_status.state } else { 'UNKNOWN' } }"') do set "APP_STATE=%%s"
if "!APP_STATE!"=="RUNNING" goto wait_done
if "!APP_STATE!"=="ACTIVE"  goto wait_done
if "!APP_STATE!"=="ERROR"   (echo [deploy] ERROR: App entered !APP_STATE!. Check `databricks apps logs !APP_NAME!`. & exit /b 1)
if "!APP_STATE!"=="FAILED"  (echo [deploy] ERROR: App entered !APP_STATE!. Check `databricks apps logs !APP_NAME!`. & exit /b 1)
<nul set /p =.
timeout /t 5 /nobreak >nul
goto wait_app
:wait_done
echo.

set "APP_URL="
for /f "delims=" %%u in ('databricks --profile %PROFILE% apps get !APP_NAME! 2^>nul ^| powershell -NoProfile -Command "$j = $input ^| ConvertFrom-Json; if ($j -and $j.url) { $j.url }"') do set "APP_URL=%%u"

echo.
echo [deploy] Done.
echo [deploy]   ETL job   : !JOB_NAME!  ^(running in background^)
echo [deploy]   App       : !APP_NAME!  ^(state: !APP_STATE!^)
if defined APP_URL echo [deploy]   App URL   : !APP_URL!
echo [deploy]
echo [deploy] Watch ETL progress:
echo [deploy]   databricks --profile %PROFILE% bundle open --target %TARGET% care_gap_etl
endlocal
