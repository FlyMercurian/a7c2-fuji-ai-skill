@echo off
setlocal
if not exist "%~dp0..\assets\runtime\guide\A7C2Guide.exe" (
  echo {"ok":false,"error":"Extract the complete Windows skill package including assets/runtime.","camera_io":false}
  exit /b 2
)
"%~dp0..\assets\runtime\guide\A7C2Guide.exe" %*
exit /b %errorlevel%
