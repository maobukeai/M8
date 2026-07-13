# M8 Update API Contract

The client sends the installed version as the `version` query parameter and the
plugin token only in the `X-Developer-Token` HTTP header. The token must not be
required in the URL or JSON request body.

When an update is available, the response must include a HTTPS download URL on
`mao.591595.xyz` and a SHA-256 digest for the exact ZIP payload.

```json
{
  "updateAvailable": true,
  "latestVersion": "3.7.0",
  "downloadUrl": "https://mao.591595.xyz/downloads/M8-3.7.0.zip",
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "changelog": "..."
}
```

`downloadSha256` is accepted as an alias for `sha256` during migration. The
server should rate-limit requests and treat the bundled token as a public client
identifier, not a secret credential.
