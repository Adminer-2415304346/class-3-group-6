param(
    [Parameter(Mandatory = $true)][string[]]$InputPaths,
    [string]$OutputDirectory = (Join-Path $env:TEMP ('week78-word-preview-' + [guid]::NewGuid().ToString('N')))
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
$word = $null
$document = $null
$records = @()
$privateInstance = $false
try {
    $word = New-Object -ComObject Word.Application
    if ($word.Documents.Count -ne 0) { throw 'Expected an empty private Word instance' }
    $privateInstance = $true
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    foreach ($inputPath in $InputPaths) {
        $source = (Resolve-Path -LiteralPath $inputPath).Path
        $document = $word.Documents.Open($source, $false, $false, $false)
        $document.TrackRevisions = $false
        [void]$document.Fields.Update()
        foreach ($section in $document.Sections) {
            foreach ($footer in $section.Footers) { [void]$footer.Range.Fields.Update() }
        }
        $document.Repaginate()
        $document.Save()
        $number = $records.Count + 1
        $xps = Join-Path $OutputDirectory ('document-' + $number + '.xps')
        $document.ExportAsFixedFormat($xps, 18)
        $pageCount = $document.ComputeStatistics(2)
        $tableCount = $document.Tables.Count
        $document.Close(0)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
        $document = $null
        $records += [pscustomobject]@{
            source = $source
            xps = $xps
            pages = $pageCount
            tables = $tableCount
            sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $index = Join-Path $OutputDirectory 'render-index.json'
    @{ engine = 'Microsoft Word / XPS'; pdf_generated = $false; documents = $records } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $index -Encoding utf8
    Write-Output ('RENDER_INDEX=' + $index)
    $records | Select-Object pages, tables, source | ConvertTo-Json -Depth 3
}
finally {
    if ($document -ne $null) {
        $document.Close(0)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($word -ne $null -and $privateInstance) {
        $word.Quit()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
