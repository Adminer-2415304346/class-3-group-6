param([string]$DocumentPath = (Join-Path $PSScriptRoot '..\AI Agent工程实践-开源软件泛读报告.docx'))
$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $DocumentPath).Path
$outputPath = [System.IO.Path]::ChangeExtension($sourcePath, '.pdf')
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordDoc = $wordApp.Documents.Open($sourcePath, $false, $true)
    $wordDoc.Repaginate()
    $wordDoc.ExportAsFixedFormat($outputPath, 17)
    Write-Output $outputPath
}
finally {
    if ($null -ne $wordDoc) {
        $wordDoc.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordDoc)
    }
    if ($null -ne $wordApp) {
        $wordApp.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp)
    }
}
