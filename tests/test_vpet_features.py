from pathlib import Path

from models.state.pet_state import PetState
from models.vpet import FoodType, ModeType, VPetCatalog, VPetFeatureService, VPetGameSave, WorkType
from models.vpet.lps import parse_lps
from models.vpet.work import run_work


def test_lps_parser_reads_food_and_work_records():
    records = parse_lps(
        """
        food:|name#water:|type#Drink:|StrengthDrink#120:|Health#1:|graph#drink:|
        work:|Type#Work:|Name#writing:|MoneyBase#8:|StrengthFood#3.5:|StrengthDrink#2.5:|Time#60:|FinishBonus#0.1:|
        """
    )

    catalog = VPetCatalog()
    catalog.extend_records(records)

    assert catalog.foods[0].name == "water"
    assert catalog.foods[0].food_type == FoodType.DRINK
    assert catalog.foods[0].graph_name == "drink"
    assert catalog.works[0].name == "writing"
    assert catalog.works[0].work_type == WorkType.WORK


def test_feed_updates_vpet_save_and_existing_pet_state():
    pet_state = PetState(mood="neutral", energy=40, intimacy=20, pet_id="test_pet")
    service = VPetFeatureService()

    event = service.feed("sandwich", pet_state=pet_state)

    assert event.action == "eat"
    assert service.save.name == "test_pet"
    assert service.save.strength_food > 40
    assert pet_state.energy >= 40
    assert pet_state.intimacy == round(service.save.likability)


def test_work_run_adds_money_and_consumes_food_drink():
    save = VPetGameSave(name="worker")
    work = VPetCatalog.builtin().find_work("writing")

    result = run_work(save, work)

    assert result.completed is True
    assert result.work_type == WorkType.WORK
    assert save.money > 100
    assert save.strength_food < 100
    assert save.strength_drink < 100


def test_study_adds_experience_and_can_change_level():
    save = VPetGameSave(name="student", exp=95)
    work = VPetCatalog.builtin().find_work("study")

    result = run_work(save, work)

    assert result.work_type == WorkType.STUDY
    assert save.total_exp_gained() > 95
    assert save.level >= 1


def test_text_rule_renders_current_save_values():
    service = VPetFeatureService(save=VPetGameSave(name="tester", host_name="owner"))

    text = service.choose_text(kind="selecttext")

    assert text is not None
    assert "Level" in text
    assert "money" in text


def test_mod_loader_reads_vpet_style_lps_directory(tmp_path: Path):
    mod = tmp_path / "demo"
    (mod / "food").mkdir(parents=True)
    (mod / "pet").mkdir()
    (mod / "text").mkdir()
    (mod / "theme").mkdir()
    (mod / "food" / "food.lps").write_text(
        "food:|name#tea:|type#Drink:|StrengthDrink#80:|Feeling#4:|price#4:|\n",
        encoding="utf-8",
    )
    (mod / "pet" / "demo.lps").write_text(
        "work:|Type#Play:|Name#mini_game:|MoneyBase#12:|StrengthFood#1:|StrengthDrink#1:|Feeling#-1:|Time#10:|\n",
        encoding="utf-8",
    )
    (mod / "text" / "ClickText.lps").write_text(
        "clicktext:|Text#Hello {name}:|LikeMin#0:|tag#all:|\n",
        encoding="utf-8",
    )
    (mod / "theme" / "default.lps").write_text(
        "default#Demo:|image#default:|\nPrimary#FF000000:|\n",
        encoding="utf-8",
    )

    catalog = VPetCatalog.from_mod_dir(mod)

    assert catalog.find_food("tea").strength_drink == 80
    assert catalog.find_work("mini_game").work_type == WorkType.PLAY
    assert catalog.texts[0].text == "Hello {name}"
    assert catalog.themes[0].colors["primary"] == "FF000000"


def test_mode_calculation_marks_low_health_as_ill():
    save = VPetGameSave(health=20, feeling=10, likability=0)

    assert save.cal_mode() == ModeType.ILL
