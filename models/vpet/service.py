from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from models.vpet.catalog import VPetCatalog
from models.vpet.items import Food
from models.vpet.save import ModeType, VPetGameSave
from models.vpet.texts import TextRule, choose_text
from models.vpet.work import Work, WorkResult, run_work


@dataclass
class VPetEvent:
    action: str
    message: str
    save: VPetGameSave
    item_name: str | None = None
    work_result: WorkResult | None = None


class VPetFeatureService:
    """
    Adapter between VPet-style gameplay data and this project's PetState.

    Existing code can opt into this service without replacing PetState or the
    PySide UI. The mapping is deliberately conservative:
    energy follows VPet strength, intimacy follows likability, and mood follows
    the calculated VPet mode.
    """

    def __init__(self, catalog: VPetCatalog | None = None, save: VPetGameSave | None = None):
        self.catalog = catalog or VPetCatalog.builtin()
        self.save = save or VPetGameSave()

    @classmethod
    def from_project_assets(cls, project_root: str | Path, save: VPetGameSave | None = None) -> "VPetFeatureService":
        root = Path(project_root)
        catalog = VPetCatalog.builtin()
        mods_root = root / "assets" / "vpet_mods"
        if mods_root.exists():
            for mod_dir in sorted(path for path in mods_root.iterdir() if path.is_dir()):
                catalog = catalog.merge(VPetCatalog.from_mod_dir(mod_dir))
        return cls(catalog=catalog, save=save)

    def sync_from_pet_state(self, pet_state) -> None:
        self.save.name = getattr(pet_state, "pet_id", self.save.name) or self.save.name
        energy = float(getattr(pet_state, "energy", self.save.strength))
        intimacy = float(getattr(pet_state, "intimacy", self.save.likability))
        mood = str(getattr(pet_state, "mood", "neutral"))
        self.save.strength = max(0.0, min(self.save.strength_max, energy))
        self.save.strength_food = max(0.0, min(self.save.strength_max, energy))
        self.save.strength_drink = max(0.0, min(self.save.strength_max, energy))
        self.save.likability = max(0.0, min(self.save.likability_max, intimacy))
        if mood == "happy":
            self.save.feeling = max(self.save.feeling, self.save.feeling_max * 0.90)
        elif mood in {"sad", "hungry"}:
            self.save.feeling = min(self.save.feeling, self.save.feeling_max * 0.35)
        elif mood == "angry":
            self.save.health = min(self.save.health, 55)
        self.save.mode = self.save.cal_mode()

    def apply_to_pet_state(self, pet_state) -> None:
        if self.save.mode == ModeType.HAPPY:
            mood = "happy"
        elif self.save.mode == ModeType.ILL:
            mood = "sad"
        elif self.save.mode == ModeType.POOR_CONDITION:
            mood = "hungry" if self.save.strength_food <= self.save.strength_max * 0.3 else "sad"
        else:
            mood = "neutral"
        pet_state.mood = mood
        pet_state.energy = int(max(0, min(100, round(self.save.strength))))
        pet_state.intimacy = int(max(0, min(100, round(self.save.likability))))
        if hasattr(pet_state, "set_pet_id"):
            pet_state.set_pet_id(self.save.name)

    def feed(self, food_name: str, pet_state=None, buff: float = 1.0) -> VPetEvent:
        food = self.catalog.find_food(food_name)
        if food is None:
            raise KeyError(f"Unknown food: {food_name}")
        if pet_state is not None:
            self.sync_from_pet_state(pet_state)
        self.save.eat_food(food, buff=buff)
        if pet_state is not None:
            self.apply_to_pet_state(pet_state)
        return VPetEvent(
            action=food.graph_name,
            message=f"fed {food.name}",
            save=self.save,
            item_name=food.name,
        )

    def perform_work(self, work_name: str, pet_state=None, minutes: float | None = None) -> VPetEvent:
        work = self.catalog.find_work(work_name)
        if work is None:
            raise KeyError(f"Unknown work: {work_name}")
        if pet_state is not None:
            self.sync_from_pet_state(pet_state)
        result = run_work(self.save, work, minutes=minutes, complete=minutes is None or minutes >= work.time)
        if pet_state is not None:
            self.apply_to_pet_state(pet_state)
        unit = "money" if result.work_type.value == "Work" else "exp"
        return VPetEvent(
            action=work.graph or work.work_type.value.lower(),
            message=f"{work.name} gained {result.total_gained:.2f} {unit}",
            save=self.save,
            work_result=result,
        )

    def choose_text(
        self,
        *,
        kind: str = "clicktext",
        state: str | None = None,
        working: str | None = None,
        tags: set[str] | None = None,
        apply_effects: bool = False,
    ) -> str | None:
        rule = choose_text(self.catalog.texts, self.save, kind=kind, state=state, working=working, tags=tags)
        if rule is None:
            return None
        if apply_effects:
            rule.apply_effects(self.save)
        return rule.render(self.save)

    @property
    def foods(self) -> list[Food]:
        return list(self.catalog.foods)

    @property
    def works(self) -> list[Work]:
        return list(self.catalog.works)

    @property
    def texts(self) -> list[TextRule]:
        return list(self.catalog.texts)
