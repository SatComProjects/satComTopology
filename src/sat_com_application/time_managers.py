import datetime
import time
from typing import Callable


class TimeManager:
    def get_current_time(self):
        pass

    def advance_time(self, time_delta: float):
        pass

    def set_time(self, new_time):
        pass


class SimulationTimeManager(TimeManager):
    current_time: datetime.datetime
    start_time: datetime.datetime
    end_time: datetime.datetime
    on_tick_action: list[Callable]

    def __init__(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        verbose: bool = False,
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

        self.verbose = verbose

    def get_current_time(self):
        return self.current_time

    def advance_time(self, time_delta: float):
        self.current_time += datetime.timedelta(seconds=time_delta)

    def set_time(self, new_time):
        self.current_time = new_time

    def register_action(self, action):
        self.on_tick_actions.append(action)

    def execute_actions(self):
        for action in self.on_tick_actions:
            tim_start = time.time()
            action()
            time_end = time.time()
            elapsed_time = time_end - tim_start
            if self.verbose:
                print(
                    f"Action {action.__name__} executed in {elapsed_time:.2f} seconds"
                )

    def tick(self, seconds: float = 1):
        self.current_time = self.current_time + datetime.timedelta(seconds=seconds)

        time_now = time.time()

        self.execute_actions()

        time_after = time.time()
        elapsed_time = time_after - time_now

        if self.verbose:
            print(f"Tick executed in {elapsed_time:.2f} seconds")

    def tick_until_the_end(self, ticking_time_in_seconds: float = 1):
        while self.current_time < self.end_date:
            if self.verbose:
                print(
                    f"Current simulation time: {self.current_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            self.tick(ticking_time_in_seconds)
