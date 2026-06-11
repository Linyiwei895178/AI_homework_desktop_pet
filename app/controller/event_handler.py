"""EventHandler: responds to user events (click/drag) and triggers pet actions.

Also handles instant cloud event sync on action triggers (feed/play/pet).
"""
from models.state.behavior_rules import decide_action
from utils.logger import get_logger

logger = get_logger("EventHandler")


class EventHandler:
    """Handle pet mouse events; delegate to PetController; optionally sync to cloud."""

    def __init__(self, pet, pet_controller, cloud_manager=None):
        """
        :param pet: DesktopPet object
        :param pet_controller: PetController object
        :param cloud_manager: optional SharedPetRoomManager for instant event sync
        """
        self.pet = pet
        self.pet_controller = pet_controller
        self.cloud_manager = cloud_manager
        self._event_queue = []

    def set_cloud_manager(self, mgr) -> None:
        self.cloud_manager = mgr

    def _try_sync_event(self, action: str) -> None:
        """Immediately push an interaction event to the cloud if connected."""
        if self.cloud_manager is None:
            return
        if not hasattr(self.cloud_manager, "is_in_room") or not self.cloud_manager.is_in_room():
            return
        # Only sync meaningful actions (skip neutral/idle)
        if not action or action in ("", "idle"):
            return
        try:
            pet_state = self.pet_controller.pet_state
            delta = {
                "feed":   {"hunger": -20, "energy": 20},
                "play":   {"energy": -10, "intimacy": 3},
                "click":  {"intimacy": 2},
                "pet":    {"intimacy": 2},
                "happy":  {"mood": 5},
                "sad":    {"mood": -5},
                "hungry": {"hunger": -10},
                "angry":  {"mood": -5},
            }.get(action, {})
            self.cloud_manager.append_interaction(
                action_type=action,
                actor_name="我",
                delta=delta,
            )
            if hasattr(pet_state, "_last_event"):
                pet_state._last_event = action
        except Exception as exc:
            logger.warning(f"[EventHandler] 即时事件同步失败(已降级): {exc}")

    def handle_drag(self, _event):
        logger.info(f"拖拽事件 - 新位置: ({self.pet.position[0]}, {self.pet.position[1]})")

    def handle_click(self, _event):
        logger.info("点击事件触发")

        pet_state = self.pet_controller.pet_state
        action = decide_action(pet_state)
        logger.info(f"行为决策结果: {action}")

        self.pet_controller.trigger_action(self.pet, action)
        pet_state.update_state(action)
        logger.info(f"状态更新: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

        # ── Instant cloud event sync ──
        self._try_sync_event(action)

    def handle_action(self, action: str) -> None:
        """Programmatic action trigger (e.g. from UI buttons, timer events)."""
        pet_state = self.pet_controller.pet_state
        self.pet_controller.trigger_action(self.pet, action)
        pet_state.update_state(action)
        logger.info(f"[EventHandler] 动作触发: {action} | mood={pet_state.mood}, energy={pet_state.energy}")
        self._try_sync_event(action)

    def get_next_event(self):
        if self._event_queue:
            return self._event_queue.pop(0)
        return None

    def dispatch(self, event):
        if hasattr(event, 'type'):
            if event.type == "drag":
                self.handle_drag(event)
            elif event.type == "click":
                self.handle_click(event)
