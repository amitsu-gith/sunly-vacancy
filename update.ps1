# 毎朝の更新スクリプト（Windows タスクスケジューラから実行）
#   powershell -ExecutionPolicy Bypass -File update.ps1
# 手順: CSV置き場から取り込み → vacancy.json 生成 → GitHub Pages へ push
$ErrorActionPreference = 'Stop'
$Repo   = Split-Path -Parent $MyInvocation.MyCommand.Path
$CsvDir = 'G:\共有ドライブ\VAIO\Claude Code\work\clients\サンリー\base\faboc'   # ファボックCSVの置き場（手動ダウンロード先）
$InDir  = Join-Path $Repo 'input'

New-Item -ItemType Directory -Force $InDir | Out-Null
foreach ($f in 'trunkroom.csv', 'operatingstatus.csv') {
    $src = Join-Path $CsvDir $f
    if (-not (Test-Path $src)) { throw "CSVがありません: $src" }
    Copy-Item $src (Join-Path $InDir $f) -Force
}

Set-Location $Repo
python build_vacancy.py --csv-dir $InDir --out docs
if ($LASTEXITCODE -ne 0) { throw 'build_vacancy.py が失敗しました' }

git add docs
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m ("空室状況更新 " + (Get-Date -Format 'yyyy-MM-dd HH:mm'))
    git push
    Write-Host '公開しました'
} else {
    Write-Host '変更なし'
}
