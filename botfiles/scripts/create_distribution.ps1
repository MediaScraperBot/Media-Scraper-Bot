# Create Clean Distribution Package
# Run this to create a distribution-ready copy of Media Scraper Bot

$source = $PSScriptRoot
$dest = Join-Path $source "..\Media_Scraper_Bot_v2.0_Distribution"

Write-Host "Creating clean distribution package..." -ForegroundColor Cyan
Write-Host "Source: $source" -ForegroundColor Gray
Write-Host "Destination: $dest" -ForegroundColor Gray
Write-Host ""

# Create destination directories
New-Item -ItemType Directory -Force -Path $dest | Out-Null
New-Item -ItemType Directory -Force -Path "$dest\botfiles" | Out-Null

# Copy essential root files
Write-Host "Copying root files..." -ForegroundColor Yellow
Copy-Item "$source\main.py" $dest -Force
Copy-Item "$source\requirements.txt" $dest -Force
Copy-Item "$source\README.md" $dest -Force

# Copy essential botfiles
Write-Host "Copying botfiles..." -ForegroundColor Yellow
$essentialFiles = @(
    "__init__.py",
    "__main__.py",
    "gui.py",
    "reddit_scraper.py",
    "twitter_scraper.py",
    "website_scraper.py",
    "duplicate_checker.py",
    "history.py",
    "user_manager.py",
    "utils.py",
    "sitemap_scanner.py",
    "download_queue.py"
)

foreach ($file in $essentialFiles) {
    if (Test-Path "$source\botfiles\$file") {
        Copy-Item "$source\botfiles\$file" "$dest\botfiles\" -Force
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Missing: $file" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Distribution package created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Review files in: $dest"
Write-Host "2. Test by running: python main.py"
Write-Host "3. Compress to ZIP for sharing"
Write-Host ""
Write-Host "Users will need to run:" -ForegroundColor Yellow
Write-Host "  pip install -r requirements.txt" -ForegroundColor White
Write-Host "  python main.py" -ForegroundColor White
Write-Host ""

# Open destination folder
Start-Process explorer.exe $dest
