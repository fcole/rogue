from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TileType(str, Enum):
    WALL = "wall"
    FLOOR = "floor" 
    DOOR = "door"
    WATER = "water"


class EntityType(str, Enum):
    PLAYER = "player"
    OGRE = "ogre"
    GOBLIN = "goblin"
    SHOP = "shop"
    CHEST = "chest"


class EntityData(BaseModel):
    x: int
    y: int
    properties: Dict[str, Any] = Field(default_factory=dict)


class MapData(BaseModel):
    id: str
    prompt: str
    width: int
    height: int
    tiles: str  # ASCII representation
    entities: Dict[EntityType, List[EntityData]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.now)


class GenerationResult(BaseModel):
    prompt_index: int
    status: str
    map_data: Optional[MapData] = None
    generation_time: float
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class VerificationResult(BaseModel):
    test_id: str
    overall_score: float
    passed: bool
    quantitative_checks: Dict[str, Any] = Field(default_factory=dict)
    qualitative_checks: Dict[str, Any] = Field(default_factory=dict)
    llm_response: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float