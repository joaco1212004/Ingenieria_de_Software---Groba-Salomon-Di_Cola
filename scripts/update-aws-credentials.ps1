[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias("i")]
    [string]$PemPath,

    [Alias("b")]
    [string]$Bucket = $env:BRONZE_BUCKET,

    [Alias("r")]
    [string]$Region = $(if ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "us-east-1" }),

    [string]$AccessKeyId = $env:AWS_ACCESS_KEY_ID,
    [string]$SecretAccessKey = $env:AWS_SECRET_ACCESS_KEY,
    [string]$SessionToken = $env:AWS_SESSION_TOKEN,
    [string]$Ec2User = $(if ($env:EC2_USER) { $env:EC2_USER } else { "ubuntu" }),
    [string]$Ec2Host = $(if ($env:EC2_HOST) { $env:EC2_HOST } else { "api-hidraulicos-tipazos.duckdns.org" }),
    [string]$RemoteAppDir
)

$ErrorActionPreference = "Stop"

function Read-SecretPlain {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not (Test-Path -LiteralPath $PemPath)) {
    throw "No existe la llave PEM: $PemPath"
}

if (-not $Bucket) {
    $Bucket = Read-Host "BRONZE_BUCKET"
}

if (-not $AccessKeyId) {
    $AccessKeyId = Read-Host "AWS_ACCESS_KEY_ID"
}

if (-not $SecretAccessKey) {
    $SecretAccessKey = Read-SecretPlain "AWS_SECRET_ACCESS_KEY"
}

if (-not $SessionToken) {
    $SessionToken = Read-SecretPlain "AWS_SESSION_TOKEN"
}

if (-not $RemoteAppDir) {
    $RemoteAppDir = "/home/$Ec2User/Ingenieria_de_Software---Groba-Salomon-Di_Cola"
}

foreach ($required in @("Bucket", "AccessKeyId", "SecretAccessKey", "SessionToken", "Region")) {
    if (-not (Get-Variable -Name $required -ValueOnly)) {
        throw "Falta completar $required"
    }
}

$remoteEnv = "$RemoteAppDir/.env"
Write-Host "Actualizando .env en ${Ec2Host}:${remoteEnv}..."

$remoteScript = @'
set -euo pipefail

REMOTE_APP_DIR="$1"
BRONZE_BUCKET="$2"
S3_ENDPOINT_URL="$3"
AWS_ACCESS_KEY_ID="$4"
AWS_SECRET_ACCESS_KEY="$5"
AWS_SESSION_TOKEN="$6"
AWS_DEFAULT_REGION="$7"
REMOTE_ENV="${REMOTE_APP_DIR}/.env"

export BRONZE_BUCKET
export S3_ENDPOINT_URL
export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY
export AWS_SESSION_TOKEN
export AWS_DEFAULT_REGION

mkdir -p "$(dirname "$REMOTE_ENV")"
touch "$REMOTE_ENV"
chmod 600 "$REMOTE_ENV"

python3 - "$REMOTE_ENV" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
updates = {
    key: os.environ[key]
    for key in (
        "BRONZE_BUCKET",
        "S3_ENDPOINT_URL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
    )
}

lines = path.read_text().splitlines() if path.exists() else []
seen = set()
out = []

for line in lines:
    key = line.split("=", 1)[0] if "=" in line else None
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text("\n".join(out) + "\n")
PY

echo "  BRONZE_BUCKET actualizado: ${BRONZE_BUCKET}"
echo "  S3_ENDPOINT_URL actualizado para AWS S3 real"
echo "  AWS_ACCESS_KEY_ID actualizado"
echo "  AWS_SECRET_ACCESS_KEY actualizado"
echo "  AWS_SESSION_TOKEN actualizado"
echo "  AWS_DEFAULT_REGION actualizado: ${AWS_DEFAULT_REGION}"

cd "$REMOTE_APP_DIR"

if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d
else
    docker compose up -d
fi
'@

$sshArgs = @(
    "-i", $PemPath,
    "-o", "StrictHostKeyChecking=no",
    "${Ec2User}@${Ec2Host}",
    "bash", "-s", "--",
    $RemoteAppDir,
    $Bucket,
    "",
    $AccessKeyId,
    $SecretAccessKey,
    $SessionToken,
    $Region
)

$remoteScript | & ssh @sshArgs

Write-Host "Listo."
