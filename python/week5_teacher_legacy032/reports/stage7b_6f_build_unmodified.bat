@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "MIC=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\third_party\gym_microrts_legacy032_source\gym_microrts\microrts"
set "STAGE=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\third_party\gym_microrts_legacy032_source\build_stage7b_unmodified"
set "LOG=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage7b_6f_build_stdout.log"
set "ERR=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage7b_6f_build_stderr.log"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%\classes"
if exist "%LOG%" del /f /q "%LOG%"
if exist "%ERR%" del /f /q "%ERR%"
echo Compiling Java sources > "%LOG%"
if exist "%STAGE%\sources.txt" del /f /q "%STAGE%\sources.txt"
for /r "%MIC%\src" %%F in (*.java) do echo %%F>> "%STAGE%\sources.txt"
set "CP="
for %%J in ("%MIC%\lib\*.jar") do set "CP=!CP!;%%~fJ"
set "CP=!CP:~1!"
javac -d "%STAGE%\classes" -cp "%CP%" -sourcepath "%MIC%\src" @"%STAGE%\sources.txt" 1>> "%LOG%" 2>> "%ERR%"
if errorlevel 1 (
  echo JAVAC_EXIT_CODE=%ERRORLEVEL%>> "%LOG%"
  echo BUILD_EXIT_CODE=%ERRORLEVEL%
  exit /b %ERRORLEVEL%
)
copy /y "%MIC%\lib\*.jar" "%STAGE%\classes" >nul
pushd "%STAGE%\classes"
for %%J in (*.jar) do jar xf "%%J" 1>> "%LOG%" 2>> "%ERR%"
del /f /q *.jar
jar cvf "%STAGE%\microrts.jar" * 1>> "%LOG%" 2>> "%ERR%"
set "RC=%ERRORLEVEL%"
popd
echo JAR_EXIT_CODE=%RC%>> "%LOG%"
echo BUILD_EXIT_CODE=%RC%
if exist "%STAGE%\microrts.jar" dir "%STAGE%\microrts.jar"
exit /b %RC%
