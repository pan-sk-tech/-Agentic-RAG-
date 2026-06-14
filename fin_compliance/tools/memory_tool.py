from fin_compliance.memory.case_memory import CaseMemory


class MemoryTool:
    def __init__(self):
        self.case_memory = CaseMemory()

    def save_audit(self, record):
        self.case_memory.append(record)

