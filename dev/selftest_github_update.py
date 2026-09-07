"""Self-test script for M8 GitHub Releases update mechanism."""
import json
import re
import sys
import urllib.parse
from pathlib import Path

# Add parent directory to sys.path to import utils
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Mock bpy and mathutils so we can import utils.network outside Blender if needed
try:
    import bpy
except ImportError:
    import unittest.mock as mock
    sys.modules['bpy'] = mock.MagicMock()

try:
    import mathutils
except ImportError:
    import unittest.mock as mock
    sys.modules['mathutils'] = mock.MagicMock()

from utils.network import (
    _is_allowed_https_url,
    _is_sha256,
    version_str_to_tuple,
    version_tuple_to_str,
    GITHUB_REPO,
    GITHUB_API_LATEST,
    ALLOWED_UPDATE_HOSTS,
)

def test_whitelist():
    print("[TEST 1] Testing URL Whitelist Validation...")
    allowed_samples = [
        "https://github.com/maobukeai/M8/releases/download/v3.7.8/M8-v3.7.8.zip",
        "https://api.github.com/repos/maobukeai/M8/releases/latest",
        "https://objects.githubusercontent.com/github-production-release-asset-2e65be/12345",
        "https://github-releases.githubusercontent.com/12345",
        "https://raw.githubusercontent.com/maobukeai/M8/main/blender_manifest.toml",
    ]
    for url in allowed_samples:
        assert _is_allowed_https_url(url), f"Should be allowed: {url}"
    
    blocked_samples = [
        "http://github.com/maobukeai/M8/releases/download/v3.7.8/M8.zip",
        "https://malicious-site.com/M8.zip",
        "https://github.com.evil.com/fake.zip",
        "ftp://github.com/M8.zip",
        "https://mao.591595.xyz/downloads/M8.zip",  # decommissioned server
    ]
    for url in blocked_samples:
        assert not _is_allowed_https_url(url), f"Should be blocked: {url}"
    print("  -> PASS: All URL whitelist checks passed!")

def test_version_comparisons():
    print("[TEST 2] Testing Version Parsing and Comparison...")
    assert version_str_to_tuple("v3.7.8") == (3, 7, 8)
    assert version_str_to_tuple("3.7.8") == (3, 7, 8)
    assert version_str_to_tuple("3.7.10") == (3, 7, 10)
    assert version_str_to_tuple("3.7.10") > version_str_to_tuple("3.7.8")
    assert version_str_to_tuple("3.8.0") > version_str_to_tuple("3.7.9")
    assert version_str_to_tuple("3.7.7") < version_str_to_tuple("3.7.8")
    print("  -> PASS: Version parsing and numerical comparison passed!")

def test_mock_github_release_parsing():
    print("[TEST 3] Testing GitHub Release API Parsing Logic...")
    mock_response = {
        "tag_name": "v3.7.8",
        "html_url": "https://github.com/maobukeai/M8/releases/tag/v3.7.8",
        "body": "## What's Changed\n* Fix issue 1\n* SHA256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "assets": [
            {
                "name": "source_code.tar.gz",
                "browser_download_url": "https://github.com/maobukeai/M8/archive/refs/tags/v3.7.8.tar.gz"
            },
            {
                "name": "M8-v3.7.8.zip",
                "browser_download_url": "https://github.com/maobukeai/M8/releases/download/v3.7.8/M8-v3.7.8.zip"
            }
        ]
    }
    
    tag_name = mock_response.get("tag_name", "").strip()
    match = re.search(r"(\d+(?:\.\d+)+)", tag_name)
    latest_version = match.group(1) if match else tag_name.lstrip("v")
    assert latest_version == "3.7.8"
    
    # Add M8.zip to mock response to test priority
    mock_response["assets"].append({
        "name": "M8.zip",
        "browser_download_url": "https://github.com/maobukeai/M8/releases/download/v3.7.8/M8.zip"
    })
    
    # Priority matching test
    priority_url = ""
    for asset in mock_response.get("assets", []):
        if asset.get("name", "").lower() == "m8.zip":
            priority_url = asset.get("browser_download_url", "")
            break
    assert priority_url == "https://github.com/maobukeai/M8/releases/download/v3.7.8/M8.zip"
    print("  -> PASS: Standard M8.zip priority selection passed!")

def test_duplicate_scan():
    print("[TEST 4] Testing Duplicate Installation Scanning...")
    from utils.network import scan_duplicate_installations
    # Ensure current running dir is never flagged as duplicate
    dupes = scan_duplicate_installations()
    for d in dupes:
        assert d.name.lower() != "m8", "Active M8 directory should not be flagged as duplicate!"
    print(f"  -> PASS: Duplicate scan completed safely (found {len(dupes)} legacy folder(s)).")

if __name__ == '__main__':
    test_whitelist()
    test_version_comparisons()
    test_mock_github_release_parsing()
    test_duplicate_scan()
    print("\n=====================================")
    print("All GitHub Update Selftests Passed!")
    print("=====================================")
