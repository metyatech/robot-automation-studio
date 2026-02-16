param(
    [string]$Owner = "metyatech",
    [string]$Repo = "robot-automation-studio",
    [string]$Branch = "main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$requiredChecks = @(
    "verify",
    "analyze (python)",
    "gitleaks"
)

$payload = @{
    required_status_checks = @{
        strict   = $true
        contexts = $requiredChecks
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismiss_stale_reviews           = $true
        require_code_owner_reviews      = $false
        required_approving_review_count = 1
    }
    restrictions                   = $null
    required_linear_history        = $false
    allow_force_pushes             = $false
    allow_deletions                = $false
    block_creations                = $false
    required_conversation_resolution = $true
    lock_branch                    = $false
    allow_fork_syncing             = $true
}

$tmpPath = [System.IO.Path]::GetTempFileName()
try {
    $json = $payload | ConvertTo-Json -Depth 8
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tmpPath, $json, $utf8NoBom)
    $null = gh api `
        --method PUT `
        -H "Accept: application/vnd.github+json" `
        "/repos/$Owner/$Repo/branches/$Branch/protection" `
        --input $tmpPath
    if ($LASTEXITCODE -ne 0) {
        throw "gh api failed with exit code $LASTEXITCODE."
    }
    Write-Host "Branch protection updated for $Owner/$Repo ($Branch)."
}
finally {
    if (Test-Path $tmpPath) {
        Remove-Item $tmpPath -Force
    }
}
