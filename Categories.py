
from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Union


@dataclass
class Category:
    name: str
    parent_category: Union["Category", None]
    space_count: int
    subcategories: List["Category"] = field(default_factory=lambda: [])
    values: Dict[str, int] = field(default_factory=lambda: {})
    level: int = 0
    
    categories_created: ClassVar[set] = set()
    
    def __post_init__(self):
        self.categories_created.add(self)
        self.level = self.space_count // 2
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __repr__(self) -> str:
        current_category = self
        while current_category:
            current_category = current_category.parent_category
            
        return f"Category: {self.name} | Level: {self.level} | Top-Level Parent: {current_category.name if current_category else 'None'}"
    
    def add_child(self, other: "Category"):
        print(f'{self} adding child {other}')
        if self == other: raise ValueError
        self.subcategories.append(other)
        other.parent_category = self
        
    @classmethod
    def find_by_level(cls, level) -> List["Category"]:
        return [i for i in cls.categories_created if i.level == level]
    
    @classmethod
    def find_by_name(cls, name) -> "Category":
        return [i for i in cls.categories_created if i.name == name][0]
    
    def get_age_group(self, key):
        return self.values[key]
    
    