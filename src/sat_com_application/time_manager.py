import datetime
import copy
from argparse import Action


class TimeManager:
    current_time: datetime.datetime

    start_date: datetime.datetime

    end_date: datetime.datetime

    on_tick_actions: []

    ticking_delta = 1

    def __init__(
        self, start_date: datetime.datetime, end_date: datetime.datetime = None
    ):
        self.start_date = datetime.datetime(
            start_date.year,
            start_date.month,
            start_date.day,
            start_date.hour,
            start_date.minute,
            start_date.second,
        )
        self.end_date = datetime.datetime(
            end_date.year,
            end_date.month,
            end_date.day,
            end_date.hour,
            end_date.minute,
            end_date.second,
        )

        self.current_time = start_date

        self.on_tick_actions = []

    def register_action(self, action):
        self.on_tick_actions.append(action)

    def execute_actions(self):
        for action in self.on_tick_actions:
            action()

    def tick(self, seconds: float = 1):
        self.current_time = self.current_time + datetime.timedelta(seconds=seconds)
        self.execute_actions()

    def tick_until_the_end(self):
        while self.current_time <= self.end_date:
            self.tick()
