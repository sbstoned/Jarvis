@echo off
setlocal
title JARVIS GitHub Setup
cd /d "%~dp0"
echo ============================================================
echo JARVIS - GITHUB SETUP
echo ============================================================
where git >nul 2>nul
if errorlevel 1 (
  echo Git is not installed. Install Git for Windows first.
  echo https://git-scm.com/download/win
  pause
  exit /b 1
)
git --version
where gh >nul 2>nul
if errorlevel 1 (
  echo GitHub CLI is not installed.
  echo Install with: winget install --id GitHub.cli
  choice /M "Install GitHub CLI now"
  if errorlevel 2 goto skipgh
  winget install --id GitHub.cli
)
:skipgh
where gh >nul 2>nul
if not errorlevel 1 (
  gh auth status
  if errorlevel 1 gh auth login
)
echo.
echo Git identity:
git config --global user.name
git config --global user.email
echo.
echo If blank, configure with:
echo git config --global user.name "Your Name"
echo git config --global user.email "you@example.com"
pause

