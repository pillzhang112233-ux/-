from datetime import datetime

class CostTracker:
    def __init__(self):
        self.total_credits = 0
        self.session_start = datetime.now()

    def add(self, credits):
        self.total_credits += credits

    def report(self):
        duration = datetime.now() - self.session_start
        minutes = duration.total_seconds() / 60
        return f"消耗: {self.total_credits} Credits | 运行时长: {minutes:.1f}m"

# 单例模式，全局共享
tracker = CostTracker()
