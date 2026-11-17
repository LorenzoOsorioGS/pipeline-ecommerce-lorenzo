# Alternativa ao docker-compose para máquinas SEM Docker (ver docs/N3/desvios_da_N2.md):
# sobe o MongoDB 7 portátil (zip oficial, sem instalação) em 127.0.0.1:27017 e o visualizador
# somente leitura (scripts/visualizar.py) em http://localhost:8081 — as mesmas portas do compose.
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\mongo_local.ps1          (sobe)
#       powershell -ExecutionPolicy Bypass -File scripts\mongo_local.ps1 -Parar   (para)
# Requer: zip oficial do MongoDB 7 extraído. Caminho do mongod.exe na variável MONGOD_PATH, ou o padrão
#         %USERPROFILE%\tools\mongodb-win32-x86_64-windows-7.0.25\bin\mongod.exe
param([switch]$Parar)
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$dados = Join-Path $raiz ".mongo-local\db"
$logs = Join-Path $raiz ".mongo-local"
$mongod = if ($env:MONGOD_PATH) { $env:MONGOD_PATH } else { "$env:USERPROFILE\tools\mongodb-win32-x86_64-windows-7.0.25\bin\mongod.exe" }
$python = if (Test-Path "$raiz\.venv\Scripts\python.exe") { "$raiz\.venv\Scripts\python.exe" } else { "python" }

function Testa-Porta($porta) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $porta); $c.Close(); return $true } catch { return $false }
}

if ($Parar) {
    Get-Process mongod -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*visualizar.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Output "MongoDB e visualizador parados."
    exit 0
}

if (-not (Test-Path $mongod)) { throw "mongod.exe não encontrado em $mongod. Defina MONGOD_PATH (ver README)." }
New-Item -ItemType Directory -Force $dados | Out-Null

if (Testa-Porta 27017) {
    Write-Output "MongoDB já está respondendo em 127.0.0.1:27017."
} else {
    Start-Process -FilePath $mongod -WindowStyle Hidden -ArgumentList @(
        "--dbpath", "`"$dados`"", "--bind_ip", "127.0.0.1", "--port", "27017",
        "--logpath", "`"$logs\mongod.log`"", "--logappend")
    for ($i = 0; $i -lt 40 -and -not (Testa-Porta 27017); $i++) { Start-Sleep -Milliseconds 500 }
    if (-not (Testa-Porta 27017)) { throw "MongoDB não subiu; veja $logs\mongod.log" }
    Write-Output "MongoDB 7 rodando em 127.0.0.1:27017 (dados em .mongo-local\db)."
}

if (Testa-Porta 8081) {
    Write-Output "Visualizador já está em http://localhost:8081"
} else {
    Start-Process -FilePath $python -WindowStyle Hidden -ArgumentList "`"$raiz\scripts\visualizar.py`""
    for ($i = 0; $i -lt 20 -and -not (Testa-Porta 8081); $i++) { Start-Sleep -Milliseconds 500 }
    Write-Output "Visualizador (somente leitura) em http://localhost:8081"
}
