import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.accounts.models import User
from apps.tasks.models import Task
from apps.notifications.models import Notification
from apps.ai.services.nlp.service import NLPCommandService

def run_test():
    print("=== Testing NLP Gemini Task Creation & Assignment Pipeline ===")
    user = User.objects.filter(email='liodinesh1905@gmail.com').first()
    if not user:
        user = User.objects.first()
    print(f"Executing as user: {user.username} (Email: {user.email}, ID: {user.id})")

    command_text = "create a new task Review Project Architecture by tomorrow at 5pm with high priority and assign to liodinesh1905@gmail.com"
    print(f"Command text: '{command_text}'")

    result = NLPCommandService.parse_and_execute(
        command_text=command_text,
        user=user
    )

    print("\n--- NLP Execution Result ---")
    print(f"Success: {result.get('success')}")
    print(f"Action: {result.get('action')}")
    print(f"Intent: {result.get('intent')}")
    print(f"Message: {result.get('message')}")
    print(f"Data: {result.get('data')}")

    # Check database
    created_task = Task.objects.filter(title__icontains="Review Project Architecture").order_by('-created_at').first()
    if created_task:
        print(f"\n[OK] Task found in DB: #{created_task.id} - '{created_task.title}'")
        print(f"     Priority: {created_task.priority}")
        print(f"     Deadline: {created_task.deadline}")
        print(f"     Assignee: {created_task.assigned_to.email if created_task.assigned_to else 'None'}")
    else:
        print("\n[FAIL] Task not found in DB!")

    # Check notification in DB
    notif = Notification.objects.filter(user=user).order_by('-created_at').first()
    if notif:
        print(f"\n[OK] Latest Notification in DB: #{notif.id} - '{notif.title}'")
        print(f"     Type: {notif.notification_type}")
        print(f"     Recipient Email: {notif.recipient_email}")
        print(f"     Message: {notif.message}")
    else:
        print("\n[INFO] No notification found for recipient.")

    # Now test task completion via NLP
    print("\n--- Testing Task Completion via NLP ---")
    complete_cmd = f"complete task #{created_task.id}"
    print(f"Command text: '{complete_cmd}'")
    complete_res = NLPCommandService.parse_and_execute(
        command_text=complete_cmd,
        user=user
    )
    print(f"Complete Success: {complete_res.get('success')}")
    print(f"Complete Message: {complete_res.get('message')}")

    # Check notification for completion
    notif_comp = Notification.objects.filter(user=user).order_by('-created_at').first()
    if notif_comp:
        print(f"\n[OK] Completion Notification in DB: #{notif_comp.id} - '{notif_comp.title}'")
        print(f"     Type: {notif_comp.notification_type}")
        print(f"     Recipient Email: {notif_comp.recipient_email}")
        print(f"     Message: {notif_comp.message}")

if __name__ == '__main__':
    run_test()
