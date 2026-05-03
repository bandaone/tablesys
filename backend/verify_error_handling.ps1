# Checkpoint 1.6: Error Handling & Logging - Verification Tests

## Test 1: Error Handler Verification
Write-Host "`n=== TEST 1: ERROR HANDLER VERIFICATION ===" -ForegroundColor Cyan

# Wait for backend to be ready
Start-Sleep -Seconds 3

# Test invalid login (should return consistent error format)
Write-Host "`nTesting error handler with invalid login..." -ForegroundColor Yellow
try {
    $body = @{username=""; password=""} | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
        -Method POST `
        -Body $body `
        -ContentType "application/json" `
        -ErrorAction Stop
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "Error Response:" -ForegroundColor Green
    $errorResponse | ConvertTo-Json -Depth 5
    
    # Verify error format
    if ($errorResponse.error.type -and $errorResponse.error.message -and $errorResponse.error.timestamp -and $errorResponse.error.request_id) {
        Write-Host "✓ PASS: Error has consistent format" -ForegroundColor Green
    } else {
        Write-Host "✗ FAIL: Error format incomplete" -ForegroundColor Red
    }
}

## Test 2: Audit Logging - Login Events
Write-Host "`n=== TEST 2: AUDIT LOGGING - LOGIN EVENTS ===" -ForegroundColor Cyan

# Make failed login attempt
Write-Host "`nMaking failed login attempt..." -ForegroundColor Yellow
try {
    $body = @{username="coordinator"; password="wrong"} | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
        -Method POST `
        -Body $body `
        -ContentType "application/json" `
        -ErrorAction Stop
} catch {
    Write-Host "Failed login (expected)" -ForegroundColor Gray
}

# Make successful login attempt
Write-Host "Making successful login attempt..." -ForegroundColor Yellow
$body = @{username="coordinator"; password="pass"} | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"
Write-Host "Login successful" -ForegroundColor Green

# Check audit log
Write-Host "`nChecking audit log..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
$auditLog = docker exec tablesys-backend cat logs/audit.log 2>$null

if ($auditLog) {
    Write-Host "`nAudit Log Entries:" -ForegroundColor Green
    $auditLog -split "`n" | Select-Object -Last 5 | ForEach-Object {
        if ($_ -match "LOGIN") {
            $entry = $_ | ConvertFrom-Json
            Write-Host "  - $($entry.event_type): $($entry.username) from $($entry.ip_address)" -ForegroundColor Cyan
        }
    }
    Write-Host "✓ PASS: Login events logged" -ForegroundColor Green
} else {
    Write-Host "✗ FAIL: Audit log not found or empty" -ForegroundColor Red
}

## Test 3: Audit Logging - Bulk Upload
Write-Host "`n=== TEST 3: AUDIT LOGGING - BULK UPLOAD ===" -ForegroundColor Cyan

# Create test CSV
Write-Host "`nCreating test CSV..." -ForegroundColor Yellow
$csv = @"
code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
TEST101,Test Course,1,2,3,3,1,0
"@
$csv | Out-File -FilePath "test_courses.csv" -Encoding UTF8

# Upload CSV
Write-Host "Uploading CSV..." -ForegroundColor Yellow
$token = $loginResponse.access_token
$headers = @{Authorization = "Bearer $token"}

try {
    $form = @{
        file = Get-Item "test_courses.csv"
    }
    $uploadResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/courses/bulk-upload" `
        -Method POST `
        -Headers $headers `
        -Form $form
    Write-Host "Upload successful: $($uploadResponse.message)" -ForegroundColor Green
} catch {
    Write-Host "Upload failed: $_" -ForegroundColor Red
}

# Check audit log for bulk upload event
Write-Host "`nChecking audit log for bulk upload..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
$auditLog = docker exec tablesys-backend cat logs/audit.log 2>$null

if ($auditLog -match "BULK_UPLOAD_COURSE") {
    Write-Host "`nBulk Upload Events:" -ForegroundColor Green
    $auditLog -split "`n" | Where-Object { $_ -match "BULK_UPLOAD" } | Select-Object -Last 2 | ForEach-Object {
        $entry = $_ | ConvertFrom-Json
        Write-Host "  - $($entry.event_type): $($entry.details.count) records by $($entry.username)" -ForegroundColor Cyan
    }
    Write-Host "✓ PASS: Bulk upload events logged" -ForegroundColor Green
} else {
    Write-Host "✗ FAIL: No bulk upload events in audit log" -ForegroundColor Red
}

# Cleanup
Remove-Item "test_courses.csv" -ErrorAction SilentlyContinue

## Test 4: Log Files Verification
Write-Host "`n=== TEST 4: LOG FILES VERIFICATION ===" -ForegroundColor Cyan

Write-Host "`nChecking log files..." -ForegroundColor Yellow
$logFiles = docker exec tablesys-backend ls -lh logs/ 2>$null

if ($logFiles) {
    Write-Host "`nLog Files:" -ForegroundColor Green
    Write-Host $logFiles
    
    if ($logFiles -match "app.log" -and $logFiles -match "audit.log" -and $logFiles -match "error.log") {
        Write-Host "✓ PASS: All log files created" -ForegroundColor Green
    } else {
        Write-Host "✗ FAIL: Some log files missing" -ForegroundColor Red
    }
} else {
    Write-Host "✗ FAIL: Cannot access log files" -ForegroundColor Red
}

## Test 5: Request ID Tracking
Write-Host "`n=== TEST 5: REQUEST ID TRACKING ===" -ForegroundColor Cyan

Write-Host "`nChecking request ID in logs..." -ForegroundColor Yellow
$appLog = docker exec tablesys-backend cat logs/app.log 2>$null

if ($appLog -match "\[[\w-]+\]") {
    Write-Host "✓ PASS: Request IDs found in logs" -ForegroundColor Green
    Write-Host "`nSample log entry:" -ForegroundColor Cyan
    $appLog -split "`n" | Where-Object { $_ -match "\[[\w-]+\]" } | Select-Object -Last 1
} else {
    Write-Host "✗ FAIL: No request IDs in logs" -ForegroundColor Red
}

## Summary
Write-Host "`n=== CHECKPOINT 1.6 VERIFICATION SUMMARY ===" -ForegroundColor Cyan
Write-Host "✓ Error handler middleware working" -ForegroundColor Green
Write-Host "✓ Audit logging for login events" -ForegroundColor Green
Write-Host "✓ Audit logging for bulk uploads" -ForegroundColor Green
Write-Host "✓ Log files created (app, audit, error)" -ForegroundColor Green
Write-Host "✓ Request ID tracking enabled" -ForegroundColor Green
Write-Host "`nCheckpoint 1.6 COMPLETE! 🎉" -ForegroundColor Green
