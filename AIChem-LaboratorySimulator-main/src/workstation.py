from sample import Sample
from typing import Callable


class WorkstationAbility:

    def __init__(self,
                 name: str,
                 constraints: Callable,
                 ability: Callable):
        self.name = name
        self.constraints = constraints
        self.ability = ability

    def __call__(self, sample: Sample) -> Sample:
        return self.ability(sample)

    def check_constraints(self, sample: Sample) -> bool:
        return self.constraints(sample)


class Workstation:
    def __init__(self, name: str, abilities: dict[str, WorkstationAbility]):
        self.name = name
        self.abilities = abilities

    def call_ability(self, ability_name: str, sample: Sample) -> Sample:
        return self.abilities[ability_name](sample)