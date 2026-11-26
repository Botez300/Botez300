# Google Drive ingestion and authentication

## Method A: Drive for desktop (recommended)
- **Setup:** no credentials. Point `local_dir` at the real synced `03_Verified_Signals` folder on your machine.
- **Partial-sync protection:**
  - files younger than 5 s and temp names are skipped;
  - truncated JSON younger than 120 s is deferred and retried;
  - hashes and the SQLite ledger prevent reprocessing.

## Method B: Drive API (read-only scope `drive.readonly`)
- **Credential, either:**
  - a service account (share the folder as Viewer), or
  - an OAuth desktop token (`python -m legion.drive_auth --client-secret <file> --token <file>`).
- **Storage:** keep both files outside the repo and outside Drive.
- **Downloads:** verified against Drive `md5Checksum` and size, then SHA-256. Folder listing paginates.
- **Status:** tested only against a fake Drive service. **Real Google authentication has not been tested.**

## What was tested this phase
The genuine report was retrieved through the Claude Drive connector:
- SHA-256 matched the expected `443e77ac...3373c`;
- size is 10,888 bytes, matching Drive metadata.

The connector is the session's authorized access, not the app's own credential.

## Safety
Drive content never changes mode, permissions, limits or code. Report text is treated as data and scanned for injection patterns. Execution flags inside reports are schema-forced to `research_only=true` / `execution_authorized=false`.
