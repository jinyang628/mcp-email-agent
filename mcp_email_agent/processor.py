import re

from .gmail import create_draft, delete_message, get_label_ids_by_name, modify_message_labels


def process_email(service, email_details, rules_config):
    if not email_details:
        return False

    email_id: str = email_details.get("id")
    sender_full: str = email_details.get("from", "")
    sender_email: str = _extract_email_address(sender_full)
    subject: str = email_details.get("subject", "").lower()
    recipient_full: str = email_details.get("to", "")
    processed_action_taken = False

    _delete_spam(
        sender_email=sender_email,
        subject=subject,
        email_id=email_id,
        rules_config=rules_config,
        service=service,
        email_details=email_details,
    )

    # 3. Auto-Drafting (apply first matching draft rule)
    for draft_rule in rules_config.get("auto_drafts", []):
        condition = draft_rule.get("condition", {})
        match = False
        conditions_met = 0
        total_conditions = 0

        # Check 'to_contains' or 'to_exact' against the 'To' header
        actual_recipients_lower = [_extract_email_address(r) for r in recipient_full.split(",")]

        if condition.get("to_contains"):
            total_conditions += 1
            if any(
                tc.lower() in actual_recipients_lower for tc in condition.get("to_contains", [])
            ):
                conditions_met += 1
        if condition.get("to_exact"):
            total_conditions += 1
            if any(te.lower() in actual_recipients_lower for te in condition.get("to_exact", [])):
                conditions_met += 1
        if condition.get("subject_contains"):
            total_conditions += 1
            if any(sc.lower() in subject for sc in condition.get("subject_contains", [])):
                conditions_met += 1
        if condition.get("from_contains"):
            total_conditions += 1
            if any(fc.lower() in sender_email for fc in condition.get("from_contains", [])):
                conditions_met += 1

        match_all = condition.get("match_all_conditions", True)  # Default to AND for drafts
        if total_conditions > 0:
            if match_all and conditions_met == total_conditions:
                match = True
            elif not match_all and conditions_met > 0:
                match = True

        if match and draft_rule.get("action") == "draft_reply":
            sender_name_match = re.match(r"^(.*?)\s*<", sender_full)
            sender_name = (
                sender_name_match.group(1).strip().title()
                if sender_name_match
                else sender_email.split("@")[0].title()
            )
            original_subject_text = email_details.get("subject", "")

            reply_body = draft_rule["response_template"].format(
                sender_name=sender_name,
                original_subject=original_subject_text,
                sender_email=sender_email,
                original_body=email_details.get(
                    "body_plain", ""
                ),  # Add original body if needed in template
            )
            reply_subject = f"Re: {original_subject_text}"

            # Determine recipient: 'Reply-To' header if present, otherwise 'From'
            reply_to_header = email_details.get("reply-to")
            actual_reply_to_email = (
                _extract_email_address(reply_to_header) if reply_to_header else sender_email
            )

            print(
                f"  ACTION: Drafting reply for '{draft_rule.get('name', 'Untitled Draft')}' -> To: '{actual_reply_to_email}', Subject: '{reply_subject}'"
            )
            create_draft(
                service,
                to=actual_reply_to_email,
                subject=reply_subject,
                message_text=reply_body,
                thread_id=email_details.get("threadId"),
                in_reply_to=email_details.get(
                    "message-id"
                ),  # Use original Message-ID for In-Reply-To
                references=email_details.get("references"),  # Preserve references
            )
            # Mark original as read after drafting
            unread_label_id = get_label_ids_by_name(service, ["UNREAD"])
            if unread_label_id:
                modify_message_labels(service, email_id, [], unread_label_id)

            processed_action_taken = True
            break  # Only one auto-draft per email typically

    if not processed_action_taken and rules_config.get("default_action_if_no_match") == "mark_read":
        print(
            f"  ACTION: No rules matched. Marking as read. -> Subject: '{email_details.get('subject')}'"
        )
        unread_label_id = get_label_ids_by_name(service, ["UNREAD"])
        if unread_label_id:
            modify_message_labels(service, email_id, [], unread_label_id)
        processed_action_taken = True

    return processed_action_taken


def _extract_email_address(email_header_value: str) -> str:
    """Extracts the first email address from a typical 'From' or 'To' header."""
    if not email_header_value:
        return ""
    match = re.search(r"[\w\.-]+@[\w\.-]+", email_header_value)
    return match.group(0).lower() if match else email_header_value.lower()


def _delete_spam(
    sender_email: str,
    subject: str,
    email_id: str,
    rules_config: dict,
    service: any,
    email_details: dict,
):
    for rule_name, rule_data in rules_config.get(
        "spam_deletion", {}
    ).items():  # Changed from items() to values() if rule_name not used
        if rule_data.get("action") == "delete":
            delete_email = False
            if any(f.lower() == sender_email for f in rule_data.get("from_exact", [])):
                delete_email = True
            if not delete_email and any(
                f.lower() in sender_email for f in rule_data.get("from_contains", [])
            ):
                delete_email = True
            if not delete_email and any(
                s.lower() in subject for s in rule_data.get("subject_contains_any", [])
            ):
                delete_email = True

            if delete_email:
                print(
                    f"  ACTION: Deleting (spam rule '{rule_name}') -> Subject: '{email_details.get('subject')}', From: '{sender_email}'"
                )
                delete_message(service, email_id)
                return True  # Email processed, stop further rules
