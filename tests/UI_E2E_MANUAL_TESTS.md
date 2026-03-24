# DvsDB UI End-to-End Manual Tests

## Setup

1. Start backend:
   - `uvicorn api.main:app --reload`
2. Start frontend:
   - `cd ui`
   - `npm run dev`
3. Open the local UI URL shown by Vite.

## 10) UI Query Flow

1. In Query Editor, enter:
   - `SELECT * FROM users;`
2. Click **Run Query**
3. Expected:
   - Results table renders headers `id`, `username`, `email`
   - Empty table or rows appear without UI crash

## 11) Data Upload Form

1. In **Data Upload**, enter:
   - id: `501`
   - username: `form_user`
   - email: `form_user@email.com`
2. Click **Insert Row**
3. Expected:
   - Status shows success
   - Running `SELECT * FROM users;` includes id `501`

## 12) CSV Upload

1. Create CSV with:
   - `id,username,email`
   - `601,csv_a,csv_a@email.com`
   - `602,csv_b,csv_b@email.com`
2. Upload via CSV input in **Data Upload**
3. Expected:
   - Status reports inserted row count
   - `SELECT * FROM users;` includes ids `601`, `602`

## 13) Checkpoint Button

1. Insert a few rows (query or form)
2. Click **Checkpoint WAL**
3. Expected:
   - Status shows `WAL checkpoint completed`
   - App remains responsive
   - New inserts continue to work after checkpoint

## Optional File-Level Verification

When running against a temporary/test DB directory:
- Confirm `dvsdb.wal` becomes empty after checkpoint.
- Restart backend and verify inserted data still exists.
