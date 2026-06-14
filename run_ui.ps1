$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot "venv\Scripts\python.exe"
$port = 8501
$url = "http://localhost:$port"

Set-Location $projectRoot

$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("-m", "streamlit", "run", "run_web.py", "--server.port", "$port", "--server.showEmailPrompt", "false") `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden

    for ($i = 0; $i -lt 20; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1
            if ($response.StatusCode -eq 200) { break }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
}

Start-Process $url
Write-Host "FinCompliance-Agent 已打开：$url"
