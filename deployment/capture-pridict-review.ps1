param(
    [string]$DebuggerUrl = "http://127.0.0.1:9223",
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "Administrator",
    [Parameter(Mandatory = $true)]
    [string]$Password,
    [string]$PurchaseOrder = "PUR-ORD-2026-00001",
    [string]$OutputDirectory = "design/review-20260917",
    [int]$ViewportWidth = 1440,
    [int]$ViewportHeight = 1000
)

$ErrorActionPreference = "Stop"
$outputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$targets = (Invoke-WebRequest -UseBasicParsing "$DebuggerUrl/json").Content | ConvertFrom-Json
$target = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
if (-not $target) {
    throw "No Chrome page target is available at $DebuggerUrl."
}

$socket = [Net.WebSockets.ClientWebSocket]::new()
$cancellationToken = [Threading.CancellationToken]::None
$socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, $cancellationToken).GetAwaiter().GetResult()
$script:commandId = 0

function Invoke-Cdp {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [hashtable]$Parameters = @{}
    )

    $script:commandId++
    $id = $script:commandId
    $message = @{ id = $id; method = $Method; params = $Parameters } | ConvertTo-Json -Compress -Depth 20
    $bytes = [Text.Encoding]::UTF8.GetBytes($message)
    $socket.SendAsync(
        [ArraySegment[byte]]::new($bytes),
        [Net.WebSockets.WebSocketMessageType]::Text,
        $true,
        $cancellationToken
    ).GetAwaiter().GetResult()

    do {
        $stream = [IO.MemoryStream]::new()
        do {
            $buffer = [byte[]]::new(65536)
            $received = $socket.ReceiveAsync(
                [ArraySegment[byte]]::new($buffer),
                $cancellationToken
            ).GetAwaiter().GetResult()
            $stream.Write($buffer, 0, $received.Count)
        } while (-not $received.EndOfMessage)

        $response = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
    } while ($response.id -ne $id)

    if ($response.error) {
        throw "$Method failed: $($response.error.message)"
    }

    return $response.result
}

function Invoke-JavaScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Expression,
        [switch]$AwaitPromise
    )

    $result = Invoke-Cdp "Runtime.evaluate" @{
        expression = $Expression
        awaitPromise = [bool]$AwaitPromise
        returnByValue = $true
    }

    if ($result.exceptionDetails) {
        throw "JavaScript evaluation failed: $($result.exceptionDetails.text)"
    }

    return $result.result.value
}

function Wait-ForCondition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Expression,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            if (Invoke-JavaScript $Expression) {
                return
            }
        } catch {
            # Navigation can briefly invalidate the execution context.
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for browser condition: $Expression"
}

function Navigate-To {
    param([Parameter(Mandatory = $true)][string]$Path)

    Invoke-Cdp "Page.navigate" @{ url = "$BaseUrl$Path" } | Out-Null
    Wait-ForCondition "document.readyState === 'complete'"
    Wait-ForCondition "!Array.from(document.querySelectorAll('.freeze, .loading-screen')).some((element) => element.offsetParent !== null && getComputedStyle(element).visibility !== 'hidden')"
    Start-Sleep -Seconds 2
}

function Set-PridictTheme {
    param([ValidateSet("light", "dark")][string]$Theme)

    $expression = @"
(() => {
    document.documentElement.setAttribute('data-theme-mode', '$Theme');
    if (window.frappe?.ui?.set_theme) {
        window.frappe.ui.set_theme('$Theme');
    } else {
        document.documentElement.setAttribute('data-theme', '$Theme');
    }
    window.scrollTo(0, 0);
    return document.documentElement.getAttribute('data-theme');
})()
"@
    Invoke-JavaScript $expression | Out-Null
    Wait-ForCondition "document.documentElement.getAttribute('data-theme') === '$Theme'"
    Start-Sleep -Milliseconds 750
}

function Save-Screenshot {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Route,
        [Parameter(Mandatory = $true)][ValidateSet("light", "dark")][string]$Theme,
        [string]$BeforeCapture = ""
    )

    Navigate-To $Route
    Set-PridictTheme $Theme
    if ($BeforeCapture) {
        Invoke-JavaScript $BeforeCapture | Out-Null
        Start-Sleep -Seconds 1
    }

    $state = Invoke-JavaScript @"
(() => {
    const sidebar = document.querySelector('.layout-side-section');
    const sidebarStyle = sidebar ? getComputedStyle(sidebar) : null;
    return {
        title: document.title,
        url: location.href,
        theme: document.documentElement.getAttribute('data-theme'),
        width: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        bodyText: document.body.innerText.slice(0, 500),
        bodyClass: document.body.className,
        sidebar: sidebar ? {
            className: sidebar.className,
            display: sidebarStyle.display,
            position: sidebarStyle.position,
            width: sidebarStyle.width,
            left: sidebarStyle.left,
            transform: sidebarStyle.transform
        } : null
    };
})()
"@
    $capture = Invoke-Cdp "Page.captureScreenshot" @{
        format = "png"
        fromSurface = $true
        captureBeyondViewport = $false
    }
    $file = Join-Path $outputPath "$Name-$Theme.png"
    [IO.File]::WriteAllBytes($file, [Convert]::FromBase64String($capture.data))

    return [pscustomobject]@{
        screen = $Name
        theme = $Theme
        route = $Route
        file = $file
        title = $state.title
        url = $state.url
        width = $state.width
        scroll_width = $state.scrollWidth
        horizontal_overflow = $state.scrollWidth -gt $state.width
        body_excerpt = $state.bodyText
        body_class = $state.bodyClass
        sidebar = $state.sidebar
    }
}

try {
    Invoke-Cdp "Page.enable" | Out-Null
    Invoke-Cdp "Runtime.enable" | Out-Null
    $userAgent = if ($ViewportWidth -le 600) {
        "Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
    } else {
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    }
    Invoke-Cdp "Emulation.setUserAgentOverride" @{
        userAgent = $userAgent
        platform = if ($ViewportWidth -le 600) { "Android" } else { "Windows" }
    } | Out-Null
    Invoke-Cdp "Emulation.setDeviceMetricsOverride" @{
        width = $ViewportWidth
        height = $ViewportHeight
        deviceScaleFactor = 1
        mobile = $ViewportWidth -le 600
    } | Out-Null

    Invoke-Cdp "Page.navigate" @{ url = "$BaseUrl/api/method/logout" } | Out-Null
    Start-Sleep -Seconds 1
    Navigate-To "/login"
    $escapedUsername = $Username | ConvertTo-Json -Compress
    $escapedPassword = $Password | ConvertTo-Json -Compress
    Invoke-JavaScript @"
(() => {
    const username = document.querySelector('#login_email');
    const password = document.querySelector('#login_password');
    if (!username || !password) return 'already-authenticated';
    username.value = $escapedUsername;
    password.value = $escapedPassword;
    username.dispatchEvent(new Event('input', { bubbles: true }));
    password.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('.btn-login')?.click();
    return 'submitted';
})()
"@ | Out-Null
    Wait-ForCondition "location.pathname.startsWith('/app')" 45

    $screens = @(
        @{ name = "executive-home"; route = "/app/pridict-home"; before = "window.scrollTo(0, 0)" },
        @{ name = "buying-workspace"; route = "/app/buying"; before = "window.scrollTo(0, 0)" },
        @{ name = "purchase-order-list"; route = "/app/purchase-order?company=%5B%22%3D%22%2C%22_Test%20Company%22%5D&status=%5B%22in%22%2C%5B%22To%20Receive%22%2C%22To%20Receive%20and%20Bill%22%5D%5D"; before = "window.scrollTo(0, 0)" },
        @{ name = "purchase-order-form"; route = "/app/purchase-order/$PurchaseOrder"; before = 'document.querySelector("[data-fieldname=items]")?.scrollIntoView({ block: "center" })' },
        @{ name = "profit-and-loss-report"; route = "/app/query-report/Profit%20and%20Loss%20Statement"; before = "window.scrollTo(0, 0)" }
    )

    $evidence = foreach ($screen in $screens) {
        foreach ($theme in @("light", "dark")) {
            Save-Screenshot -Name $screen.name -Route $screen.route -Theme $theme -BeforeCapture $screen.before
        }
    }

    $manifest = Join-Path $outputPath "capture-manifest.json"
    $evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifest -Encoding utf8
    $evidence | Select-Object screen, theme, title, horizontal_overflow, file | Format-Table -AutoSize
    Write-Host "Manifest: $manifest"
} finally {
    $socket.Dispose()
}
