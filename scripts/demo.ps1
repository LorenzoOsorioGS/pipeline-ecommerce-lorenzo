# Demonstração guiada do pipeline (Windows PowerShell).
# Uso, na raiz do projeto:  powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
# Cada passo espera Enter, para dar tempo de explicar o que aparece na tela.
# -SemPausa roda tudo direto (ensaio/teste) e não abre a pasta output no final.
param([switch]$SemPausa)
# "Continue": docker e python escrevem progresso no stderr; quem decide se falhou é o código de saída
$ErrorActionPreference = "Continue"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz
$env:PYTHONIOENCODING = "utf-8"
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

function Passo($titulo) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkCyan
    Write-Host "  $titulo" -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor DarkCyan
    if (-not $SemPausa) { Read-Host "  [Enter para executar]" | Out-Null }
}

function Roda($argumentos) {
    & $py @argumentos
    if ($LASTEXITCODE -ne 0) { throw "falhou: $py $argumentos" }
}

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host ".env criado a partir do .env.example" }

Passo "1/9  Subir a infraestrutura (MongoDB 7 + visualização em http://localhost:8081)"
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw "docker compose falhou" }
    docker compose ps
} else {
    Write-Host "Docker não encontrado: usando o MongoDB portátil (scripts\mongo_local.ps1)" -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File "$raiz\scripts\mongo_local.ps1"
}

Passo "2/9  Começar do zero: apagar o banco 'ecommerce' (só o banco desta demo)"
Roda @("scripts\inspecionar.py", "limpar")

Passo "3/9  EXTRACT – kagglehub → data/raw/ + manifesto (hash, bytes, linhas)"
Roda @("src\main.py", "--step", "extract")

Passo "4/9  VALIDATE – regras V1–V9; rejeitados em output/rejeitados/"
Roda @("src\main.py", "--step", "validate")

Passo "5/9  TRANSFORM – regras T1–T12; Parquet em data/processed/"
Roda @("src\main.py", "--step", "transform")
Get-Content "output\relatorio_qualidade.md" | Select-Object -First 30

Passo "6/9  LOAD – validador `$jsonSchema, upsert em lotes, índices e conciliação"
Roda @("src\main.py", "--step", "load")
Roda @("scripts\inspecionar.py", "contar")

Passo "7/9  Um pedido completo no MongoDB (B-25608: Chennai, 3 categorias, prejuízo > venda)"
Roda @("scripts\inspecionar.py", "pedido", "B-25608")
Write-Host "No navegador: http://localhost:8081/pedidos/B-25608" -ForegroundColor Green

Passo "8/9  IDEMPOTÊNCIA – rodar a carga de novo: 0 inseridos, 0 modificados, contagem igual"
Roda @("src\main.py", "--step", "load")
Roda @("scripts\inspecionar.py", "contar")

Passo "9/9  ANALYZE – aggregations A1–A4 → coleções analytics_* + CSV e PNG em output/"
Roda @("src\main.py", "--step", "analyze")
Get-ChildItem output -File | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "Gráficos: output\a1_meta_realizado.png, a2_pracas.png, a3_venda_casada.png, a4_margem_subcategoria.png" -ForegroundColor Green
if (-not $SemPausa) { Invoke-Item "output" }
