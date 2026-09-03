$ErrorActionPreference = "Stop"

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "宣讲会日历" `
    app.py

Write-Host "打包完成：dist\宣讲会日历.exe"

