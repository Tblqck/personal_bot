from list_fun import get_user_task_list

# Test user and timezone
user_id = "user_7416057134"
user_tz = "Africa/Lagos"

# Messages to query
messages = [
    "next two tasks",
    "what do I have lined up for the month",
    "set up a call for tomorrow by 10 am",
    "show all"
]

results = get_user_task_list(user_id, user_tz, messages)

for msg, info in results.items():
    print(f"Message: {msg}")
    print(f"Response time: {info['elapsed_seconds']:.2f} seconds")
    print("Tasks returned:", len(info["tasks"]))
    for t in info["tasks"]:
        print(" -", t["title"], "google_id:", t["google_id"])
    print("-"*50)
