# Paper.pdf Flow: Complete Architecture

## 📄 **Overview: PDF Never Goes Through MongoDB**

**Key Architecture Decision:**
- **MinIO (S3)** stores the actual PDF file (binary data)
- **MongoDB** stores only metadata (path, size, type)
- **Presigned URLs** enable direct upload/download without exposing credentials

```
PDF Binary Data:  Sakana → MinIO → Frontend (Direct)
PDF Metadata:     Sakana → Backend → MongoDB → Frontend (Via API)
```

## 🔄 **Complete Flow (Step-by-Step)**

### Step 1: Sakana Generates PDF

**Location:** `pod_worker.py` line 359-378

```python
# Sakana generates paper using LaTeX
from ai_scientist.perform_icbinb_writeup import perform_writeup

writeup_success = perform_writeup(
    base_folder=idea_dir,
    big_model="o1-preview-2024-09-12",
    page_limit=4,
    citations_text=citations_text
)

# PDF is now saved to disk:
# experiments/2025-10-22_12-34-56_my_idea_run_123/paper.pdf
pdf_files = [f for f in os.listdir(idea_dir) if f.endswith(".pdf")]
if pdf_files:
    pdf_path = os.path.join(idea_dir, pdf_files[0])
    # e.g., "experiments/.../paper.pdf"
```

### Step 2: Request Presigned PUT URL

**Location:** `pod_worker.py` line 218-229

```python
def upload_artifact(run_id: str, file_path: str, kind: str) -> bool:
    filename = os.path.basename(file_path)  # "paper.pdf"
    content_type = "application/pdf"
    
    # Request presigned URL from backend
    resp = requests.post(
        f"{CONTROL_PLANE_URL}/api/runs/{run_id}/artifacts/presign",
        json={
            "action": "put",
            "filename": filename,
            "content_type": content_type
        },
        timeout=30
    )
    
    presigned_url = resp.json()["url"]
    # e.g., "https://minio.example.com/ai-scientist/runs/123/paper.pdf?
    #        AWSAccessKeyId=...&Signature=...&Expires=..."
```

### Step 3: Backend Generates Presigned PUT URL

**Location:** `orchestrator/apps/web/app/api/runs/[id]/artifacts/presign/route.ts` line 27-29

```typescript
if (parsed.data.action === "put") {
  const result = await presignArtifactUpload(id, parsed.data.filename)
  return NextResponse.json(result)  // { url: "...", key: "..." }
}
```

**Location:** `orchestrator/apps/web/lib/services/artifacts.service.ts` line 5-16

```typescript
export async function presignArtifactUpload(runId: string, filename: string) {
  const key = `${runId}/${Date.now()}-${sanitizeFilename(filename)}`
  // e.g., "01JDNW3A.../1729629465000-paper.pdf"
  
  // Generate presigned PUT URL (MinIO)
  const url = await presignPutObject(key)
  // This URL allows uploading to MinIO for 15 minutes
  
  // Create artifact metadata in MongoDB (not the file!)
  await createArtifact({
    _id: randomUUID(),
    runId,
    key,                          // Path in MinIO
    uri: buildPublicUrl(key),     // Public URL (if configured)
    createdAt: new Date()
  })
  
  return { url, key }
}
```

**Location:** `orchestrator/apps/web/lib/storage/minio.ts`

```typescript
async function presignPutObject(key: string): Promise<string> {
  const minioClient = getMinioClient()
  
  // Generate presigned URL valid for 15 minutes
  const url = await minioClient.presignedPutObject(
    BUCKET_NAME,        // "ai-scientist"
    key,                // "runs/123/paper.pdf"
    15 * 60             // 900 seconds
  )
  
  return url
}
```

### Step 4: Worker Uploads PDF to MinIO

**Location:** `pod_worker.py` line 231-235

```python
# Read PDF file from disk
with open(file_path, "rb") as f:
    file_bytes = f.read()  # Binary PDF data

# Upload directly to MinIO using presigned URL
resp = requests.put(
    presigned_url,      # From step 2
    data=file_bytes,    # Raw PDF binary
    timeout=300         # 5 minutes
)
resp.raise_for_status()

# PDF is now in MinIO at: runs/01JDNW.../paper.pdf
```

**What happens in MinIO:**
```
MinIO Storage:
├── ai-scientist (bucket)
│   ├── runs/
│   │   ├── 01JDNW3A21Q0X9MBYF4F1A9B3D/
│   │   │   ├── 1729629465000-paper.pdf  ← PDF file stored here!
│   │   │   ├── 1729629470000-figure1.png
│   │   │   └── 1729629472000-figure2.png
```

### Step 5: Worker Emits Event to Backend

**Location:** `pod_worker.py` line 237-246

```python
sha256 = hashlib.sha256(file_bytes).hexdigest()

# Emit event (metadata only, not the PDF!)
emit_event("ai.artifact.registered", {
    "run_id": run_id,
    "key": f"runs/{run_id}/{filename}",  # MinIO path
    "bytes": len(file_bytes),            # File size
    "sha256": sha256,                    # Checksum
    "content_type": "application/pdf",
    "kind": "paper"                      # Artifact type
})
```

### Step 6: Backend Creates Artifact Record in MongoDB

**Location:** `orchestrator/apps/web/lib/services/events.service.ts` line 224-236

```typescript
async function handleArtifactRegistered(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  
  // Create artifact metadata in MongoDB
  await createArtifact({
    _id: `${runId}-${data.kind}-${Date.now()}`,
    runId: runId,
    key: data.key,               // MinIO path: "runs/123/paper.pdf"
    kind: data.kind,             // "paper"
    contentType: data.content_type,
    size: data.bytes,            // File size in bytes
    createdAt: new Date(event.time)
  })
}
```

**MongoDB document created:**
```javascript
// artifacts collection
{
  "_id": "01JDNW...-paper-1729629465000",
  "runId": "01JDNW3A21Q0X9MBYF4F1A9B3D",
  "key": "runs/01JDNW.../1729629465000-paper.pdf",  // ← MinIO path
  "kind": "paper",
  "contentType": "application/pdf",
  "size": 524288,  // bytes
  "createdAt": ISODate("2025-10-22T19:17:45Z")
}
```

### Step 7: Frontend Queries MongoDB for Artifacts

**Location:** `orchestrator/apps/web/lib/data/runs.ts` line 28-38

```typescript
export async function getRunDetail(runId: string) {
  const run = await findRunById(runId)
  if (!run) return null
  
  const [stages, validations, artifacts, hypothesis] = await Promise.all([
    listStagesForRun(runId),
    listValidationsForRun(runId),
    listArtifactsForRun(runId),  // ← Gets artifact metadata from MongoDB
    findHypothesisById(run.hypothesisId)
  ])
  
  return { run, stages, validations, artifacts, hypothesis }
}
```

**API Response:**
```json
{
  "run": { ... },
  "artifacts": [
    {
      "_id": "01JDNW...-paper-1729629465000",
      "runId": "01JDNW3A21Q0X9MBYF4F1A9B3D",
      "key": "runs/01JDNW.../1729629465000-paper.pdf",
      "kind": "paper",
      "contentType": "application/pdf",
      "size": 524288
    }
  ]
}
```

### Step 8: User Clicks Download Button

**Frontend component:**
```typescript
// In RunDetail page
<button onClick={async () => {
  // Request presigned GET URL
  const response = await fetch(
    `/api/runs/${runId}/artifacts/presign`,
    {
      method: 'POST',
      body: JSON.stringify({
        action: 'get',
        key: artifact.key  // "runs/01JDNW.../paper.pdf"
      })
    }
  )
  
  const { url } = await response.json()
  
  // Open in new tab or download
  window.open(url, '_blank')
}}>
  Download Paper
</button>
```

### Step 9: Backend Generates Presigned GET URL

**Location:** `orchestrator/apps/web/app/api/runs/[id]/artifacts/presign/route.ts` line 31-32

```typescript
const result = await presignArtifactDownload(parsed.data.key)
return NextResponse.json(result)  // { url: "..." }
```

**Location:** `orchestrator/apps/web/lib/services/artifacts.service.ts` line 18-21

```typescript
export async function presignArtifactDownload(key: string) {
  const url = await presignGetObject(key)
  // Returns MinIO presigned GET URL valid for 15 minutes
  return { url }
}
```

**Location:** `orchestrator/apps/web/lib/storage/minio.ts`

```typescript
async function presignGetObject(key: string): Promise<string> {
  const minioClient = getMinioClient()
  
  // Generate presigned GET URL
  const url = await minioClient.presignedGetObject(
    BUCKET_NAME,        // "ai-scientist"
    key,                // "runs/123/paper.pdf"
    15 * 60             // Valid for 15 minutes
  )
  
  return url
}
```

### Step 10: Frontend Downloads from MinIO

**Browser makes direct request:**
```
GET https://minio.example.com/ai-scientist/runs/01JDNW.../paper.pdf?
    AWSAccessKeyId=minioadmin&
    Signature=abc123...&
    Expires=1729630365

Response: 
  Content-Type: application/pdf
  Content-Length: 524288
  [PDF binary data]
```

User sees PDF in browser! 🎉

---

## 📊 **Data Flow Comparison**

### What Goes Through MongoDB (Metadata Only)

```javascript
// Small, fast, indexed
{
  "runId": "01JDNW...",
  "key": "runs/01JDNW.../paper.pdf",  // ← Path to file in MinIO
  "kind": "paper",
  "size": 524288,
  "contentType": "application/pdf"
}
```

**Size:** ~200 bytes per artifact

### What Goes Through MinIO (Binary Data)

```
Raw PDF file: 524,288 bytes (512 KB)
```

**Size:** The actual file size (can be MBs)

---

## 🔐 **Security: Presigned URLs**

### Why Presigned URLs?

1. **No credentials exposed** - Worker/Frontend never see MinIO keys
2. **Time-limited** - URLs expire after 15 minutes
3. **Action-specific** - PUT URL ≠ GET URL
4. **Direct transfer** - No proxy through backend (faster)

### Presigned PUT URL (Upload)

```
https://minio.example.com/ai-scientist/runs/123/paper.pdf?
  AWSAccessKeyId=minioadmin&
  Signature=xyz789&
  Expires=1729629765&
  X-Amz-Algorithm=AWS4-HMAC-SHA256
```

**Allows:** Upload (PUT) to specific path for 15 minutes  
**Prevents:** Download, delete, list

### Presigned GET URL (Download)

```
https://minio.example.com/ai-scientist/runs/123/paper.pdf?
  AWSAccessKeyId=minioadmin&
  Signature=abc123&
  Expires=1729630365
```

**Allows:** Download (GET) from specific path for 15 minutes  
**Prevents:** Upload, delete, modify

---

## 🎯 **Why This Architecture?**

### ✅ Advantages

1. **Scalable** - MinIO handles large files efficiently
2. **Fast** - Direct upload/download, no backend proxy
3. **Secure** - Time-limited, scoped URLs
4. **Clean** - MongoDB stays fast (no binary data)
5. **Standard** - S3-compatible (portable)

### ❌ What We DON'T Do (Anti-Patterns)

**❌ Store PDF in MongoDB:**
```javascript
// BAD: Would make MongoDB slow and bloated
{
  "runId": "...",
  "pdfData": "JVBERi0xLjQKJeLjz9M..." // ← Don't do this!
}
```

**❌ Proxy through Backend:**
```python
# BAD: Backend becomes bottleneck
@app.post("/upload-artifact")
def upload(file: UploadFile):
    # Backend reads entire file, then uploads to MinIO
    data = file.read()  # ← Slow! Large memory usage!
    minio_client.put_object(bucket, key, data)
```

**❌ Expose MinIO Credentials:**
```javascript
// BAD: Security risk
{
  "minioUrl": "...",
  "accessKey": "minioadmin",  // ← Never expose!
  "secretKey": "..."
}
```

---

## 🧪 **Testing the Flow**

### Test 1: Manual Upload/Download

```bash
# 1. Create test PDF
echo "%PDF-1.4\nTest PDF" > test.pdf

# 2. Get presigned PUT URL
curl -X POST https://your-app.railway.app/api/runs/test-run-123/artifacts/presign \
  -H "Content-Type: application/json" \
  -d '{"action": "put", "filename": "test.pdf"}'

# Response: {"url": "https://minio.../...", "key": "..."}

# 3. Upload using presigned URL
curl -X PUT "<presigned_url_from_step_2>" \
  --data-binary @test.pdf \
  -H "Content-Type: application/pdf"

# 4. Get presigned GET URL
curl -X POST https://your-app.railway.app/api/runs/test-run-123/artifacts/presign \
  -H "Content-Type: application/json" \
  -d '{"action": "get", "key": "<key_from_step_2>"}'

# 5. Download
curl "<presigned_url_from_step_4>" -o downloaded.pdf
```

### Test 2: Verify in MongoDB

```javascript
// Connect to MongoDB
db.artifacts.find({ runId: "test-run-123" })

// Should see:
{
  "_id": "...",
  "runId": "test-run-123",
  "key": "test-run-123/1729629465000-test.pdf",
  "kind": "paper",
  "contentType": "application/pdf",
  "size": ...,
  "createdAt": ISODate("...")
}
```

---

## 📝 **Summary**

**Paper.pdf Flow:**
1. ✅ Sakana generates PDF locally
2. ✅ Worker requests presigned PUT URL from backend
3. ✅ Backend generates URL (MinIO) + creates metadata (MongoDB)
4. ✅ Worker uploads PDF directly to MinIO
5. ✅ Worker emits `ai.artifact.registered` event
6. ✅ Backend updates artifact metadata in MongoDB
7. ✅ Frontend reads metadata from MongoDB
8. ✅ User requests download
9. ✅ Backend generates presigned GET URL
10. ✅ Frontend downloads directly from MinIO

**Key Points:**
- 📄 PDF **never** goes through MongoDB (only metadata)
- 🚀 PDF uploaded/downloaded **directly** to/from MinIO
- 🔐 **Presigned URLs** provide secure, time-limited access
- ⚡ **Fast** - No backend bottleneck
- 📊 **Scalable** - MinIO handles GBs of artifacts

**The backend is just a "URL factory" - it generates signed URLs but never touches the file data itself!** 🏭

