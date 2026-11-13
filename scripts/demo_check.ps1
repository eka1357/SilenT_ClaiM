$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "api"
$WebDir = Join-Path $RepoRoot "web"

$OverallFailed = $false

function Invoke-Step {
    param(
        [string]$Label,
        [scriptblock]$Action
    )
    $global:LASTEXITCODE = 0
    try {
        & $Action *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FAIL: $Label"
            $script:OverallFailed = $true
        } else {
            Write-Host "PASS: $Label"
        }
    } catch {
        Write-Host "FAIL: $Label ($_)"
        $script:OverallFailed = $true
    }
}

# 1. ruff
Invoke-Step "ruff" {
    Push-Location $ApiDir
    try {
        uv run ruff check .
    } finally {
        Pop-Location
    }
}

# 2. pytest (offline)
Invoke-Step "pytest" {
    Push-Location $ApiDir
    $prevOffline = $env:DEMO_OFFLINE
    try {
        $env:DEMO_OFFLINE = "1"
        uv run pytest -q
    } finally {
        $env:DEMO_OFFLINE = $prevOffline
        Pop-Location
    }
}

# 3. pnpm typecheck
Invoke-Step "pnpm typecheck" {
    pnpm --dir $WebDir typecheck
}

# 4. pnpm lint
Invoke-Step "pnpm lint" {
    pnpm --dir $WebDir lint
}

# 5. pnpm lint:design
Invoke-Step "pnpm lint:design" {
    pnpm --dir $WebDir lint:design
}

# 6. pnpm build
Invoke-Step "pnpm build" {
    pnpm --dir $WebDir build
}

# 7. offline e2e
Invoke-Step "offline e2e" {
    pnpm --dir $WebDir test:e2e
}

# 8. GET /api/health
$apiProc = $null
try {
    $alreadyRunning = $false
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            $alreadyRunning = $true
        }
    } catch {
        $alreadyRunning = $false
    }

    if (-not $alreadyRunning) {
        $env:DEMO_OFFLINE = "1"
        $apiProc = Start-Process -FilePath "uv" `
            -ArgumentList "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory $ApiDir `
            -PassThru `
            -WindowStyle Hidden

        $healthy = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Milliseconds 500
            try {
                $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
                if ($resp.status -eq "ok") {
                    $healthy = $true
                    break
                }
            } catch {
                # Wait for startup
            }
        }
        if ($healthy) {
            Write-Host "PASS: GET /api/health"
        } else {
            Write-Host "FAIL: GET /api/health"
            $OverallFailed = $true
        }
    } else {
        Write-Host "PASS: GET /api/health"
    }
} catch {
    Write-Host "FAIL: GET /api/health ($_)"
    $OverallFailed = $true
} finally {
    if ($null -ne $apiProc -and -not $apiProc.HasExited) {
        Stop-Process -Id $apiProc.Id -Force -ErrorAction SilentlyContinue
    }
}

# 9. paytm_spike.py --probe
Invoke-Step "paytm_spike.py --probe" {
    Push-Location $ApiDir
    try {
        uv run python scripts/paytm_spike.py --probe
    } finally {
        Pop-Location
    }
}

if ($OverallFailed) {
    exit 1
}
exit 0
