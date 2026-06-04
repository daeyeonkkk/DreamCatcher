param(
    [string]$ImageTag = "dreamcatcher/runtime-prewarm:cuda12.8-frontier",
    [string]$BaseImage = "runpod/comfyui:1.4.1-cuda12.8",
    [string]$NodeMajor = "24",
    [switch]$PrewarmCustomNodes,
    [switch]$Push
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$dockerfile = Join-Path $scriptRoot "prewarm\Dockerfile.runtime"
$customNodeFlag = if ($PrewarmCustomNodes) { "1" } else { "0" }

$dockerArgs = @(
    "build",
    "-f", $dockerfile,
    "--build-arg", "BASE_IMAGE=$BaseImage",
    "--build-arg", "NODE_MAJOR=$NodeMajor",
    "--build-arg", "PREWARM_CUSTOM_NODES=$customNodeFlag",
    "-t", $ImageTag,
    $repoRoot
)

Write-Host "Building DreamCatcher prewarmed image: $ImageTag"
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "docker build failed with exit code $LASTEXITCODE"
}

if ($Push) {
    Write-Host "Pushing DreamCatcher prewarmed image: $ImageTag"
    & docker push $ImageTag
    if ($LASTEXITCODE -ne 0) {
        throw "docker push failed with exit code $LASTEXITCODE"
    }
}
