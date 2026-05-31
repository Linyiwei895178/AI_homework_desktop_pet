"""
VPet-compatible feature layer.

This package ports the data-driven pet simulation concepts from the
Apache-2.0 VPet project into Python objects that can be composed with this
project's existing PetState without replacing current UI/controller code.
"""

from models.vpet.catalog import VPetCatalog
from models.vpet.items import Food, FoodType, Item
from models.vpet.save import ModeType, VPetGameSave
from models.vpet.service import VPetFeatureService
from models.vpet.texts import TextRule
from models.vpet.themes import Theme
from models.vpet.work import Work, WorkResult, WorkType

__all__ = [
    "Food",
    "FoodType",
    "Item",
    "ModeType",
    "TextRule",
    "Theme",
    "VPetCatalog",
    "VPetFeatureService",
    "VPetGameSave",
    "Work",
    "WorkResult",
    "WorkType",
]
