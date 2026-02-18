# test_task_filter.py

from datetime import datetime
import pytz
from list_fun import get_user_task_list, load_all_tasks  # replace your_module_name with the filename if needed

USER_ID = "user_1249752083"
USER_TZ = "Europe/Athens"

# -----------------------
# Optional: Seed some test tasks if CSV is empty
# -----------------------
if not load_all_tasks():
    import csv
    TASKS_CSV = "tasks.csv"
    tasks = [
        {"user_id": USER_ID, "title": "Call Mom", "details": "Weekly call", "due": "2026-02-12T10:00:00+01:00", "google_id": "Yl9lV3lBWnExYUZ2Qm5WZA", "ai_comment": ""},
        {"user_id": USER_ID, "title": "Team Meeting", "details": "Project update", "due": "2026-02-11T15:00:00+01:00", "google_id": "Xy2AbC3D4EfG", "ai_comment": ""},
        {"user_id": USER_ID, "title": "Buy Groceries", "details": "Eggs, Milk, Bread", "due": "2026-02-11T18:00:00+01:00", "google_id": "AbC123XyZ", "ai_comment": ""}
    ]
    with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=tasks[0].keys())
        writer.writeheader()
        writer.writerows(tasks)

# -----------------------
# Test messages
# -----------------------
test_messages = [
    
    "what task do i have pending",
    "what are my pending task",
    "do i have any pending task",
    "what task am i yet to do",
    
    "what task do i have today"
]

# -----------------------
# Run test
# -----------------------
results = get_user_task_list(USER_ID, USER_TZ, test_messages)

# -----------------------
# Print results
# -----------------------
for msg, data in results.items():
    print(f"\nMessage: {msg}")
    print(f"Elapsed seconds: {data['elapsed_seconds']:.2f}")
    print("Tasks:")
    for t in data["tasks"]:
        print(f" - {t['title']} (google_id: {t['google_id']})")
