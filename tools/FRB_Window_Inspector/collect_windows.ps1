# FRB Window / Process Inspector v1.0
# Windows 10/11, Windows PowerShell 5.1+; read-only diagnostics.
[CmdletBinding()]
param(
    [ValidateSet('Snapshot', 'Monitor')]
    [string]$Mode = 'Snapshot',
    [ValidateRange(3, 600)]
    [int]$DurationSeconds = 30,
    [ValidateRange(100, 5000)]
    [int]$IntervalMs = 250,
    [string]$FocusRegex = '(?i)obsidian|code|frb|launch|python|pyw|sakura|notepad',
    [string]$OutputRoot = '',
    [switch]$IncludeCommandLine
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# Resolve the report destination after parameter binding. In some Windows PowerShell
# invocation contexts, $PSScriptRoot is not populated while param defaults evaluate.
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $scriptFile = $MyInvocation.MyCommand.Path
    if ([string]::IsNullOrWhiteSpace($scriptFile)) {
        throw 'Cannot resolve the script path. Supply -OutputRoot explicitly.'
    }
    $OutputRoot = Join-Path -Path (Split-Path -Path $scriptFile -Parent) -ChildPath 'reports'
}

if (-not ('FRBWindowInspectorNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class FRBWindowInspectorNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }
    public delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumProc callback, IntPtr lParam);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr lParam);
    [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="GetWindowTextW", ExactSpelling=true)]
    private static extern int GetWindowTextW(IntPtr hwnd, StringBuilder text, int maxCount);
    [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="GetWindowTextLengthW", ExactSpelling=true)]
    private static extern int GetWindowTextLengthW(IntPtr hwnd);
    [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="GetClassNameW", ExactSpelling=true)]
    private static extern int GetClassNameW(IntPtr hwnd, StringBuilder name, int maxCount);
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsZoomed(IntPtr hwnd);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")]
    private static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")]
    private static extern IntPtr GetWindow(IntPtr hwnd, uint command);
    [DllImport("user32.dll")]
    private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetCursorPos(out POINT point);
    [DllImport("user32.dll")]
    private static extern IntPtr WindowFromPoint(POINT point);
    [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")]
    private static extern IntPtr GetWindowLongPtr64(IntPtr hwnd, int index);
    [DllImport("user32.dll", EntryPoint="GetWindowLongW")]
    private static extern int GetWindowLong32(IntPtr hwnd, int index);
    [DllImport("dwmapi.dll")]
    private static extern int DwmGetWindowAttribute(IntPtr hwnd, int attribute, out int value, int size);

    public static IntPtr[] TopWindows() {
        var list = new List<IntPtr>();
        EnumWindows(delegate(IntPtr h, IntPtr p) { list.Add(h); return true; }, IntPtr.Zero);
        return list.ToArray();
    }
    public static IntPtr[] Children(IntPtr parent) {
        var list = new List<IntPtr>();
        EnumChildWindows(parent, delegate(IntPtr h, IntPtr p) { list.Add(h); return true; }, IntPtr.Zero);
        return list.ToArray();
    }
    public static string Text(IntPtr h) {
        int length = GetWindowTextLengthW(h);
        var sb = new StringBuilder(Math.Max(256, Math.Min(length + 2, 8192)));
        GetWindowTextW(h, sb, sb.Capacity);
        return sb.ToString();
    }
    public static string Class(IntPtr h) {
        var sb = new StringBuilder(512);
        GetClassNameW(h, sb, sb.Capacity);
        return sb.ToString();
    }
    public static uint ProcessId(IntPtr h) { uint pid; GetWindowThreadProcessId(h, out pid); return pid; }
    public static uint ThreadId(IntPtr h) { uint pid; return GetWindowThreadProcessId(h, out pid); }
    public static bool Visible(IntPtr h) { return IsWindowVisible(h); }
    public static bool Minimized(IntPtr h) { return IsIconic(h); }
    public static bool Maximized(IntPtr h) { return IsZoomed(h); }
    public static IntPtr Parent(IntPtr h) { return GetParent(h); }
    public static IntPtr Owner(IntPtr h) { return GetWindow(h, 4); }
    public static IntPtr Root(IntPtr h) { return GetAncestor(h, 2); }
    public static IntPtr Foreground() { return GetForegroundWindow(); }
    public static POINT CursorPosition() { POINT p; GetCursorPos(out p); return p; }
    public static IntPtr WindowAt(POINT p) { return WindowFromPoint(p); }
    public static RECT Bounds(IntPtr h) { RECT rect; GetWindowRect(h, out rect); return rect; }
    public static string Cloaked(IntPtr h) {
        try { int value; int rc = DwmGetWindowAttribute(h, 14, out value, 4);
              return rc == 0 ? value.ToString() : "unknown"; }
        catch { return "unknown"; }
    }
    public static string LongHex(IntPtr h, int index) {
        long value = IntPtr.Size == 8 ? GetWindowLongPtr64(h, index).ToInt64() : GetWindowLong32(h, index);
        return "0x" + unchecked((uint)value).ToString("X8");
    }
    public static string Hex(IntPtr h) { return "0x" + h.ToInt64().ToString("X"); }
}
'@ -ErrorAction Stop
}

function Get-ProcessInventory {
    $result = New-Object 'System.Collections.Generic.List[object]'
    try {
        $items = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        foreach ($proc in $items) {
            $created = ''
            if ($null -ne $proc.CreationDate) { $created = [string]$proc.CreationDate }
            $command = ''
            if ($IncludeCommandLine) { $command = [string]$proc.CommandLine }
            $result.Add([pscustomobject]@{
                PID = [int]$proc.ProcessId
                ParentPID = [int]$proc.ParentProcessId
                Name = [string]$proc.Name
                ExecutablePath = [string]$proc.ExecutablePath
                CreationDate = $created
                SessionID = [int]$proc.SessionId
                WorkingSetMB = [math]::Round(([double]$proc.WorkingSetSize / 1MB), 1)
                CommandLine = $command
            })
        }
    } catch {
        Write-Warning ('CIM unavailable; reduced process fields: ' + $_.Exception.Message)
        foreach ($proc in @(Get-Process)) {
            $result.Add([pscustomobject]@{
                PID = [int]$proc.Id; ParentPID = 0; Name = [string]$proc.ProcessName
                ExecutablePath = ''; CreationDate = ''; SessionID = 0
                WorkingSetMB = [math]::Round(([double]$proc.WorkingSet64 / 1MB),1)
                CommandLine = ''
            })
        }
    }
    return $result.ToArray()
}

function New-ProcessNameIndex([object[]]$processes) {
    $map = @{}
    foreach ($proc in $processes) { $map[[int]$proc.PID] = [string]$proc.Name }
    return $map
}

function Refresh-ProcessNames([hashtable]$map) {
    try {
        foreach ($proc in @(Get-Process -ErrorAction Stop)) {
            $map[[int]$proc.Id] = [string]$proc.ProcessName
        }
    } catch { }
}

function New-WindowEntry([IntPtr]$handle, [string]$kind, [hashtable]$processMap, [int]$zRank = -1) {
    $windowProcessId = [int][FRBWindowInspectorNative]::ProcessId($handle)
    $name = ''
    if ($processMap.ContainsKey($windowProcessId)) { $name = [string]$processMap[$windowProcessId] }
    $r = [FRBWindowInspectorNative]::Bounds($handle)
    $h = [FRBWindowInspectorNative]::Hex($handle)
    return [pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Kind = $kind
        ZRank = $zRank
        HWND = $h
        PID = $windowProcessId
        ProcessName = $name
        ThreadID = [int][FRBWindowInspectorNative]::ThreadId($handle)
        Title = [FRBWindowInspectorNative]::Text($handle)
        ClassName = [FRBWindowInspectorNative]::Class($handle)
        Visible = [FRBWindowInspectorNative]::Visible($handle)
        Cloaked = [FRBWindowInspectorNative]::Cloaked($handle)
        Minimized = [FRBWindowInspectorNative]::Minimized($handle)
        Maximized = [FRBWindowInspectorNative]::Maximized($handle)
        Foreground = ($handle -eq [FRBWindowInspectorNative]::Foreground())
        ParentHWND = [FRBWindowInspectorNative]::Hex([FRBWindowInspectorNative]::Parent($handle))
        OwnerHWND = [FRBWindowInspectorNative]::Hex([FRBWindowInspectorNative]::Owner($handle))
        RootHWND = [FRBWindowInspectorNative]::Hex([FRBWindowInspectorNative]::Root($handle))
        Left = $r.Left
        Top = $r.Top
        Right = $r.Right
        Bottom = $r.Bottom
        Width = $r.Right - $r.Left
        Height = $r.Bottom - $r.Top
        Style = [FRBWindowInspectorNative]::LongHex($handle, -16)
        ExStyle = [FRBWindowInspectorNative]::LongHex($handle, -20)
        # Read-only: WS_EX_TOPMOST is bit 0x8 of the Win32 extended style.
        # Captured for ALL windows; the shared timeline exposes only the
        # immediate/intersecting neighbors of the focused editor/workspace.
        Topmost = (([Convert]::ToUInt32(
            ([FRBWindowInspectorNative]::LongHex($handle, -20)).Substring(2), 16) -band 0x8) -ne 0)
    }
}

function Test-FocusedWindow($window) {
    return (([string]$window.ProcessName -match $FocusRegex) -or
            ([string]$window.Title -match $FocusRegex) -or
            ([string]$window.ClassName -match $FocusRegex))
}

function Get-WindowInventory([hashtable]$processMap, [bool]$children) {
    $list = New-Object 'System.Collections.Generic.List[object]'
    $seen = New-Object 'System.Collections.Generic.HashSet[string]'
    $zRank = 0
    foreach ($hwnd in [FRBWindowInspectorNative]::TopWindows()) {
        $item = New-WindowEntry $hwnd 'TopLevel' $processMap $zRank
        $zRank++
        if ($seen.Add($item.HWND)) { $list.Add($item) }
        if ($children -and (Test-FocusedWindow $item)) {
            foreach ($child in [FRBWindowInspectorNative]::Children($hwnd)) {
                $entry = New-WindowEntry $child 'Child' $processMap
                if ($seen.Add($entry.HWND)) { $list.Add($entry) }
            }
        }
    }
    return $list.ToArray()
}

# Read-only focused Z-order diagnostic. EnumWindows lists top-level windows from
# highest to lowest Z order. The nearest visible predecessor is NOT necessarily
# an occluder; the cursor hit and geometry give additional evidence.
function Get-FocusedZOrderSamples([object[]]$topWindows, [int]$sampleNumber) {
    $rows = New-Object 'System.Collections.Generic.List[object]'
    $byHwnd = @{}
    foreach ($w in $topWindows) { $byHwnd[[string]$w.HWND] = $w }

    $point = [FRBWindowInspectorNative]::CursorPosition()
    $hit = [FRBWindowInspectorNative]::WindowAt($point)
    $hitRoot = [FRBWindowInspectorNative]::Root($hit)
    $hitHwnd = [FRBWindowInspectorNative]::Hex($hit)
    $hitRootHwnd = [FRBWindowInspectorNative]::Hex($hitRoot)
    $frontHwnd = [FRBWindowInspectorNative]::Hex([FRBWindowInspectorNative]::Foreground())
    $hitRootWindow = $null
    $frontWindow = $null
    if ($byHwnd.ContainsKey($hitRootHwnd)) { $hitRootWindow = $byHwnd[$hitRootHwnd] }
    if ($byHwnd.ContainsKey($frontHwnd)) { $frontWindow = $byHwnd[$frontHwnd] }

    foreach ($w in $topWindows) {
        if (-not (Test-FocusedWindow $w)) { continue }
        $nearest = $null
        $aboveCursor = $null
        $overlapping = $null
        $rank = [int]$w.ZRank
        for ($i = ($rank - 1); $i -ge 0; $i--) {
            $prev = $topWindows[$i]
            $cloak = [string]$prev.Cloaked
            if (-not $prev.Visible -or $prev.Minimized -or ($cloak -ne '0' -and $cloak -ne 'unknown')) { continue }
            if ($null -eq $nearest) { $nearest = $prev }
            # Geometric overlap is a stronger clue than mere stack order.
            # Does not assume anything about alpha, window regions or DWM.
            if ($null -eq $overlapping -and
                [math]::Min($prev.Right, $w.Right) -gt [math]::Max($prev.Left, $w.Left) -and
                [math]::Min($prev.Bottom, $w.Bottom) -gt [math]::Max($prev.Top, $w.Top)) {
                $overlapping = $prev
            }
            if ($null -eq $aboveCursor -and
                $point.X -ge $prev.Left -and $point.X -lt $prev.Right -and
                $point.Y -ge $prev.Top -and $point.Y -lt $prev.Bottom) {
                $aboveCursor = $prev
            }
        }
        $rows.Add([pscustomobject]@{
            Timestamp = (Get-Date).ToString('o')
            Sample = $sampleNumber
            HWND = $w.HWND
            PID = $w.PID
            ProcessName = $w.ProcessName
            Title = $w.Title
            ClassName = $w.ClassName
            ZRank = $w.ZRank
            Visible = $w.Visible
            Cloaked = $w.Cloaked
            Topmost = $w.Topmost
            ExStyle = $w.ExStyle
            Foreground = $w.Foreground
            NearestVisibleAboveHWND = $(if ($null -ne $nearest) { $nearest.HWND } else { '' })
            NearestVisibleAboveProcess = $(if ($null -ne $nearest) { $nearest.ProcessName } else { '' })
            NearestVisibleAboveClass = $(if ($null -ne $nearest) { $nearest.ClassName } else { '' })
            NearestVisibleAboveZRank = $(if ($null -ne $nearest) { $nearest.ZRank } else { -1 })
            NearestVisibleAboveTopmost = $(if ($null -ne $nearest) { $nearest.Topmost } else { $false })
            NearestVisibleAboveExStyle = $(if ($null -ne $nearest) { $nearest.ExStyle } else { '' })
            NearestOverlappingAboveHWND = $(if ($null -ne $overlapping) { $overlapping.HWND } else { '' })
            NearestOverlappingAboveProcess = $(if ($null -ne $overlapping) { $overlapping.ProcessName } else { '' })
            NearestOverlappingAboveZRank = $(if ($null -ne $overlapping) { $overlapping.ZRank } else { -1 })
            NearestOverlappingAboveTopmost = $(if ($null -ne $overlapping) { $overlapping.Topmost } else { $false })
            NearestOverlappingAboveExStyle = $(if ($null -ne $overlapping) { $overlapping.ExStyle } else { '' })
            AboveCursorHWND = $(if ($null -ne $aboveCursor) { $aboveCursor.HWND } else { '' })
            AboveCursorProcess = $(if ($null -ne $aboveCursor) { $aboveCursor.ProcessName } else { '' })
            AboveCursorClass = $(if ($null -ne $aboveCursor) { $aboveCursor.ClassName } else { '' })
            AboveCursorTopmost = $(if ($null -ne $aboveCursor) { $aboveCursor.Topmost } else { $false })
            CursorX = $point.X
            CursorY = $point.Y
            HitHWND = $hitHwnd
            HitRootHWND = $hitRootHwnd
            HitRootProcess = $(if ($null -ne $hitRootWindow) { $hitRootWindow.ProcessName } else { '' })
            HitRootClass = $(if ($null -ne $hitRootWindow) { $hitRootWindow.ClassName } else { '' })
            ForegroundHWND = $frontHwnd
            ForegroundProcess = $(if ($null -ne $frontWindow) { $frontWindow.ProcessName } else { '' })
            ForegroundZRank = $(if ($null -ne $frontWindow) { $frontWindow.ZRank } else { -1 })
            ForegroundTopmost = $(if ($null -ne $frontWindow) { $frontWindow.Topmost } else { $false })
        })
    }
    return $rows.ToArray()
}

function New-Event([string]$type, $win, [string]$detail) {
    return [pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Event = $type
        HWND = [string]$win.HWND
        PID = [int]$win.PID
        ProcessName = [string]$win.ProcessName
        ClassName = [string]$win.ClassName
        Title = [string]$win.Title
        Detail = $detail
        Rect = ('{0},{1} {2}x{3}' -f $win.Left, $win.Top, $win.Width, $win.Height)
        Visible = [string]$win.Visible
        ParentHWND = [string]$win.ParentHWND
        OwnerHWND = [string]$win.OwnerHWND
    }
}

function Save-Csv([object[]]$items, [string]$path) {
    if ($items.Count -eq 0) {
        [System.IO.File]::WriteAllText($path, '', ([System.Text.UTF8Encoding]::new($true)))
        return
    }
    $items | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding UTF8
}

function Save-Json($data, [string]$path) {
    $value = ConvertTo-Json -InputObject $data -Depth 8
    [System.IO.File]::WriteAllText($path, $value, ([System.Text.UTF8Encoding]::new($true)))
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$dest = Join-Path $OutputRoot ('FRB_WindowReport_' + $Mode + '_' + $stamp)
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$hostVersion = $PSVersionTable.PSVersion.ToString()
Write-Host ('[FRB Window Inspector] ' + $Mode) -ForegroundColor Cyan
Write-Host ('Report folder: ' + $dest)
Write-Host ('Focus regex: ' + $FocusRegex)
Write-Host ('CommandLine collection: ' + [bool]$IncludeCommandLine)

$processesBefore = @(Get-ProcessInventory)
$names = New-ProcessNameIndex $processesBefore
$windowsBefore = @(Get-WindowInventory $names $true)
$events = New-Object 'System.Collections.Generic.List[object]'
$zOrderTimeline = New-Object 'System.Collections.Generic.List[object]'
$sampleNumber = 0

if ($Mode -eq 'Monitor') {
    Write-Host ("MONITOR: for {0}s / {1}ms sampling. Trigger your app action now." -f $DurationSeconds, $IntervalMs) -ForegroundColor Yellow
    $previous = @{}
    $initialTop = @(Get-WindowInventory $names $false)
    foreach ($w in $initialTop) { $previous[$w.HWND] = $w }
    foreach ($row in @(Get-FocusedZOrderSamples $initialTop $sampleNumber)) { $zOrderTimeline.Add($row) }
    $lastForeground = [FRBWindowInspectorNative]::Hex([FRBWindowInspectorNative]::Foreground())
    $started = Get-Date
    $refreshAt = Get-Date
    while (((Get-Date) - $started).TotalSeconds -lt $DurationSeconds) {
        Start-Sleep -Milliseconds $IntervalMs
        if ((Get-Date) -ge $refreshAt) {
            Refresh-ProcessNames $names
            $refreshAt = (Get-Date).AddSeconds(2)
        }
        $sampleNumber++
        $now = @{}
        $currentTop = @(Get-WindowInventory $names $false)
        foreach ($row in @(Get-FocusedZOrderSamples $currentTop $sampleNumber)) { $zOrderTimeline.Add($row) }
        foreach ($w in $currentTop) {
            $now[$w.HWND] = $w
            if (-not $previous.ContainsKey($w.HWND)) {
                $events.Add((New-Event 'NEW_TOP_LEVEL' $w ''))
            } else {
                $old = $previous[$w.HWND]
                if ($old.Visible -ne $w.Visible -or $old.Cloaked -ne $w.Cloaked) {
                    $events.Add((New-Event 'VISIBILITY_CHANGED' $w ("from visible={0},cloaked={1}" -f $old.Visible, $old.Cloaked)))
                }
                if ($old.Left -ne $w.Left -or $old.Top -ne $w.Top -or $old.Width -ne $w.Width -or $old.Height -ne $w.Height) {
                    $events.Add((New-Event 'RECT_CHANGED' $w ("from {0},{1} {2}x{3}" -f $old.Left, $old.Top, $old.Width, $old.Height)))
                }
                if ($old.Title -ne $w.Title) {
                    $events.Add((New-Event 'TITLE_CHANGED' $w ('from ' + $old.Title)))
                }
            }
        }
        foreach ($oldKey in @($previous.Keys)) {
            if (-not $now.ContainsKey($oldKey)) {
                $events.Add((New-Event 'GONE_FROM_TOP_LEVEL' $previous[$oldKey] 'Could be closed, hidden by reparenting, or destroyed. Check final child windows.'))
            }
        }
        $front = [FRBWindowInspectorNative]::Hex([FRBWindowInspectorNative]::Foreground())
        if ($front -ne $lastForeground -and $now.ContainsKey($front)) {
            $events.Add((New-Event 'FOREGROUND_CHANGED' $now[$front] ('from ' + $lastForeground)))
        }
        $lastForeground = $front
        $previous = $now
    }
    Write-Host ("Monitor complete; {0} window events captured." -f $events.Count) -ForegroundColor Green
}

$processesAfter = @(Get-ProcessInventory)
$names = New-ProcessNameIndex $processesAfter
$windowsAfter = @(Get-WindowInventory $names $true)
if ($Mode -eq 'Snapshot') {
    $snapshotTop = @($windowsAfter | Where-Object { $_.Kind -eq 'TopLevel' })
    foreach ($row in @(Get-FocusedZOrderSamples $snapshotTop $sampleNumber)) { $zOrderTimeline.Add($row) }
}
$focusedProcesses = @($processesAfter | Where-Object { $_.Name -match $FocusRegex })
$focusedWindows = @($windowsAfter | Where-Object { Test-FocusedWindow $_ })
$focusedEvents = @($events.ToArray() | Where-Object { Test-FocusedWindow $_ })

Save-Csv $processesBefore (Join-Path $dest 'processes_before_ALL.csv')
Save-Csv $windowsBefore (Join-Path $dest 'windows_before_ALL.csv')
Save-Csv $processesAfter (Join-Path $dest 'processes_after_ALL.csv')
Save-Csv $windowsAfter (Join-Path $dest 'windows_after_ALL.csv')
Save-Csv $focusedProcesses (Join-Path $dest 'processes_FOCUS.csv')
Save-Csv $focusedWindows (Join-Path $dest 'windows_FOCUS.csv')
Save-Csv $zOrderTimeline.ToArray() (Join-Path $dest 'zorder_timeline_FOCUS.csv')
if ($Mode -eq 'Monitor') {
    Save-Csv $events.ToArray() (Join-Path $dest 'window_events_ALL.csv')
    Save-Csv $focusedEvents (Join-Path $dest 'window_events_FOCUS.csv')
}
$meta = [ordered]@{
    Product = 'FRB Window / Process Inspector v1.0'
    Mode = $Mode
    CapturedAt = (Get-Date).ToString('o')
    ComputerName = $env:COMPUTERNAME
    PSVersion = $hostVersion
    FocusRegex = $FocusRegex
    DurationSeconds = $(if ($Mode -eq 'Monitor') { $DurationSeconds } else { 0 })
    CommandLineIncluded = [bool]$IncludeCommandLine
    ProcessTotal = $processesAfter.Count
    WindowTotal = $windowsAfter.Count
    ZOrderSamples = $zOrderTimeline.Count
}
Save-Json ([ordered]@{ Meta=$meta; Processes=$focusedProcesses; Windows=$focusedWindows; Events=$focusedEvents; ZOrder=$zOrderTimeline.ToArray() }) (Join-Path $dest 'FOCUS.json')
Save-Json ([ordered]@{ Meta=$meta; Processes=$processesAfter; Windows=$windowsAfter; Events=@($events.ToArray()) }) (Join-Path $dest 'FULL_LOCAL.json')

$lines = New-Object 'System.Collections.Generic.List[string]'
$lines.Add('FRB Window / Process Inspector v1.0')
$lines.Add(('Mode: ' + $Mode + '  /  Captured: ' + $meta.CapturedAt))
$lines.Add(('Windows process count: ' + $processesAfter.Count + ' / focus: ' + $focusedProcesses.Count))
$lines.Add(('Windows handle count (top-level + target child): ' + $windowsAfter.Count + ' / focus: ' + $focusedWindows.Count))
$lines.Add(('Events: ' + $events.Count + ' / focus: ' + $focusedEvents.Count))
$lines.Add(('Focus filter: ' + $FocusRegex))
$lines.Add(('Z-order focused timeline rows: ' + $zOrderTimeline.Count))
$lines.Add('ZRank: 0 = top of all top-level windows, larger value = farther back.')
$lines.Add('')
$lines.Add('FOCUSED WINDOWS (HWND | PID | process | kind | visible | class | parent | owner | root | rect | title)')
foreach ($w in $focusedWindows) {
    $lines.Add(('{0} | {1} | {2} | {3} | {4} | {5} | p={6} | o={7} | root={8} | {9},{10} {11}x{12} | {13}' -f $w.HWND,$w.PID,$w.ProcessName,$w.Kind,$w.Visible,$w.ClassName,$w.ParentHWND,$w.OwnerHWND,$w.RootHWND,$w.Left,$w.Top,$w.Width,$w.Height,$w.Title))
}
$lines.Add('')
$lines.Add('PROCESS DETAILS: see processes_FOCUS.csv')
$lines.Add('WINDOW PARENT/OWNER/ROOT: see windows_FOCUS.csv')
$lines.Add('EVENTS: see window_events_FOCUS.csv (Monitor only)')
$lines.Add('Z-ORDER: see zorder_timeline_FOCUS.csv (Snapshot + Monitor).')
$lines.Add('TOPMOST: True = WS_EX_TOPMOST (0x8) in ExStyle. HWND_TOP cannot rise above TOPMOST windows.')
$lines.Add('NearestOverlappingAbove is the first visible window geometrically intersecting this one (not pixel occlusion).')
$lines.Add('NearestVisibleAbove may be unrelated to actual occlusion; compare HitRootHWND and cursor coordinates.')
$lines.Add('NOTE: A window that disappears from TopLevel may become a child of Launch. Compare final RootHWND/ParentHWND.')
$lines.Add('PRIVACY: Names, paths and titles may reveal local files. Inspect files before sharing.')
[System.IO.File]::WriteAllLines((Join-Path $dest 'SUMMARY.txt'), $lines.ToArray(), ([System.Text.UTF8Encoding]::new($true)))

$shareNote = @'
FRB Window Inspector - sharing guidance
This ZIP contains focus-matched process/window records plus nearby window IDs/process/class, topmost flags and extended styles for Z-order diagnosis. It is not the all-process inventory.
It can still contain process paths, document titles, local file names, and other programs' process/class information.
Please inspect before sharing. Nothing is uploaded by this tool.
For the full inventory, consult the unzipped local report directory instead.
'@
[System.IO.File]::WriteAllText((Join-Path $dest 'READ_BEFORE_SHARING.txt'), $shareNote, ([System.Text.UTF8Encoding]::new($true)))
$shareFiles = @('SUMMARY.txt','READ_BEFORE_SHARING.txt','processes_FOCUS.csv','windows_FOCUS.csv','zorder_timeline_FOCUS.csv','FOCUS.json')
if ($Mode -eq 'Monitor') { $shareFiles += 'window_events_FOCUS.csv' }
$sharePath = Join-Path $dest 'FRB_WindowReport_FOCUS_SHARE.zip'
$shareFilePaths = @($shareFiles | ForEach-Object { Join-Path $dest $_ })
Compress-Archive -LiteralPath $shareFilePaths -DestinationPath $sharePath -Force
Write-Host ''
Write-Host ('DONE: ' + $dest) -ForegroundColor Green
Write-Host ('Share (after review): ' + $sharePath) -ForegroundColor Green
Write-Host 'Full local CSV / JSON inventory is retained in the report folder only.'
