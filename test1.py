from upload_pending_tasks import upload_pending_tasks

# Run uploader silently
updated = upload_pending_tasks()

if updated:
    print("✅ Tasks synced with Google Tasks.")
else:
    print("No updates needed.")
