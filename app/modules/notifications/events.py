import uuid
from app.modules.notifications.models.notification_model import (
    NotificationType,
    NotificationPriority,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Notification templates: maps NotificationType → metadata
#   title: static title
#   message_template: Python format string with {kwargs}
#   roles: which staff roles receive this notification
#   priority: default priority
#   target: "assigned_staff" means only the assigned staff member
# ──────────────────────────────────────────────────────────────

TEMPLATES: dict[NotificationType, dict] = {
    # ── Booking events ──
    NotificationType.BOOKING_CREATED: {
        "title": "New Booking",
        "message_template": "Booking {ref_number} created by {guest_name} for {room_names}",
        "roles": ["admin", "manager", "front_desk"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Booking",
    },
    NotificationType.BOOKING_CONFIRMED: {
        "title": "Booking Confirmed",
        "message_template": "Booking {ref_number} confirmed — payment received from {guest_name}",
        "roles": ["admin", "manager", "front_desk"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Booking",
    },
    NotificationType.WALKIN_BOOKING_CREATED: {
        "title": "Walk-in Booking",
        "message_template": "Walk-in booking {ref_number} created for {guest_name} — room {room_names}",
        "roles": ["admin", "manager", "front_desk"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Booking",
    },
    NotificationType.BOOKING_CHECKED_IN: {
        "title": "Guest Checked In",
        "message_template": "{guest_name} checked in to room {room_names} (Booking {ref_number})",
        "roles": ["admin", "manager", "front_desk", "housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Booking",
    },
    NotificationType.BOOKING_CHECKED_OUT: {
        "title": "Guest Checked Out",
        "message_template": "{guest_name} checked out from room {room_names} (Booking {ref_number})",
        "roles": ["admin", "manager", "front_desk", "housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Booking",
    },
    NotificationType.BOOKING_CANCELLED: {
        "title": "Booking Cancelled",
        "message_template": "Booking {ref_number} cancelled — {guest_name} ({reason})",
        "roles": ["admin", "manager", "front_desk"],
        "priority": NotificationPriority.WARNING,
        "entity_type": "Booking",
    },
    NotificationType.BOOKING_MODIFIED: {
        "title": "Booking Modified",
        "message_template": "Booking {ref_number} modified by {guest_name}",
        "roles": ["admin", "manager", "front_desk"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Booking",
    },

    # ── Housekeeping events ──
    NotificationType.TASK_ASSIGNED: {
        "title": "Task Assigned",
        "message_template": "{task_type} assigned to room {room_name}",
        "roles": ["housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "HousekeepingTask",
        "target": "assigned_staff",
    },
    NotificationType.TASK_STARTED: {
        "title": "Task Started",
        "message_template": "{task_type} started for room {room_name} by {staff_name}",
        "roles": ["admin", "manager"],
        "priority": NotificationPriority.INFO,
        "entity_type": "HousekeepingTask",
    },
    NotificationType.TASK_COMPLETED: {
        "title": "Task Completed",
        "message_template": "{task_type} completed for room {room_name} by {staff_name}",
        "roles": ["admin", "manager"],
        "priority": NotificationPriority.INFO,
        "entity_type": "HousekeepingTask",
    },
    NotificationType.TASK_CANCELLED: {
        "title": "Task Cancelled",
        "message_template": "{task_type} cancelled for room {room_name}",
        "roles": ["admin", "manager"],
        "priority": NotificationPriority.WARNING,
        "entity_type": "HousekeepingTask",
    },
    NotificationType.CLEANING_SUBMITTED: {
        "title": "Cleaning Submitted",
        "message_template": "Cleaning results submitted for room {room_name} — awaiting inspection",
        "roles": ["admin", "manager"],
        "priority": NotificationPriority.INFO,
        "entity_type": "CleaningSubmission",
    },
    NotificationType.CLEANING_APPROVED: {
        "title": "Cleaning Approved",
        "message_template": "Cleaning for room {room_name} approved — room is now available",
        "roles": ["housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "CleaningSubmission",
        "target": "assigned_staff",
    },
    NotificationType.CLEANING_REJECTED: {
        "title": "Cleaning Rejected",
        "message_template": "Cleaning for room {room_name} rejected — please redo",
        "roles": ["housekeeping"],
        "priority": NotificationPriority.WARNING,
        "entity_type": "CleaningSubmission",
        "target": "assigned_staff",
    },

    # ── Room status events ──
    NotificationType.ROOM_DIRTY: {
        "title": "Room Needs Cleaning",
        "message_template": "Room {room_name} is now dirty after checkout",
        "roles": ["admin", "manager", "housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Room",
    },
    NotificationType.ROOM_MAINTENANCE: {
        "title": "Room Under Maintenance",
        "message_template": "Room {room_name} is now under maintenance",
        "roles": ["admin", "manager", "maintenance"],
        "priority": NotificationPriority.WARNING,
        "entity_type": "Room",
    },
    NotificationType.ROOM_AVAILABLE: {
        "title": "Room Available",
        "message_template": "Room {room_name} is now available",
        "roles": ["admin", "manager", "front_desk"],
        "priority": NotificationPriority.INFO,
        "entity_type": "Room",
    },

    # ── Maintenance events ──
    NotificationType.MAINTENANCE_REPORTED: {
        "title": "Maintenance Reported",
        "message_template": "Maintenance issue reported in room {room_name}: {category}",
        "roles": ["admin", "manager", "maintenance"],
        "priority": NotificationPriority.WARNING,
        "entity_type": "MaintenanceReport",
    },
    NotificationType.MAINTENANCE_RESOLVED: {
        "title": "Maintenance Resolved",
        "message_template": "Maintenance issue in room {room_name} has been resolved",
        "roles": ["admin", "manager"],
        "priority": NotificationPriority.INFO,
        "entity_type": "MaintenanceReport",
    },

    # ── Schedule events ──
    NotificationType.SWAP_REQUESTED: {
        "title": "Shift Swap Request",
        "message_template": "Shift swap request from {requester_name}",
        "roles": ["housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "ShiftSwapRequest",
        "target": "target_staff",
    },
    NotificationType.LEAVE_REQUESTED: {
        "title": "Leave Request",
        "message_template": "Leave request from {staff_name}: {leave_type} ({start_date} to {end_date})",
        "roles": ["admin", "manager"],
        "priority": NotificationPriority.INFO,
        "entity_type": "LeaveRequest",
    },
    NotificationType.LEAVE_STATUS_CHANGED: {
        "title": "Leave Request Updated",
        "message_template": "Your {leave_type} request has been {status}",
        "roles": ["housekeeping"],
        "priority": NotificationPriority.INFO,
        "entity_type": "LeaveRequest",
        "target": "requesting_staff",
    },
}


class NotificationEvents:
    """Helper to fire notifications from anywhere in the codebase."""

    @staticmethod
    async def fire(
        notification_type: NotificationType,
        notification_service: NotificationService,
        property_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        actor_guest_id: uuid.UUID | None = None,
        entity_id: uuid.UUID | None = None,
        recipient_user_ids: list[uuid.UUID] | None = None,
        **template_kwargs,
    ):
        """Fire a notification using the template registry.

        If recipient_user_ids is not provided, resolves recipients from the template's roles.
        If target is "assigned_staff", uses template_kwargs["assigned_staff_id"] to resolve.
        """
        template = TEMPLATES.get(notification_type)
        if not template:
            logger.warning(
                f"[NotificationEvents] No template for {notification_type.value}"
            )
            return

        title = template["title"]
        message = template["message_template"].format(**template_kwargs)

        # Resolve recipients for target-based templates
        recipient_user_ids = None
        roles = None
        target = template.get("target")

        if target in ("assigned_staff", "target_staff", "requesting_staff"):
            staff_key = {
                "assigned_staff": "assigned_staff_id",
                "target_staff": "target_staff_id",
                "requesting_staff": "requesting_staff_id",
            }[target]
            staff_id = template_kwargs.get(staff_key)
            if staff_id:
                uid = await notification_service.resolve_recipient_by_staff_id(staff_id)
                recipient_user_ids = [uid] if uid else []
            else:
                recipient_user_ids = []
        else:
            roles = template.get("roles", [])

        await notification_service.create_notification(
            notification_type=notification_type,
            property_id=property_id,
            organization_id=organization_id,
            title=title,
            message=message,
            recipient_user_ids=recipient_user_ids,
            roles=roles,
            actor_user_id=actor_user_id,
            actor_guest_id=actor_guest_id,
            entity_type=template.get("entity_type"),
            entity_id=entity_id,
            priority=template.get("priority", NotificationPriority.INFO),
            meta=template_kwargs,
        )
