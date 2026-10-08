from workstation import Workstation
from sample import Sample
from copy import deepcopy


class Environment:
    def __init__(self,
                 workstation_workflow: list[Workstation]):
        self.workstation_workflow = workstation_workflow

    def run(self, sample: Sample):
        sample_copy = deepcopy(sample)
        for workstation in self.workstation_workflow:
            try:
                sample_copy = workstation(sample_copy)
            except Exception as e:
                print(f"Error in {workstation.__class__.__name__}: {e}")
                return None
